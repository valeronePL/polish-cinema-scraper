#!/usr/bin/env python3
"""
Polish Cinema Scraper for kino.coigdzie.pl
==========================================

Based on confirmed site analysis:
- Server-Side Rendered (static HTML) - no JS needed
- Data hierarchy: Movie → Cinema → Times (NOT Cinema → Movie)
- URL supports both day names AND YYYY-MM-DD dates
- No anti-bot protection detected
- robots.txt allows scraping (only /contao/ disallowed)

Structure confirmed:
- Movie titles in <h2> or similar headings
- Cinema names as links with href containing "/kino/"
- Times as HH:MM patterns (often with "bilet" ticket links)
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import time
import random
import re
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict, field
from concurrent.futures import ThreadPoolExecutor, as_completed

# =============================================================================
# LOGGING SETUP
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

BASE_URL = "https://kino.coigdzie.pl"

# Major Polish cities (with Polish diacritics - required by site)
CITIES = [
    "warszawa", "kraków", "wrocław", "poznań", "gdańsk",
    "łódź", "szczecin", "bydgoszcz", "lublin", "katowice",
    "białystok", "gdynia", "częstochowa", "radom", "sosnowiec",
    "kielce", "gliwice", "zielona-góra", "rzeszów", "toruń"
]

# Polish day name mapping (for URL building if needed)
POLISH_DAYS = {
    0: "poniedzialek",
    1: "wtorek", 
    2: "sroda",
    3: "czwartek",
    4: "piatek",
    5: "sobota",
    6: "niedziela"
}

# Request settings - be polite!
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
}

REQUEST_TIMEOUT = 15
DELAY_MIN = 1.5  # Minimum seconds between requests
DELAY_MAX = 3.5  # Maximum seconds between requests

# Output
OUTPUT_DIR = Path("./cinema_data")

# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class Screening:
    time: str
    ticket_url: Optional[str] = None
    format: Optional[str] = None  # 2D, 3D, IMAX, etc.
    language: Optional[str] = None  # dubbing, napisy, lektor

@dataclass
class CinemaShowtime:
    cinema_name: str
    cinema_url: Optional[str] = None
    screenings: List[Dict] = field(default_factory=list)

@dataclass
class Movie:
    title: str
    cinemas: List[Dict] = field(default_factory=list)
    # Optional metadata (if parseable)
    year: Optional[str] = None
    genre: Optional[str] = None
    duration: Optional[str] = None

@dataclass 
class DailySchedule:
    city: str
    date: str  # YYYY-MM-DD format
    day_name: str  # Polish day name
    scraped_at: str
    movies: List[Dict] = field(default_factory=list)
    cinema_count: int = 0
    screening_count: int = 0

# =============================================================================
# SCRAPER CLASS
# =============================================================================

class KinoCoigdzieScraper:
    """
    Scraper for kino.coigdzie.pl
    
    Key insight: The site organizes data by MOVIE first, then lists
    cinemas and times under each movie. This is the opposite of
    what you might expect (cinema → movies).
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self.stats = {"requests": 0, "errors": 0, "movies": 0, "screenings": 0}
    
    def _delay(self):
        """Human-like delay between requests"""
        delay = random.uniform(DELAY_MIN, DELAY_MAX)
        time.sleep(delay)
    
    def _build_url(self, city: str, date_or_day: str) -> str:
        """
        Build URL for city/date combination.
        
        Supports both formats:
        - Date: "2026-01-10" → /miasto/warszawa/dzien/2026-01-10
        - Day name: "sobota" → /miasto/warszawa/dzien/sobota
        
        RECOMMENDATION: Use YYYY-MM-DD format for reliability!
        """
        return f"{BASE_URL}/miasto/{city}/dzien/{date_or_day}"
    
    def _fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a page with error handling"""
        try:
            self.stats["requests"] += 1
            logger.debug(f"Fetching: {url}")
            
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            response.encoding = 'utf-8'  # Handle Polish characters
            
            if response.status_code == 404:
                logger.warning(f"Page not found (404): {url}")
                return None
            
            response.raise_for_status()
            return BeautifulSoup(response.text, 'html.parser')
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching {url}")
            self.stats["errors"] += 1
            return None
        except requests.RequestException as e:
            logger.error(f"Request failed for {url}: {e}")
            self.stats["errors"] += 1
            return None
    
    def _extract_times(self, text: str) -> List[str]:
        """Extract HH:MM time patterns from text"""
        # Match times like 10:30, 09:00, 21:45
        pattern = r'\b([0-2]?[0-9]:[0-5][0-9])\b'
        times = re.findall(pattern, text)
        # Normalize to HH:MM format
        return [t.zfill(5) if len(t) == 4 else t for t in times]
    
    def _extract_format_language(self, text: str) -> tuple:
        """Extract format (2D/3D/IMAX) and language (dubbing/napisy/lektor)"""
        text_lower = text.lower()
        
        # Format detection
        format_type = None
        if 'imax' in text_lower:
            format_type = 'IMAX'
        elif '4dx' in text_lower:
            format_type = '4DX'
        elif '3d' in text_lower:
            format_type = '3D'
        elif '2d' in text_lower:
            format_type = '2D'
        
        # Language detection
        language = None
        if 'dubbing' in text_lower or 'dub' in text_lower:
            language = 'dubbing'
        elif 'napisy' in text_lower or 'sub' in text_lower:
            language = 'napisy'
        elif 'lektor' in text_lower:
            language = 'lektor'
        elif 'original' in text_lower or 'oryginał' in text_lower:
            language = 'original'
        
        return format_type, language
    
    def _parse_movie_block(self, block) -> Optional[Movie]:
        """
        Parse a single movie block (div.movie).

        Verified structure from kino.coigdzie.pl:
        - div.movie container
        - h2 contains movie title
        - p.info contains "year | country | genre"
        - div.cinema.row for each cinema:
          - a.cinemaname for cinema name/link
          - span.badge[data-time] for each screening time
        """
        movie = Movie(title="", cinemas=[])

        # Find movie title in h2
        title_el = block.select_one('h2')
        if not title_el:
            return None

        movie.title = title_el.get_text(strip=True)
        if not movie.title or len(movie.title) < 2:
            return None

        # Extract format/language from title (e.g., "Avatar 3D (dubbing)")
        format_type, language = self._extract_format_language(movie.title)

        # Parse info (year | country | genre)
        info_el = block.select_one('p.info')
        if info_el:
            info_text = info_el.get_text(strip=True)
            parts = [p.strip() for p in info_text.split('|')]
            if len(parts) >= 1:
                movie.year = parts[0]
            if len(parts) >= 3:
                movie.genre = parts[2]

        # Find all cinema rows
        cinema_rows = block.select('div.cinema.row')

        for cinema_row in cinema_rows:
            # Get cinema name from a.cinemaname
            cinema_link = cinema_row.select_one('a.cinemaname')
            if not cinema_link:
                continue

            cinema_name = cinema_link.get_text(strip=True)
            if not cinema_name:
                continue

            cinema_data = CinemaShowtime(
                cinema_name=cinema_name,
                cinema_url=BASE_URL + cinema_link.get('href', ''),
                screenings=[]
            )

            # Find all time badges with data-time attribute
            time_badges = cinema_row.select('span.badge[data-time]')

            for badge in time_badges:
                # data-time format: "2026-01-10 14:30:00"
                data_time = badge.get('data-time', '')
                if data_time:
                    # Extract just the time part (HH:MM)
                    time_match = re.search(r'(\d{2}:\d{2})', data_time)
                    if time_match:
                        time_str = time_match.group(1)
                        cinema_data.screenings.append(asdict(Screening(
                            time=time_str,
                            format=format_type,
                            language=language
                        )))

            if cinema_data.screenings:
                movie.cinemas.append(asdict(cinema_data))

        return movie if movie.cinemas else None
    
    def _parse_page(self, soup: BeautifulSoup, city: str, date: str) -> DailySchedule:
        """
        Parse the full page for movie schedules.

        Verified structure: Each movie is in a div.movie container.
        """
        # Get Polish day name from date
        try:
            dt = datetime.strptime(date, "%Y-%m-%d")
            day_name = POLISH_DAYS[dt.weekday()]
        except ValueError:
            day_name = date  # If date is already a day name

        schedule = DailySchedule(
            city=city,
            date=date,
            day_name=day_name,
            scraped_at=datetime.now().isoformat(),
            movies=[]
        )

        # Select all div.movie containers
        movie_containers = soup.select('div.movie')

        if not movie_containers:
            logger.warning(f"No div.movie containers found for {city}")
            return schedule

        for container in movie_containers:
            movie = self._parse_movie_block(container)
            if movie:
                schedule.movies.append(asdict(movie))

        # Calculate statistics
        schedule.cinema_count = len(set(
            cinema['cinema_name']
            for movie in schedule.movies
            for cinema in movie.get('cinemas', [])
        ))
        schedule.screening_count = sum(
            len(cinema.get('screenings', []))
            for movie in schedule.movies
            for cinema in movie.get('cinemas', [])
        )

        self.stats["movies"] += len(schedule.movies)
        self.stats["screenings"] += schedule.screening_count

        return schedule
    
    def scrape_city_date(self, city: str, date: str) -> Optional[DailySchedule]:
        """
        Scrape a single city for a specific date.
        
        Args:
            city: City slug (e.g., "warszawa")
            date: Date in YYYY-MM-DD format (recommended) or day name
        
        Returns:
            DailySchedule object or None if failed
        """
        url = self._build_url(city, date)
        soup = self._fetch_page(url)
        
        if not soup:
            return None
        
        schedule = self._parse_page(soup, city, date)
        
        logger.info(
            f"✓ {city.upper()}: {len(schedule.movies)} movies, "
            f"{schedule.cinema_count} cinemas, {schedule.screening_count} screenings"
        )
        
        return schedule
    
    def scrape_all_cities_for_date(self, date: str) -> List[DailySchedule]:
        """
        Scrape all major cities for a specific date.
        
        Args:
            date: Date in YYYY-MM-DD format
        
        Returns:
            List of DailySchedule objects
        """
        logger.info(f"🚀 Starting scrape for {date} across {len(CITIES)} cities")
        results = []
        
        for i, city in enumerate(CITIES, 1):
            logger.info(f"[{i}/{len(CITIES)}] Scraping {city}...")
            
            schedule = self.scrape_city_date(city, date)
            if schedule:
                results.append(schedule)
            
            # Don't delay after the last request
            if i < len(CITIES):
                self._delay()
        
        return results
    
    def scrape_week(self, city: str, start_date: Optional[str] = None) -> List[DailySchedule]:
        """
        Scrape a full week for a single city.
        
        Args:
            city: City slug
            start_date: Starting date (default: today)
        
        Returns:
            List of DailySchedule objects (up to 7)
        """
        if start_date:
            start = datetime.strptime(start_date, "%Y-%m-%d")
        else:
            start = datetime.now()
        
        results = []
        for i in range(7):
            date = (start + timedelta(days=i)).strftime("%Y-%m-%d")
            schedule = self.scrape_city_date(city, date)
            if schedule:
                results.append(schedule)
            self._delay()
        
        return results
    
    def scrape_today_all_cities(self) -> List[DailySchedule]:
        """Convenience method: scrape today's schedule for all cities"""
        today = datetime.now().strftime("%Y-%m-%d")
        return self.scrape_all_cities_for_date(today)
    
    # =========================================================================
    # OUTPUT METHODS
    # =========================================================================
    
    def to_json(self, schedules: List[DailySchedule], filename: Optional[str] = None) -> Path:
        """Save schedules to JSON file"""
        if filename is None:
            filename = f"cinema_schedules_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.json"
        
        filepath = OUTPUT_DIR / filename
        
        data = [asdict(s) if isinstance(s, DailySchedule) else s for s in schedules]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"💾 Saved JSON: {filepath}")
        return filepath
    
    def to_csv_flat(self, schedules: List[DailySchedule], filename: Optional[str] = None) -> Path:
        """
        Save schedules to a flat CSV format.
        
        Columns: date, city, movie_title, cinema_name, time, format, language
        """
        if filename is None:
            filename = f"cinema_schedules_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.csv"
        
        filepath = OUTPUT_DIR / filename
        
        rows = []
        for schedule in schedules:
            s = asdict(schedule) if isinstance(schedule, DailySchedule) else schedule
            for movie in s.get('movies', []):
                for cinema in movie.get('cinemas', []):
                    for screening in cinema.get('screenings', []):
                        rows.append({
                            'date': s['date'],
                            'day': s['day_name'],
                            'city': s['city'],
                            'movie_title': movie['title'],
                            'cinema_name': cinema['cinema_name'],
                            'time': screening['time'],
                            'format': screening.get('format', ''),
                            'language': screening.get('language', ''),
                            'scraped_at': s['scraped_at']
                        })
        
        df = pd.DataFrame(rows)
        df.to_csv(filepath, index=False, encoding='utf-8')
        
        logger.info(f"💾 Saved CSV: {filepath} ({len(rows)} rows)")
        return filepath
    
    def print_stats(self):
        """Print scraping statistics"""
        print("\n" + "="*50)
        print("📊 SCRAPING STATISTICS")
        print("="*50)
        print(f"   Total requests:   {self.stats['requests']}")
        print(f"   Errors:           {self.stats['errors']}")
        print(f"   Movies found:     {self.stats['movies']}")
        print(f"   Screenings found: {self.stats['screenings']}")
        print("="*50 + "\n")


