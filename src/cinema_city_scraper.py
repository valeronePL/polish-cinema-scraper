#!/usr/bin/env python3
"""
Cinema City Poland API Scraper
==============================

Uses Cinema City's public data-api-service for reliable schedule data.

API Endpoints:
- Cinemas: /pl/data-api-service/v1/quickbook/10103/cinemas/with-event/until/{date}
- Films: /pl/data-api-service/v1/quickbook/10103/films/until/{date}
- Showtimes: /pl/data-api-service/v1/quickbook/10103/film-events/in-cinema/{id}/at-date/{date}

Benefits over kino.coigdzie.pl:
- Official API (more reliable)
- Includes all Cinema City locations
- Has seat availability data
- Faster (JSON vs HTML parsing)
"""

import requests
import pandas as pd
import json
import time
import random
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Configuration
BASE_URL = "https://www.cinema-city.pl/pl/data-api-service/v1/quickbook/10103"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json',
    'Accept-Language': 'pl-PL,pl;q=0.9',
}

REQUEST_TIMEOUT = 15
DELAY_MIN = 0.5
DELAY_MAX = 1.5

OUTPUT_DIR = Path("./cinema_data")


@dataclass
class CinemaCityScreening:
    date: str
    city: str
    movie_title: str
    cinema_name: str
    time: str
    format: str = ""
    language: str = ""
    event_type: str = "regular"
    availability: float = 1.0  # Seat availability ratio
    booking_url: str = ""
    scraped_at: str = ""


