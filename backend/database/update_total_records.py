#!/usr/bin/env python3
"""
Update Total Records Script
Updates total_records for all challenges that have UUIDs by fetching current data from Dedimania
"""

import sqlite3
import requests
from bs4 import BeautifulSoup
import os
import sys
from datetime import datetime
import time
import argparse

class TotalRecordsUpdater:
    def __init__(self, db_path=None):
        if db_path is None:
            # Use absolute path to ensure consistent database location
            script_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(script_dir, '..', '..', 'dedimania_history_master.db')
            db_path = os.path.abspath(db_path)
        
        self.db_path = db_path
        self.base_url = "http://dedimania.net/tmstats/"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def get_challenges_with_uuids(self):
        """Get all challenges that have UUIDs from the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT challenge_name, challenge_uuid 
            FROM challenge_info 
            WHERE challenge_uuid IS NOT NULL 
            AND challenge_uuid != ''
            ORDER BY challenge_name
        """)
        
        challenges = cursor.fetchall()
        conn.close()
        
        return challenges
    
    def fetch_total_records_for_uuid(self, challenge_uuid):
        """Fetch total records count for a challenge UUID from Dedimania"""
        try:
            # Construct the stats URL
            stats_url = f"{self.base_url}?do=stat&RGame=TMU&Uid={challenge_uuid}&Show=RECORDS"
            
            response = self.session.get(stats_url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find ALL tables with class "tabl" - we need the one with actual data
            records_tables = soup.find_all('table', class_='tabl')
            
            records_table = None
            # Look for the table that contains data rows (not just form elements)
            for table in records_tables:
                data_rows = table.find_all('tr', class_='tabl')
                data_row_count = 0
                
                for row in data_rows:
                    cells = row.find_all('td')
                    bgcolor = row.get('bgcolor')
                    # Check if this is a data row (has bgcolor and enough cells for record data)
                    if len(cells) > 10 and bgcolor in ['#FFFFFF', '#F0F0F0']:
                        data_row_count += 1
                
                if data_row_count > 0:
                    records_table = table
                    break
            
            if records_table:
                # Count actual data rows
                record_rows = records_table.find_all('tr', class_='tabl')
                data_rows = []
                
                for row in record_rows:
                    cells = row.find_all('td')
                    bgcolor = row.get('bgcolor')
                    # Check if this is a data row
                    if len(cells) > 10 and bgcolor in ['#FFFFFF', '#F0F0F0']:
                        data_rows.append(row)
                
                total_count = len(data_rows)
                return total_count
            else:
                print(f"    Warning: No records table found")
                return 0
                
        except Exception as e:
            print(f"    Error fetching data: {e}")
            return None
    
    def update_total_records(self, challenge_name, challenge_uuid, new_count):
        """Update total_records for a challenge in the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE challenge_info 
            SET total_records = ?, last_updated = ?
            WHERE challenge_name = ? AND challenge_uuid = ?
        """, (new_count, datetime.now(), challenge_name, challenge_uuid))
        
        conn.commit()
        conn.close()
    
    def run_update(self, dry_run=False, limit=None):
        """Run the total records update process"""
        print("Starting total records update from Dedimania...")
        
        if dry_run:
            print("DRY RUN MODE - No changes will be made to database")
        
        # Get all challenges with UUIDs
        challenges = self.get_challenges_with_uuids()
        print(f"Found {len(challenges)} challenges with UUIDs")
        
        if limit:
            challenges = challenges[:limit]
            print(f"Limited to first {limit} challenges for testing")
        
        updated_count = 0
        error_count = 0
        unchanged_count = 0
        
        for i, (challenge_name, challenge_uuid) in enumerate(challenges, 1):
            print(f"\n[{i}/{len(challenges)}] Processing: {challenge_name[:50]}")
            print(f"  UUID: {challenge_uuid}")
            
            # Fetch current total records from Dedimania
            total_records = self.fetch_total_records_for_uuid(challenge_uuid)
            
            if total_records is not None:
                print(f"  Current total records: {total_records}")
                
                if not dry_run:
                    # Get existing count to compare
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT total_records FROM challenge_info WHERE challenge_uuid = ?", (challenge_uuid,))
                    result = cursor.fetchone()
                    existing_count = result[0] if result and result[0] is not None else 0
                    conn.close()
                    
                    if existing_count != total_records:
                        self.update_total_records(challenge_name, challenge_uuid, total_records)
                        print(f"  Updated: {existing_count} -> {total_records}")
                        updated_count += 1
                    else:
                        print(f"  Unchanged: {total_records}")
                        unchanged_count += 1
                else:
                    print(f"  Would update to: {total_records}")
                    updated_count += 1
            else:
                print(f"  Failed to fetch data")
                error_count += 1
            
            # Small delay to be respectful to Dedimania
            time.sleep(0.2)
        
        print(f"\n=== UPDATE SUMMARY ===")
        if not dry_run:
            print(f"Updated: {updated_count} challenges")
            print(f"Unchanged: {unchanged_count} challenges")
        else:
            print(f"Would update: {updated_count} challenges")
        print(f"Errors: {error_count} challenges")
        print(f"Total processed: {len(challenges)} challenges")

def main():
    parser = argparse.ArgumentParser(description='Update total_records for challenges using existing UUIDs')
    parser.add_argument('--db-path', help='Path to database file')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be updated without making changes')
    parser.add_argument('--limit', type=int, help='Limit number of challenges to process (for testing)')
    
    args = parser.parse_args()
    
    # Create updater
    updater = TotalRecordsUpdater(args.db_path)
    
    # Run the update
    updater.run_update(args.dry_run, args.limit)

if __name__ == "__main__":
    main()