# =============================================================================
# BULK SCRAPER (Alternative approach)
# =============================================================================

class BulkCinemaScraper(KinoCoigdzieScraper):
    """
    Alternative scraper using the /kina/wszystkie/ route
    to get all cities in fewer requests.
    
    Trade-off: Bigger pages, less granular error handling
    """
    
    def scrape_all_cities_bulk(self, date: str) -> List[DailySchedule]:
        """
        Scrape all cities at once using the bulk endpoint.
        
        Note: This may return a very large page. Use with caution.
        """
        url = f"{BASE_URL}/kina/wszystkie/dzien/{date}"
        logger.info(f"🚀 Bulk scraping all cities for {date}")
        
        soup = self._fetch_page(url)
        if not soup:
            logger.warning("Bulk scrape failed, falling back to per-city scraping")
            return self.scrape_all_cities_for_date(date)
        
        # Parse the bulk page - may need different logic
        # This would need to identify city sections within the page
        # For now, fall back to individual scraping
        logger.info("Bulk page fetched, parsing by city sections...")
        
        # TODO: Implement bulk parsing if site structure supports it
        # For now, use individual city scraping
        return self.scrape_all_cities_for_date(date)


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    """Main entry point for daily scraping"""
    print("""
    ╔═══════════════════════════════════════════════════════╗
    ║     🎬 Polish Cinema Scraper - kino.coigdzie.pl 🎬    ║
    ╚═══════════════════════════════════════════════════════╝
    """)
    
    scraper = KinoCoigdzieScraper()
    
    # -------------------------------------------------------------------------
    # OPTION 1: Scrape today for all cities (most common use case)
    # -------------------------------------------------------------------------
    today = datetime.now().strftime("%Y-%m-%d")
    schedules = scraper.scrape_all_cities_for_date(today)
    
    # -------------------------------------------------------------------------
    # OPTION 2: Scrape specific city and date
    # -------------------------------------------------------------------------
    # schedule = scraper.scrape_city_date("warszawa", "2026-01-11")
    # schedules = [schedule] if schedule else []
    
    # -------------------------------------------------------------------------
    # OPTION 3: Scrape full week for one city
    # -------------------------------------------------------------------------
    # schedules = scraper.scrape_week("krakow")
    
    # -------------------------------------------------------------------------
    # Save results
    # -------------------------------------------------------------------------
    if schedules:
        # Save as both JSON (full structure) and CSV (flat, query-friendly)
        json_path = scraper.to_json(schedules)
        csv_path = scraper.to_csv_flat(schedules)
        
        scraper.print_stats()
        
        print(f"✅ Successfully scraped {len(schedules)} city schedules")
        print(f"   JSON: {json_path}")
        print(f"   CSV:  {csv_path}")
    else:
        print("❌ No data collected. Check logs for errors.")
        scraper.print_stats()


if __name__ == "__main__":
    main()
