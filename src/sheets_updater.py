#!/usr/bin/env python3
"""
Google Sheets updater for Polish Cinema Scraper.

Appends new screening data directly to Google Sheets.

Setup:
1. Go to https://console.cloud.google.com/
2. Create project or select existing
3. Enable "Google Sheets API" and "Google Drive API"
4. Create Service Account (IAM & Admin → Service Accounts)
5. Download JSON key → save as ~/.config/gspread/service_account.json
6. Share your Google Sheet with the service account email (from JSON)

Usage:
    python sheets_updater.py --date 2026-01-12
    python sheets_updater.py  # defaults to today
"""

import gspread
import pandas as pd
import argparse
import sys
import os
from pathlib import Path
from datetime import datetime

# Configuration
SPREADSHEET_ID = os.environ.get("GOOGLE_SPREADSHEET_ID", "")  # Set via env or --spreadsheet-id
CREDENTIALS_PATH = Path.home() / ".config" / "gspread" / "service_account.json"

# Chain categorization
def categorize_cinema(name: str) -> str:
    name_lower = name.lower()
    if 'multikino' in name_lower:
        return 'Multikino'
    elif 'cinema city' in name_lower:
        return 'Cinema City'
    elif 'helios' in name_lower:
        return 'Helios'
    else:
        return 'Inne'


def get_sheets_client():
    """Initialize gspread client with service account."""
    if not CREDENTIALS_PATH.exists():
        print(f"❌ Credentials not found at: {CREDENTIALS_PATH}")
        print("\nSetup instructions:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create/select project → Enable 'Google Sheets API' and 'Google Drive API'")
        print("3. Create Service Account → Download JSON key")
        print(f"4. Save as: {CREDENTIALS_PATH}")
        print("5. Share your Sheet with the service account email")
        sys.exit(1)

    return gspread.service_account(filename=str(CREDENTIALS_PATH))


def append_to_sheet(df: pd.DataFrame, date: str, spreadsheet_id: str = None, replace: bool = False):
    """Append screening data to Google Sheets.

    Args:
        df: DataFrame with screening data
        date: Date string (YYYY-MM-DD)
        spreadsheet_id: Google Spreadsheet ID
        replace: If True, delete existing data for this date before appending
    """

    sheet_id = spreadsheet_id or SPREADSHEET_ID
    if not sheet_id:
        print("❌ No spreadsheet ID provided.")
        print("   Set GOOGLE_SPREADSHEET_ID env var or use --spreadsheet-id")
        sys.exit(1)

    # Add chain column
    df = df.copy()
    df['chain'] = df['cinema_name'].apply(categorize_cinema)

    # Connect to Sheets
    print("🔗 Connecting to Google Sheets...")
    gc = get_sheets_client()

    try:
        spreadsheet = gc.open_by_key(sheet_id)
        print(f"✓ Opened spreadsheet: {spreadsheet.title}")
    except gspread.SpreadsheetNotFound:
        print(f"❌ Spreadsheet not found (ID: {sheet_id})")
        print("   Make sure you shared it with the service account email.")
        sys.exit(1)

    # Process each chain/tab
    chains = ['Cinema City', 'Multikino', 'Helios', 'Inne']

    for chain in chains:
        chain_df = df[df['chain'] == chain][['date', 'city', 'movie_title', 'cinema_name', 'time', 'format', 'language']]
        chain_df = chain_df.sort_values(['city', 'cinema_name', 'movie_title', 'time'])

        if chain_df.empty:
            print(f"   {chain}: 0 rows (skipped)")
            continue

        try:
            worksheet = spreadsheet.worksheet(chain)
        except gspread.WorksheetNotFound:
            print(f"   Creating worksheet: {chain}")
            worksheet = spreadsheet.add_worksheet(title=chain, rows=1000, cols=7)
            # Add headers
            worksheet.append_row(['Date', 'City', 'Movie', 'Cinema', 'Time', 'Format', 'Language'])

        # Check if date already exists
        existing_data = worksheet.get_all_values()
        existing_dates = set(row[0] for row in existing_data[1:] if row)  # Skip header

        if date in existing_dates:
            if replace:
                # Find rows to delete for this date
                rows_to_delete = []
                for i, row in enumerate(existing_data):
                    if i > 0 and row and row[0] == date:  # Skip header
                        rows_to_delete.append(i + 1)  # 1-indexed

                if rows_to_delete:
                    # Batch delete - find contiguous ranges
                    # Delete from bottom to top to preserve indices
                    rows_to_delete.sort(reverse=True)

                    # Use batch update for efficiency (delete in chunks)
                    deleted_count = len(rows_to_delete)

                    # Find the min and max rows to delete
                    min_row = min(rows_to_delete)
                    max_row = max(rows_to_delete)

                    # If all rows are contiguous, delete as range
                    if max_row - min_row + 1 == len(rows_to_delete):
                        worksheet.delete_rows(min_row, max_row)
                    else:
                        # Delete in batches to avoid rate limits
                        for row_idx in rows_to_delete[:50]:  # Limit to 50 deletes
                            try:
                                worksheet.delete_rows(row_idx)
                            except Exception:
                                break  # Stop on rate limit

                    print(f"   {chain}: Deleted {deleted_count} existing rows for {date}")
            else:
                print(f"   {chain}: {date} already exists (skipped)")
                continue

        # Prepare rows (replace NaN with empty string)
        rows = chain_df.fillna('').values.tolist()

        # Append rows
        worksheet.append_rows(rows, value_input_option='USER_ENTERED')
        print(f"   ✓ {chain}: +{len(rows)} rows")

    print(f"\n✅ Successfully appended {len(df)} screenings for {date}")


def main():
    parser = argparse.ArgumentParser(description='Append cinema data to Google Sheets')
    parser.add_argument('--date', type=str, default=None, help='Date to append (YYYY-MM-DD)')
    parser.add_argument('--csv', type=str, default=None, help='CSV file to import')
    parser.add_argument('--spreadsheet-id', type=str, default=None, help='Google Spreadsheet ID')
    parser.add_argument('--replace', action='store_true', help='Replace existing data for the date')
    args = parser.parse_args()

    # Determine date
    if args.date:
        date = args.date
    else:
        date = datetime.now().strftime("%Y-%m-%d")

    # Find CSV file
    if args.csv:
        csv_path = Path(args.csv)
    else:
        # Look in common locations
        possible_paths = [
            Path(f"cinema_data/cinema_{date}.csv"),
            Path(f"data/daily/cinema_{date}.csv"),
            Path(f"cinema_{date}.csv"),
        ]
        csv_path = None
        for p in possible_paths:
            if p.exists():
                csv_path = p
                break

        if not csv_path:
            print(f"❌ No CSV found for {date}")
            print("   Run the scraper first or specify --csv path")
            sys.exit(1)

    print(f"📂 Loading: {csv_path}")
    df = pd.read_csv(csv_path)
    print(f"   {len(df)} screenings loaded")

    append_to_sheet(df, date, args.spreadsheet_id, replace=args.replace)


if __name__ == "__main__":
    main()
