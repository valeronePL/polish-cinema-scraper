# Claude Code Instructions - Polish Cinema Scraper

## Project Overview

Daily scraper for Polish cinema schedules from kino.coigdzie.pl. Scrapes 20 cities, exports to CSV/JSON, appends to Google Sheets.

## Key Files

| File | Purpose |
|------|---------|
| `src/kino_scraper_v2.py` | Main scraper - fetches and parses cinema data |
| `src/sheets_updater.py` | Appends data to Google Sheets via gspread |
| `.github/workflows/daily-cinema-scrape.yml` | Daily automation at 6 AM CET |

## CSS Selectors (kino.coigdzie.pl)

These are the actual selectors discovered from live HTML:

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

### Run scraper manually
```bash
python src/kino_scraper_v2.py
```

### Append to Google Sheets
```bash
python src/sheets_updater.py --date 2026-01-11
# or with specific CSV:
python src/sheets_updater.py --csv cinema_data/cinema_2026-01-11.csv
```

### Test a single city
```python
from kino_scraper_v2 import KinoScraper
scraper = KinoScraper()
schedule = scraper.scrape_city("warszawa", "2026-01-11")
```

## Credentials

- **Local:** `~/.config/gspread/service_account.json`
- **GitHub Actions:** Secret `GOOGLE_SERVICE_ACCOUNT`

## Data Flow

```
kino.coigdzie.pl → kino_scraper_v2.py → cinema_data/*.csv
                                              ↓
                                    sheets_updater.py
                                              ↓
                                    Google Sheets (4 tabs)
```

## Error Handling

- Empty cities (like Zielona Góra sometimes) are logged but don't fail
- Duplicate dates are skipped automatically
- Rate limiting: 1.5-3.5s random delays between requests

## Dependencies

```
requests>=2.31.0
beautifulsoup4>=4.12.0
lxml>=5.0.0
pandas>=2.0.0
gspread>=5.0.0
```
