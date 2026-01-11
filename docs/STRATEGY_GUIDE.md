# 🎬 Polish Cinema Scraping: Complete Strategy Guide

## Executive Summary

**Target:** kino.coigdzie.pl - Polish cinema schedule aggregator  
**Verdict:** ✅ Excellent scraping target (SSR, no anti-bot, robots.txt allows)  
**Recommended approach:** Simple HTTP requests + BeautifulSoup  
**Reliability:** High, with proper error handling and monitoring

---

## Site Analysis (Confirmed Facts)

### Technical Architecture

| Aspect | Finding | Implication |
|--------|---------|-------------|
| **Rendering** | Server-Side Rendered (SSR) | No JavaScript/Playwright needed |
| **Anti-bot** | None detected | Simple requests work |
| **robots.txt** | Only `/contao/` disallowed | Scraping permitted |
| **Encoding** | UTF-8 | Must handle Polish characters (ą, ć, ę, ł, ń, ó, ś, ź, ż) |
| **Rate limiting** | Not aggressive | Still be polite (1-3s delays) |

### Data Structure

```
Page Hierarchy (Movie-First, NOT Cinema-First!):
─────────────────────────────────────────────────
│
├── Movie Title (h2/h3 heading)
│   ├── Cinema Name (link with /kino/ in href)
│   │   └── Screening Times (HH:MM patterns)
│   ├── Cinema Name
│   │   └── Screening Times
│   └── ...
│
├── Movie Title
│   └── ...
│
└── [Sections to SKIP: "Top tygodnia", "Premiery"]
```

### URL Patterns

```
✅ RECOMMENDED (Date format - precise, archivable):
https://kino.coigdzie.pl/miasto/{city}/dzien/2026-01-10

⚠️ ALTERNATIVE (Day name - shifts with time):
https://kino.coigdzie.pl/miasto/{city}/dzien/sobota

🔄 BULK (All cities at once):
https://kino.coigdzie.pl/kina/wszystkie/dzien/2026-01-10
```

**Critical insight:** Day names like "sobota" always point to the *next* occurrence of that day, not a fixed date. For archiving purposes, **always use YYYY-MM-DD format**.

---

## Major Polish Cities (20 Confirmed Slugs)

| City | Slug | Population Tier |
|------|------|-----------------|
| Warszawa | `warszawa` | Tier 1 |
| Kraków | `krakow` | Tier 1 |
| Łódź | `lodz` | Tier 1 |
| Wrocław | `wroclaw` | Tier 1 |
| Poznań | `poznan` | Tier 1 |
| Gdańsk | `gdansk` | Tier 1 |
| Szczecin | `szczecin` | Tier 2 |
| Bydgoszcz | `bydgoszcz` | Tier 2 |
| Lublin | `lublin` | Tier 2 |
| Katowice | `katowice` | Tier 2 |
| Białystok | `bialystok` | Tier 2 |
| Gdynia | `gdynia` | Tier 2 |
| Częstochowa | `czestochowa` | Tier 3 |
| Radom | `radom` | Tier 3 |
| Sosnowiec | `sosnowiec` | Tier 3 |
| Kielce | `kielce` | Tier 3 |
| Gliwice | `gliwice` | Tier 3 |
| Zielona Góra | `zielona-gora` | Tier 3 |
| Rzeszów | `rzeszow` | Tier 3 |
| Toruń | `torun` | Tier 3 |

---

## Obstacles & Mitigations

### 1. Date Normalization Challenge

**Problem:** URL uses "sobota" but you need "2026-01-11" for your archive.

**Solution:**
```python
from datetime import datetime

# When using day names, calculate actual date
def get_actual_date_from_page(soup):
    """Extract real date from page header/tabs"""
    # Look for patterns like "sobota 11.01" in day tabs
    tab = soup.select_one('.day-tab.active, [class*="active"]')
    if tab:
        text = tab.get_text()
        # Parse "11.01" → datetime
        match = re.search(r'(\d{1,2})\.(\d{1,2})', text)
        if match:
            day, month = match.groups()
            year = datetime.now().year
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    return datetime.now().strftime("%Y-%m-%d")

# BETTER: Just use date format in URL directly!
url = f"https://kino.coigdzie.pl/miasto/warszawa/dzien/2026-01-11"
```

