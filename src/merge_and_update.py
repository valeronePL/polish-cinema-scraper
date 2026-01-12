#!/usr/bin/env python3
"""
Merge multiple cinema data sources and update Google Sheets.

Sources:
- kino.coigdzie.pl (main aggregator - via kino_scraper_v2.py)
- Helios events (pre-premieres, kids events - via helios_scraper.py)
- Cinema City API (official API - via cinema_city_scraper.py)

Usage:
    python merge_and_update.py --dates 2026-01-12
    python merge_and_update.py --helios-csv cinema_data/helios_events.csv
    python merge_and_update.py --cinema-city-csv cinema_data/cinema_city_*.csv
"""

import pandas as pd
import argparse
import sys
import os
from pathlib import Path
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from sheets_updater import append_to_sheet, SPREADSHEET_ID

DATA_DIR = Path("./data/daily")
CINEMA_DATA_DIR = Path("./cinema_data")


def load_existing_data(date: str) -> pd.DataFrame:
    """Load existing scraped data for a date"""
    # Try multiple file patterns
    patterns = [
        DATA_DIR / f"cinema_{date}.csv",
        DATA_DIR / f"cinema_schedules_{date}*.csv",
        CINEMA_DATA_DIR / f"cinema_{date}.csv",
        CINEMA_DATA_DIR / f"cinema_schedules_{date}*.csv",
    ]

    for pattern in patterns:
        # Handle glob patterns
        if '*' in str(pattern):
            matches = list(pattern.parent.glob(pattern.name))
            if matches:
                path = matches[0]
                print(f"📂 Loading: {path}")
                return pd.read_csv(path)
        elif pattern.exists():
            print(f"📂 Loading: {pattern}")
            return pd.read_csv(pattern)

    print(f"⚠️  No existing data found for {date}")
    return pd.DataFrame()


def load_helios_data(csv_path: str) -> pd.DataFrame:
    """Load Helios events data"""
    df = pd.read_csv(csv_path)
    print(f"📂 Loaded {len(df)} Helios events from {csv_path}")
    return df


def load_cinema_city_data(csv_path: str = None) -> pd.DataFrame:
    """Load Cinema City API data"""
    if csv_path:
        path = Path(csv_path)
        if '*' in str(path):
            matches = list(path.parent.glob(path.name))
            if matches:
                path = max(matches, key=lambda p: p.stat().st_mtime)
        if path.exists():
            df = pd.read_csv(path)
            print(f"📂 Loaded {len(df)} Cinema City screenings from {path}")
            return df

    # Auto-detect most recent Cinema City file
    cinema_city_files = list(CINEMA_DATA_DIR.glob("cinema_city_*.csv"))
    if cinema_city_files:
        latest = max(cinema_city_files, key=lambda p: p.stat().st_mtime)
        df = pd.read_csv(latest)
        print(f"📂 Auto-detected Cinema City CSV: {latest} ({len(df)} screenings)")
        return df

    print("⚠️  No Cinema City data found")
    return pd.DataFrame()


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize column names to match expected format"""
    # Expected columns: date, city, movie_title, cinema_name, time, format, language

    # Rename if needed
    column_mapping = {
        'day': 'day_name',
        'scraped_at': 'scraped_at',
        'event_type': 'event_type'
    }

    df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})

    # Ensure required columns exist
    required = ['date', 'city', 'movie_title', 'cinema_name', 'time']
    for col in required:
        if col not in df.columns:
            print(f"⚠️  Missing required column: {col}")
            return pd.DataFrame()

    # Add optional columns if missing
    if 'format' not in df.columns:
        df['format'] = ''
    if 'language' not in df.columns:
        df['language'] = ''
    if 'day_name' not in df.columns:
        df['day_name'] = ''

    return df


def merge_data(existing_df: pd.DataFrame, helios_df: pd.DataFrame, cinema_city_df: pd.DataFrame, date: str) -> pd.DataFrame:
    """Merge all data sources, removing duplicates"""
    dfs_to_merge = []
    stats = []

    # Process existing data (kino.coigdzie.pl)
    if not existing_df.empty:
        existing_df = normalize_columns(existing_df)
        if 'event_type' not in existing_df.columns:
            existing_df['event_type'] = 'regular'
        dfs_to_merge.append(existing_df)
        stats.append(f"{len(existing_df)} kino.coigdzie")

    # Filter and process Helios data
    if not helios_df.empty:
        helios_filtered = helios_df[helios_df['date'] == date].copy()
        if not helios_filtered.empty:
            helios_filtered = normalize_columns(helios_filtered)
            if 'event_type' not in helios_filtered.columns:
                helios_filtered['event_type'] = 'helios-event'
            dfs_to_merge.append(helios_filtered)
            stats.append(f"{len(helios_filtered)} Helios")

    # Filter and process Cinema City data
    if not cinema_city_df.empty:
        cc_filtered = cinema_city_df[cinema_city_df['date'] == date].copy()
        if not cc_filtered.empty:
            cc_filtered = normalize_columns(cc_filtered)
            if 'event_type' not in cc_filtered.columns:
                cc_filtered['event_type'] = 'cinema-city'
            dfs_to_merge.append(cc_filtered)
            stats.append(f"{len(cc_filtered)} Cinema City")

    if not dfs_to_merge:
        print(f"   ⚠️  No data for {date}")
        return pd.DataFrame()

    # Combine all sources
    merged = pd.concat(dfs_to_merge, ignore_index=True)

    # Remove duplicates based on key columns
    key_cols = ['date', 'city', 'movie_title', 'cinema_name', 'time']
    before_count = len(merged)
    merged = merged.drop_duplicates(subset=key_cols, keep='first')
    after_count = len(merged)

    dup_msg = f" (removed {before_count - after_count} dupes)" if before_count > after_count else ""
    print(f"   ✓ Merged: {' + '.join(stats)} = {len(merged)} total{dup_msg}")

    return merged


def save_merged_data(df: pd.DataFrame, date: str) -> Path:
    """Save merged data to CSV"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Use consistent naming
    filename = f"cinema_{date}.csv"
    filepath = DATA_DIR / filename

    # Select columns in standard order
    columns = ['date', 'city', 'movie_title', 'cinema_name', 'time', 'format', 'language']
    if 'day_name' in df.columns:
        columns.insert(1, 'day_name')
    if 'event_type' in df.columns:
        columns.append('event_type')
    if 'scraped_at' in df.columns:
        columns.append('scraped_at')

    # Only include columns that exist
    columns = [c for c in columns if c in df.columns]

    df[columns].to_csv(filepath, index=False, encoding='utf-8')
    print(f"💾 Saved merged data: {filepath}")

    return filepath