class CinemaCityScraper:
    """Scraper for Cinema City Poland using their public API"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self.stats = {"requests": 0, "screenings": 0, "errors": 0}
        self.cinemas_cache = {}
        self.films_cache = {}

    def _delay(self):
        time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    def _fetch_json(self, url: str) -> Optional[Dict]:
        """Fetch JSON from API"""
        try:
            self.stats["requests"] += 1
            logger.debug(f"Fetching: {url}")
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)

            if response.status_code == 200:
                return response.json()

            logger.warning(f"HTTP {response.status_code}: {url}")
            return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            self.stats["errors"] += 1
            return None

    def get_cinemas(self, until_date: str = None) -> List[Dict]:
        """Get all Cinema City Poland locations"""
        if until_date is None:
            until_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

        url = f"{BASE_URL}/cinemas/with-event/until/{until_date}"
        data = self._fetch_json(url)

        if not data or "body" not in data:
            logger.error("Failed to fetch cinemas")
            return []

        cinemas = data["body"].get("cinemas", [])
        logger.info(f"Found {len(cinemas)} Cinema City locations")

        # Cache for later lookups
        for cinema in cinemas:
            self.cinemas_cache[cinema["id"]] = cinema

        return cinemas

    def get_films(self, until_date: str = None) -> List[Dict]:
        """Get all films currently showing"""
        if until_date is None:
            until_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

        url = f"{BASE_URL}/films/until/{until_date}"
        data = self._fetch_json(url)

        if not data or "body" not in data:
            logger.error("Failed to fetch films")
            return []

        films = data["body"].get("films", [])
        logger.info(f"Found {len(films)} films")

        # Cache for later lookups
        for film in films:
            self.films_cache[film["id"]] = film

        return films

    def get_showtimes(self, cinema_id: str, date: str) -> List[Dict]:
        """Get showtimes for a specific cinema and date"""
        url = f"{BASE_URL}/film-events/in-cinema/{cinema_id}/at-date/{date}"
        data = self._fetch_json(url)

        if not data or "body" not in data:
            return []

        return data["body"].get("events", [])

    def _extract_format(self, event: Dict) -> str:
        """Extract format (2D/3D/IMAX/4DX) from event attributes"""
        attrs = event.get("attributeIds", [])

        if "imax" in str(attrs).lower():
            return "IMAX"
        elif "4dx" in str(attrs).lower():
            return "4DX"
        elif "screenx" in str(attrs).lower():
            return "ScreenX"
        elif "3d" in str(attrs).lower():
            return "3D"
        elif "dolby" in str(attrs).lower():
            return "Dolby Atmos"
        return "2D"

    def _extract_language(self, event: Dict, film: Dict) -> str:
        """Extract language version from event or film"""
        attrs = str(event.get("attributeIds", [])).lower()
        title = film.get("name", "").lower()

        if "dubbing" in attrs or "dubbing" in title:
            return "dubbing"
        elif "napisy" in attrs or "napisy" in title:
            return "napisy"
        elif "lektor" in attrs:
            return "lektor"
        elif "original" in attrs:
            return "original"
        return ""

    def _get_city_from_cinema(self, cinema: Dict) -> str:
        """Extract city name from cinema data"""
        # City mapping for normalization
        city_mapping = {
            "Warszawa": "warszawa",
            "Kraków": "kraków",
            "Wrocław": "wrocław",
            "Poznań": "poznań",
            "Gdańsk": "gdańsk",
            "Łódź": "łódź",
            "Katowice": "katowice",
            "Lublin": "lublin",
            "Bydgoszcz": "bydgoszcz",
            "Białystok": "białystok",
            "Gdynia": "gdynia",
            "Częstochowa": "częstochowa",
            "Radom": "radom",
            "Sosnowiec": "sosnowiec",
            "Toruń": "toruń",
            "Gliwice": "gliwice",
            "Ruda Śląska": "ruda-śląska",
            "Rybnik": "rybnik",
            "Zielona Góra": "zielona-góra",
            "Legnica": "legnica",
            "Rybnik": "rybnik",
            "Bytom": "bytom",
            "Zabrze": "zabrze",
            "Bemowo": "warszawa",
            "Mokotów": "warszawa",
            "Sadyba": "warszawa",
            "Arkadia": "warszawa",
            "Ursynów": "warszawa",
            "Promenada": "warszawa",
            "Janki": "warszawa",
            "Galeria Mokotów": "warszawa",
            "Bonarka": "kraków",
            "Serenada": "kraków",
            "Kazimierz": "kraków",
            "Wroclavia": "wrocław",
            "Manufaktura": "łódź",
            "Silesia": "katowice",
            "Punkt 44": "katowice",
            "Felicity": "lublin",
            "Focus Mall": "bydgoszcz",
            "Riviera": "gdynia",
            "Korona": "wrocław",
        }

        # Try to extract city from cinema name/displayName
        cinema_name = cinema.get("displayName", cinema.get("name", ""))

        # Check if any known city/district is in the cinema name
        for key, city in city_mapping.items():
            if key.lower() in cinema_name.lower():
                return city

        # Try to parse from address if it's a string
        address = cinema.get("address", "")
        if isinstance(address, str) and address:
            # Address format often ends with city name
            # e.g., "ul. Złota 59, 00-120 Warszawa"
            parts = address.split(",")
            if parts:
                last_part = parts[-1].strip()
                # Remove postal code if present (e.g., "00-120 Warszawa" -> "Warszawa")
                words = last_part.split()
                if words:
                    potential_city = words[-1] if len(words) > 1 else words[0]
                    for key, city in city_mapping.items():
                        if key.lower() == potential_city.lower():
                            return city
                    return potential_city.lower()
        elif isinstance(address, dict):
            city = address.get("city", "")
            return city_mapping.get(city, city.lower())

        # Fallback: try to extract from groupId or other fields
        group = cinema.get("groupId", "")
        if group:
            for key, city in city_mapping.items():
                if key.lower() in group.lower():
                    return city

        return "unknown"

    def scrape_all_for_date(self, date: str) -> List[CinemaCityScreening]:
        """Scrape all Cinema City cinemas for a specific date"""
        screenings = []

        # Get cinemas and films first
        cinemas = self.get_cinemas()
        if not cinemas:
            return screenings

        films = self.get_films()
        if not films:
            return screenings

        self._delay()

        # Build film lookup by ID
        films_by_id = {f["id"]: f for f in films}

        # Scrape each cinema
        for i, cinema in enumerate(cinemas):
            cinema_id = cinema["id"]
            cinema_name = cinema.get("displayName", cinema.get("name", "Unknown"))
            city = self._get_city_from_cinema(cinema)

            logger.info(f"[{i+1}/{len(cinemas)}] Scraping {cinema_name}...")

            events = self.get_showtimes(cinema_id, date)

            for event in events:
                # Get film info
                film_id = event.get("filmId")
                film = films_by_id.get(film_id, {})

                # Parse event time
                event_time = event.get("eventDateTime", "")
                if event_time:
                    # Format: "2026-01-12T10:30:00"
                    try:
                        dt = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
                        time_str = dt.strftime("%H:%M")
                    except:
                        time_str = event_time[11:16] if len(event_time) > 16 else ""
                else:
                    continue

                # Create screening record
                screening = CinemaCityScreening(
                    date=date,
                    city=city,
                    movie_title=film.get("name", "Unknown"),
                    cinema_name=cinema_name,
                    time=time_str,
                    format=self._extract_format(event),
                    language=self._extract_language(event, film),
                    event_type="regular",
                    availability=event.get("soldOutStatus", {}).get("availabilityRatio", 1.0),
                    booking_url=event.get("bookingLink", ""),
                    scraped_at=datetime.now().isoformat()
                )
                screenings.append(screening)

            if i < len(cinemas) - 1:
                self._delay()

        self.stats["screenings"] = len(screenings)
        logger.info(f"✓ Total: {len(screenings)} screenings from {len(cinemas)} cinemas")

        return screenings

    def scrape_multiple_dates(self, dates: List[str]) -> List[CinemaCityScreening]:
        """Scrape multiple dates"""
        all_screenings = []

        for date in dates:
            logger.info(f"\n{'='*50}")
            logger.info(f"📅 Scraping Cinema City for {date}")
            logger.info('='*50)

            screenings = self.scrape_all_for_date(date)
            all_screenings.extend(screenings)

            if date != dates[-1]:
                time.sleep(2)  # Longer delay between dates

        return all_screenings

    def to_dataframe(self, screenings: List[CinemaCityScreening]) -> pd.DataFrame:
        """Convert screenings to DataFrame"""
        rows = [asdict(s) for s in screenings]
        return pd.DataFrame(rows)

    def to_csv(self, screenings: List[CinemaCityScreening], filename: str = None) -> Path:
        """Save screenings to CSV"""
        if filename is None:
            filename = f"cinema_city_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.csv"

        filepath = OUTPUT_DIR / filename
        df = self.to_dataframe(screenings)
        df.to_csv(filepath, index=False, encoding='utf-8')
        logger.info(f"💾 Saved {len(screenings)} screenings to {filepath}")
        return filepath

    def print_stats(self):
        print(f"\n{'='*50}")
        print("📊 CINEMA CITY SCRAPER STATISTICS")
        print(f"{'='*50}")
        print(f"   Requests made:     {self.stats['requests']}")
        print(f"   Screenings found:  {self.stats['screenings']}")
        print(f"   Errors:            {self.stats['errors']}")
        print(f"{'='*50}\n")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Cinema City Poland API Scraper')
    parser.add_argument('--date', type=str, help='Date to scrape (YYYY-MM-DD), defaults to today')
    parser.add_argument('--dates', nargs='+', help='Multiple dates to scrape')
    args = parser.parse_args()

    print("""
    ╔═══════════════════════════════════════════════════════╗
    ║     🎬 Cinema City Poland API Scraper 🎬              ║
    ╚═══════════════════════════════════════════════════════╝
    """)

    scraper = CinemaCityScraper()

    # Determine dates to scrape
    if args.dates:
        dates = args.dates
    elif args.date:
        dates = [args.date]
    else:
        dates = [datetime.now().strftime("%Y-%m-%d")]

    # Scrape each date
    all_screenings = []
    for date in dates:
        print(f"\n📅 Scraping Cinema City for {date}...")
        screenings = scraper.scrape_all_for_date(date)
        all_screenings.extend(screenings)

    if all_screenings:
        # Use first date for filename if single, otherwise use range
        if len(dates) == 1:
            filename = f"cinema_city_{dates[0]}_{datetime.now().strftime('%H%M%S')}.csv"
        else:
            filename = f"cinema_city_{dates[0]}_to_{dates[-1]}.csv"
        csv_path = scraper.to_csv(all_screenings, filename)
        scraper.print_stats()
        print(f"✅ Saved {len(all_screenings)} Cinema City screenings to {csv_path}")
    else:
        print("❌ No screenings found")
        scraper.print_stats()


if __name__ == "__main__":
    main()