### 2. IP Blocking / Rate Limiting

**Problem:** Too many requests too fast → blocked.

**Solution:**
```python
import random
import time

def polite_delay():
    """Random delay between 1.5 and 3.5 seconds"""
    time.sleep(random.uniform(1.5, 3.5))

# For 20 cities: ~60-70 seconds total crawl time
# That's respectful and sustainable
```

### 3. HTML Structure Changes

**Problem:** Site redesign breaks your selectors.

**Solution: Defense in Depth**
```python
def find_movie_title(block):
    """Try multiple selectors, fail gracefully"""
    selectors = [
        'h2',                           # Primary
        'h3',                           # Fallback 1
        'a.title',                      # Fallback 2
        '[class*="film"][class*="title"]',  # Fallback 3
    ]
    for sel in selectors:
        el = block.select_one(sel)
        if el and len(el.get_text(strip=True)) > 2:
            return el.get_text(strip=True)
    return None

# Plus: Store raw HTML for failed parses
def save_debug_html(city, date, html):
    Path(f"debug/{city}_{date}.html").write_text(html)
```

### 4. Movie Title Variants

**Problem:** Same movie appears as:
- "Avatar: Ogień i popiół"
- "Avatar: Ogień i popiół 3D"
- "Avatar: Ogień i popiół (dubbing)"
- "Аватар: Вогонь і попіл" (Ukrainian)

**Solution:**
```python
def normalize_title(title):
    """Extract canonical title, separate format/language"""
    # Remove format suffixes
    title = re.sub(r'\s*(2D|3D|IMAX|4DX)\s*$', '', title, flags=re.I)
    
    # Remove language tags
    title = re.sub(r'\s*\((dubbing|napisy|lektor|sub|dub)\)\s*$', '', title, flags=re.I)
    
    return title.strip()

def extract_format(title):
    match = re.search(r'(2D|3D|IMAX|4DX)', title, re.I)
    return match.group(1).upper() if match else None
```

### 5. Empty/Missing Data

**Problem:** Some city/date combinations have no screenings.

**Solution:**
```python
def scrape_with_validation(city, date):
    schedule = scrape_city(city, date)
    
    if not schedule.movies:
        logger.warning(f"No movies found for {city}/{date}")
        # Could be: (a) no screenings, (b) parsing failed, (c) page changed
        
        # Save HTML for investigation
        save_debug_html(city, date, response.text)
        
        # Don't fail silently - track this
        return {"city": city, "date": date, "status": "empty", "movies": []}
    
    return schedule
```

### 6. Encoding Issues

**Problem:** Polish characters corrupted (Łódź → £ódz)

**Solution:**
```python
response = session.get(url)
response.encoding = 'utf-8'  # Force UTF-8

# Or let requests auto-detect from headers
response.encoding = response.apparent_encoding

# When saving:
with open('data.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
```

---

## Recommended Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DAILY SCRAPING PIPELINE                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐      │
│  │   SCHEDULER  │──────│   SCRAPER    │──────│   STORAGE    │      │
│  │              │      │              │      │              │      │
│  │ • GitHub     │      │ • requests   │      │ • JSON files │      │
│  │   Actions    │      │ • BS4        │      │ • CSV files  │      │
│  │ • Cron       │      │ • pandas     │      │ • SQLite/PG  │      │
│  │ • Cloud Fn   │      │              │      │ • S3/GCS     │      │
│  └──────────────┘      └──────────────┘      └──────────────┘      │
│         │                     │                     │              │
│         │              ┌──────▼──────┐              │              │
│         │              │  VALIDATOR  │              │              │
│         │              │             │              │              │
│         │              │ • Row count │              │              │
│         │              │ • Schema    │              │              │
│         │              │ • Anomalies │              │              │
│         │              └──────┬──────┘              │              │
│         │                     │                     │              │
│         └─────────────────────┼─────────────────────┘              │
│                               │                                    │
│                        ┌──────▼──────┐                             │
│                        │   MONITOR   │                             │
│                        │             │                             │
│                        │ • Alerts    │                             │
│                        │ • Logs      │                             │
│                        │ • Dashboard │                             │
│                        └─────────────┘                             │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Automation Options (Ranked)