def update_sheets_for_date(df: pd.DataFrame, date: str, spreadsheet_id: str = None, replace: bool = True):
    """Update Google Sheets with merged data for a specific date"""
    sheet_id = spreadsheet_id or SPREADSHEET_ID or os.environ.get("GOOGLE_SPREADSHEET_ID")

    if not sheet_id:
        print("⚠️  No spreadsheet ID - skipping Sheets update")
        return

    # The append_to_sheet function handles chain categorization
    print(f"📤 Updating Google Sheets for {date} (replace={replace})...")

    try:
        append_to_sheet(df, date, sheet_id, replace=replace)
    except Exception as e:
        print(f"❌ Error updating sheets: {e}")


def main():
    parser = argparse.ArgumentParser(description='Merge all cinema data sources and update sheets')
    parser.add_argument('--helios-csv', type=str, help='Path to Helios events CSV')
    parser.add_argument('--cinema-city-csv', type=str, help='Path to Cinema City CSV')
    parser.add_argument('--dates', nargs='+', help='Dates to process (YYYY-MM-DD)')
    parser.add_argument('--spreadsheet-id', type=str, help='Google Spreadsheet ID')
    parser.add_argument('--no-sheets', action='store_true', help='Skip Google Sheets update')
    args = parser.parse_args()

    print("""
    ╔═══════════════════════════════════════════════════════╗
    ║     🔄 Merge Cinema Data & Update Sheets 🔄           ║
    ║  Sources: kino.coigdzie + Helios + Cinema City API    ║
    ╚═══════════════════════════════════════════════════════╝
    """)

    # Load Helios data (optional)
    helios_df = pd.DataFrame()
    if args.helios_csv:
        helios_df = load_helios_data(args.helios_csv)
    else:
        helios_files = list(CINEMA_DATA_DIR.glob("helios_events_*.csv"))
        if helios_files:
            helios_csv = max(helios_files, key=lambda p: p.stat().st_mtime)
            helios_df = load_helios_data(str(helios_csv))
        else:
            print("⚠️  No Helios CSV found (optional)")

    # Load Cinema City data (optional)
    cinema_city_df = load_cinema_city_data(args.cinema_city_csv)

    # Determine dates to process
    all_dates = set()
    if args.dates:
        all_dates.update(args.dates)
    else:
        # Collect dates from all sources
        if not helios_df.empty and 'date' in helios_df.columns:
            all_dates.update(helios_df['date'].unique().tolist())
        if not cinema_city_df.empty and 'date' in cinema_city_df.columns:
            all_dates.update(cinema_city_df['date'].unique().tolist())

    if not all_dates:
        print("❌ No dates to process. Specify --dates or ensure CSVs have data.")
        sys.exit(1)

    dates = sorted(all_dates)
    print(f"\n📅 Processing dates: {', '.join(dates)}\n")

    # Process each date
    for date in dates:
        print(f"\n{'='*50}")
        print(f"📆 Processing {date}")
        print('='*50)

        # Load existing data (kino.coigdzie.pl)
        existing_df = load_existing_data(date)

        # Merge all sources
        merged_df = merge_data(existing_df, helios_df, cinema_city_df, date)

        if merged_df.empty:
            continue

        # Save merged CSV
        save_merged_data(merged_df, date)

        # Update Google Sheets
        if not args.no_sheets:
            update_sheets_for_date(merged_df, date, args.spreadsheet_id)

    print("\n✅ Done!")


if __name__ == "__main__":
    main()
