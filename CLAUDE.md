# Claude Code Instructions - Polish Cinema Scraper

## Project Overview

Daily scraper for Polish cinema schedules from multiple sources:
- **kino.coigdzie.pl** - Main aggregator (20 cities, all chains)
- **helios.pl** - Special events (pre-premieres, "Helios dla Dzieci")
- **Cinema City API** - Official API with 35 cinemas and seat availability

Exports to CSV/JSON, appends to Google Sheets (4 tabs by chain).

## Key Files

| File | Purpose |
|------|---------|
| `src/kino_scraper_v2.py` | Main scraper - kino.coigdzie.pl |
| `src/helios_scraper.py` | Helios special events (pre-premieres, kids) |
| `src/cinema_city_scraper.py` | Cinema City API scraper |
| `src/merge_and_update.py` | Merges all data sources, updates sheets |
| `src/sheets_updater.py` | Appends data to Google Sheets via gspread |
| `.github/workflows/daily-cinema-scrape.yml` | Daily automation at 6 AM CET |

## Data Sources

### kino.coigdzie.pl (Primary)
- Static HTML, simple scraping
- All major chains: Cinema City, Multikino, Helios, independents
- 20 cities
- **Limitation:** Does NOT include special events/pre-premieres

### Cinema City API (Official)
- Public JSON API at `cinema-city.pl/pl/data-api-service/v1/quickbook/10103`
- 35 Cinema City locations across Poland
- Includes seat availability data and booking links
- ~1000+ screenings per day
- Endpoints:
  - `/cinemas/with-event/until/{date}` - List cinemas
  - `/films/until/{date}` - List films
  - `/film-events/in-cinema/{id}/at-date/{date}` - Showtimes

### helios.pl (Special Events)
- Nuxt.js SSR (data in `__NUXT__` state)
- "Helios dla Dzieci" pre-premiere events
- Weekend screenings at 10:30, 12:30
- 31+ cinema locations

## CSS Selectors (kino.coigdzie.pl)

```python
# Movie blocks
soup.select('div.movie')

# Movie title
block.select_one('h2')

# Cinema rows within movie
block.select('div.cinema.row')

# Cinema name link
cinema_row.select_one('a.cinemaname')

# Screening times (use data-time attribute, not text)
cinema_row.select('span.badge[data-time]')
```

## City Slugs

**IMPORTANT:** URLs require Polish diacritics:
- ✅ `wrocław`, `łódź`, `białystok`, `zielona-góra`
- ❌ `wroclaw`, `lodz`, `bialystok`, `zielona-gora`

## Google Sheets Structure

**Spreadsheet ID:** Set via `GOOGLE_SPREADSHEET_ID` env var or `--spreadsheet-id` arg

**Tabs:** Cinema City, Multikino, Helios, Inne

**Columns:** Date, City, Movie, Cinema, Time, Format, Language

## Common Tasks

### Run full scraper (all sources)
```bash
python src/kino_scraper_v2.py
python src/helios_scraper.py
python src/cinema_city_scraper.py
python src/merge_and_update.py --dates $(date +%Y-%m-%d)
```

### Run main scraper only (kino.coigdzie.pl)
```bash
python src/kino_scraper_v2.py
```

### Run Helios events scraper
```bash
python src/helios_scraper.py
```

### Run Cinema City API scraper
```bash
python src/cinema_city_scraper.py
```

### Append to Google Sheets
```bash
python src/sheets_updater.py --date 2026-01-12
# or with specific CSV:
python src/sheets_updater.py --csv data/daily/cinema_2026-01-12.csv
# replace existing data for a date:
python src/sheets_updater.py --csv data/daily/cinema_2026-01-12.csv --replace
```

### Test a single city
```python
from kino_scraper_v2 import KinoCoigdzieScraper
scraper = KinoCoigdzieScraper()
schedule = scraper.scrape_city_date("warszawa", "2026-01-12")
```

## Credentials

- **Local:** `~/.config/gspread/service_account.json`
- **GitHub Actions:** Secret `GOOGLE_SERVICE_ACCOUNT`

## Data Flow

```
kino.coigdzie.pl ───┐
                    │
Cinema City API ────┼──→ merge_and_update.py ──→ data/daily/*.csv
                    │                                   │
helios.pl ──────────┘                                   ↓
                                             sheets_updater.py
                                                        │
                                                        ↓
                                            Google Sheets (4 tabs)
```

## Error Handling

- Empty cities (like Zielona Góra sometimes) are logged but don't fail
- Duplicate dates are skipped automatically (use `--replace` to overwrite)
- Rate limiting: 1.5-3.5s random delays between requests
- Google Sheets API: 429 errors handled with retries

## Known Limitations

1. **kino.coigdzie.pl** doesn't include:
   - Pre-premiere special events
   - "Helios dla Dzieci" program
   - Festival screenings

2. **Historical data**: kino.coigdzie.pl returns current day data for past date URLs

3. **Helios scraper**: Currently based on known event patterns; live scraping of Nuxt state is complex

## Dependencies

```
requests>=2.31.0
beautifulsoup4>=4.12.0
lxml>=5.0.0
pandas>=2.0.0
gspread>=5.0.0
```