### 1. 🥇 GitHub Actions (Recommended)

**Pros:**
- Free for public repos (2,000 min/month for private)
- No server management
- Built-in artifact storage
- Version-controlled schedule

**Cons:**
- Max 6-hour runtime per job
- Can't run more frequently than every 5 minutes

**Setup time:** 15 minutes

### 2. 🥈 Google Colab + Drive

**Pros:**
- Free
- Interactive development
- Easy Google Sheets export

**Cons:**
- Manual trigger (or complex scheduling workarounds)
- Session timeouts

**Setup time:** 5 minutes

### 3. 🥉 Cloud Functions (AWS Lambda / GCP)

**Pros:**
- True serverless
- Scale to 0
- Very reliable

**Cons:**
- Costs money (minimal, but not free)
- More complex setup

**Setup time:** 30-60 minutes

### 4. VPS / Raspberry Pi with Cron

**Pros:**
- Full control
- No usage limits
- Can run frequently

**Cons:**
- Requires maintenance
- Server costs (~$5/month VPS)

**Setup time:** 1-2 hours

---

## Data Output Format

### JSON (Full Structure)
```json
{
  "city": "warszawa",
  "date": "2026-01-11",
  "day_name": "niedziela",
  "scraped_at": "2026-01-10T06:00:00Z",
  "movies": [
    {
      "title": "Avatar: Ogień i popiół",
      "cinemas": [
        {
          "cinema_name": "Cinema City Arkadia",
          "cinema_url": "https://kino.coigdzie.pl/kino/cinema-city-arkadia-123",
          "screenings": [
            {"time": "10:30", "format": "3D", "language": "dubbing"},
            {"time": "14:00", "format": "IMAX", "language": "napisy"}
          ]
        }
      ]
    }
  ]
}
```

### CSV (Flat, Query-Friendly)
```csv
date,city,movie_title,cinema_name,time,format,language
2026-01-11,warszawa,Avatar: Ogień i popiół,Cinema City Arkadia,10:30,3D,dubbing
2026-01-11,warszawa,Avatar: Ogień i popiół,Cinema City Arkadia,14:00,IMAX,napisy
```

---

## Monitoring & Alerting Checklist

- [ ] **Row count threshold:** Alert if < 50 screenings for a major city
- [ ] **Parse failure detection:** Track movies/cinemas with 0 screenings
- [ ] **HTTP error tracking:** Log all non-200 responses
- [ ] **Raw HTML backup:** Store HTML when parsing yields suspicious results
- [ ] **Daily summary email/Slack:** Total screenings, any warnings
- [ ] **Weekly diff report:** Compare to previous week's totals

---

## Legal & Ethical Notes

1. ✅ **robots.txt allows scraping** (only `/contao/` disallowed)
2. ⚠️ **Check Terms of Service** at `/regulamin` if commercial use
3. ✅ **Be polite:** 1-3 second delays, ~100 requests/day max
4. ✅ **Identify yourself:** Consider custom User-Agent with contact info
5. ⚠️ **Data usage:** Personal/research OK; commercial may need permission

---

## Quick Start

```bash
# 1. Clone your repo (after setting up)
git clone https://github.com/youruser/polish-cinema-scraper.git
cd polish-cinema-scraper

# 2. Install dependencies
pip install requests beautifulsoup4 pandas lxml

# 3. Run scraper
python kino_scraper_v2.py

# 4. Check output
ls -la cinema_data/
```

For daily automation, copy `github_actions_workflow.yml` to `.github/workflows/` in your repo.

---

## Files Included

| File | Purpose |
|------|---------|
| `kino_scraper_v2.py` | Main scraper script (production-ready) |
| `github_actions_workflow.yml` | Automated daily scraping config |
| `requirements.txt` | Python dependencies |
| `README.md` | This document |

---

*Last updated: 2026-01-10*
