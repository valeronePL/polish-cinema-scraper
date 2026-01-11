# Polish Cinema Scraper

Daily scraper for Polish cinema schedules from [kino.coigdzie.pl](https://kino.coigdzie.pl).

## Features

- Scrapes screening times from 20 major Polish cities
- Exports to JSON and CSV formats
- Appends daily data to Google Sheets (4 tabs: Cinema City, Multikino, Helios, Inne)
- Automated daily runs via GitHub Actions (6 AM CET)
- Duplicate detection (won't add same date twice)

## Cities Covered

Warszawa, Kraków, Wrocław, Poznań, Gdańsk, Łódź, Szczecin, Bydgoszcz, Lublin, Katowice, Białystok, Gdynia, Częstochowa, Radom, Sosnowiec, Kielce, Gliwice, Zielona Góra, Rzeszów, Toruń

## Quick Start

```bash
# Install dependencies
pip install requests beautifulsoup4 pandas lxml gspread

# Run scraper (today's date)
python src/kino_scraper_v2.py

# Output in cinema_data/
ls cinema_data/
```

## Output Format

### CSV (flat)
```csv
date,city,movie_title,cinema_name,time,format,language
2026-01-11,warszawa,Avatar,Cinema City Arkadia,10:30,3D,dubbing
```

### JSON (hierarchical)
```json
{
  "city": "warszawa",
  "date": "2026-01-11",
  "movies": [
    {
      "title": "Avatar",
      "cinemas": [
        {
          "cinema_name": "Cinema City Arkadia",
          "screenings": [{"time": "10:30", "format": "3D", "language": "dubbing"}]
        }
      ]
    }
  ]
}
```

## Google Sheets Integration

### Setup (one-time)

1. Create service account at [Google Cloud Console](https://console.cloud.google.com/)
2. Enable Google Sheets API and Google Drive API
3. Download JSON key to `~/.config/gspread/service_account.json`
4. Share your Google Sheet with the service account email

### Manual append

```bash
python src/sheets_updater.py --date 2026-01-11
```

### Automated (GitHub Actions)

Add secret `GOOGLE_SERVICE_ACCOUNT` with your JSON key content. The workflow runs daily at 6 AM CET.

## Project Structure

```
polish-cinema-scraper/
├── src/
│   ├── kino_scraper_v2.py    # Main scraper
│   └── sheets_updater.py      # Google Sheets integration
├── cinema_data/               # Scraped data output
├── data/daily/                # Archived daily data
├── .github/workflows/         # GitHub Actions automation
└── pyproject.toml             # Dependencies
```

## Data Source

- **Site:** kino.coigdzie.pl (Polish cinema aggregator)
- **Method:** Server-side rendered HTML, no JavaScript needed
- **Rate limiting:** 1.5-3.5s delays between requests
- **robots.txt:** Allows scraping (only `/contao/` disallowed)

## License

MIT
