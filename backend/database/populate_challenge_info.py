#!/usr/bin/env python3
"""
Challenge Info Populator
Automatically discovers new challenges and populates challenge_info table with metadata from Dedimania
"""

import sqlite3
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import time
import sys
from urllib.parse import urljoin, quote, quote_plus

class ChallengeInfoPopulator:
    def __init__(self, db_path=None):
        if db_path is None:
            # Use absolute path to ensure consistent database location regardless of where script is run
            import os
            script_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(script_dir, '..', '..', 'dedimania_history_master.db')
            db_path = os.path.abspath(db_path)
        self.db_path = db_path
        self.base_url = "http://dedimania.net/tmstats/"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def get_new_challenges(self):
        """Get challenges from dedimania_records that aren't in challenge_info"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get unique challenges from dedimania_records that aren't in challenge_info
        query = """
            SELECT DISTINCT dr.Challenge 
            FROM dedimania_records dr 
            LEFT JOIN challenge_info ci ON dr.Challenge = ci.challenge_name 
            WHERE ci.challenge_name IS NULL 
            AND dr.Challenge IS NOT NULL 
            AND dr.Challenge != ''
            ORDER BY dr.Challenge
        """
        
        cursor.execute(query)
        challenges = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return challenges
    
    def search_for_challenge_uuid(self, challenge_name):
        """Search for challenge and extract UUID from HTML hover attributes"""
        print(f"🔍 Searching for UUID of challenge: {challenge_name}")
        
        # Decode HTML entities first (e.g., &quot; becomes ")
        import html
        clean_challenge_name = html.unescape(challenge_name)
        if clean_challenge_name != challenge_name:
            print(f"🔧 Decoded HTML entities: '{clean_challenge_name}' (from '{challenge_name}')")
        
        try:
            # Method 1: Try direct search on Dedimania
            search_url = f"{self.base_url}?do=stat"
            search_data = {
                'Challenge': clean_challenge_name,  # Use cleaned name for search
                'RGame': 'TMU',
                'Show': 'MAPS'  # Search for challenges/maps
            }
            
            response = self.session.post(search_url, data=search_data, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for challenge links with UUIDs in the results
            # Find all links that might contain challenge UUIDs
            all_links = soup.find_all('a', href=True)
            
            for link in all_links:
                href = link.get('href', '')
                text = link.get_text().strip()
                
                # Check if this link contains our challenge name and has a Uid parameter
                # Try matching with both original and clean names
                original_match = (challenge_name.lower() in text.lower() or 
                                 text.lower() in challenge_name.lower() or
                                 self._names_similar(challenge_name, text))
                clean_match = (clean_challenge_name.lower() in text.lower() or 
                              text.lower() in clean_challenge_name.lower() or
                              self._names_similar(clean_challenge_name, text))
                
                if 'Uid=' in href and (original_match or clean_match):
                    
                    # Extract UUID from href
                    uuid_match = re.search(r'Uid=([A-Za-z0-9_-]+)', href)
                    if uuid_match:
                        uuid = uuid_match.group(1)
                        print(f"✅ Found UUID in search results: {uuid}")
                        return uuid
            
            # Method 2: Try more general search with partial name matching
            print(f"🔄 Trying broader search for: {clean_challenge_name}")
            
            # Try searching with just the first few words of clean name
            short_name = ' '.join(clean_challenge_name.split()[:3])  # First 3 words
            search_data['Challenge'] = short_name
            
            response = self.session.post(search_url, data=search_data, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            all_links = soup.find_all('a', href=True)
            
            for link in all_links:
                href = link.get('href', '')
                text = link.get_text().strip()
                
                if ('Uid=' in href and 
                    (short_name.lower() in text.lower() or 
                     self._names_similar(clean_challenge_name, text, threshold=0.6))):
                    
                    uuid_match = re.search(r'Uid=([A-Za-z0-9_-]+)', href)
                    if uuid_match:
                        uuid = uuid_match.group(1)
                        print(f"✅ Found UUID with broader search: {uuid}")
                        return uuid
            
            # Method 3: Try searching in Records view instead of Maps view
            print(f"🔄 Trying records search for: {clean_challenge_name}")
            search_data = {
                'Challenge': clean_challenge_name,  # Use clean name
                'RGame': 'TMU',
                'Show': 'RECORDS'
            }
            
            response = self.session.post(search_url, data=search_data, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for any element with Uid in attributes
            def has_uid_attr(attrs):
                if not attrs or not isinstance(attrs, dict):
                    return False
                try:
                    return any('Uid=' in str(v) for v in attrs.values())
                except:
                    return False
            
            elements_with_uid = soup.find_all(attrs=has_uid_attr)
            
            for element in elements_with_uid:
                for attr_name, attr_value in element.attrs.items():
                    if isinstance(attr_value, str) and 'Uid=' in attr_value:
                        uuid_match = re.search(r'Uid=([A-Za-z0-9_-]+)', attr_value)
                        if uuid_match:
                            uuid = uuid_match.group(1)
                            print(f"✅ Found UUID in element attributes: {uuid}")
                            return uuid
            
            if clean_challenge_name != challenge_name:
                print(f"❌ Could not find UUID for: {challenge_name} (cleaned: {clean_challenge_name})")
            else:
                print(f"❌ Could not find UUID for: {challenge_name}")
            return None
            
        except Exception as e:
            print(f"❌ Error searching for challenge {challenge_name}: {str(e)}")
            return None
    
    def _names_similar(self, name1, name2, threshold=0.8):
        """Check if two challenge names are similar enough to be considered the same"""
        # Simple similarity check based on common words
        words1 = set(name1.lower().split())
        words2 = set(name2.lower().split())
        
        if len(words1) == 0 or len(words2) == 0:
            return False
        
        # Calculate Jaccard similarity
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        similarity = intersection / union if union > 0 else 0
        return similarity >= threshold
    
    def get_challenge_info(self, challenge_uuid):
        """Fetch challenge information using UUID"""
        print(f"📊 Fetching info for UUID: {challenge_uuid}")
        
        try:
            # Construct the stats URL
            stats_url = f"{self.base_url}?do=stat&RGame=TMU&Uid={challenge_uuid}&Show=RECORDS"
            print(f"🔗 Requesting URL: {stats_url}")
            
            response = self.session.get(stats_url, timeout=15)
            response.raise_for_status()
            
            print(f"📄 Response status: {response.status_code}")
            print(f"📄 Response length: {len(response.content)} bytes")
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Initialize info dictionary
            info = {
                'challenge_uuid': challenge_uuid,
                'challenge_name': None,
                'environment': None,
                'mood': None,
                'difficulty': None,
                'world_record': None,
                'world_record_holder': None,
                'total_records': 0
            }
            
            # Debug: Show page title
            title_element = soup.find('title')
            if title_element:
                print(f"📋 Page title: {title_element.get_text()}")
            
            # Find ALL tables with class "tabl" - we need the second one with actual data
            records_tables = soup.find_all('table', class_='tabl')
            print(f"🔍 Found {len(records_tables)} tables with class 'tabl'")
            
            records_table = None
            # Look for the table that contains data rows (not just form elements)
            for i, table in enumerate(records_tables):
                data_rows = table.find_all('tr', class_='tabl')
                data_row_count = sum(1 for row in data_rows if len(row.find_all('td')) > 10 and row.get('bgcolor') in ['#FFFFFF', '#F0F0F0'])
                print(f"  Table {i}: {len(data_rows)} rows with class 'tabl', {data_row_count} data rows")
                if data_row_count > 0:
                    records_table = table
                    print(f"  → Using table {i} for data extraction")
                    break
            
            if records_table:
                # Look for table rows with class "tabl" that contain record data
                record_rows = records_table.find_all('tr', class_='tabl')
                print(f"🔍 Found {len(record_rows)} rows with class 'tabl'")
                
                # Filter out header/form rows and get actual record rows
                data_rows = []
                for row in record_rows:
                    cells = row.find_all('td')
                    bgcolor = row.get('bgcolor')
                    # Check if this is a data row (has bgcolor and enough cells for record data)
                    if len(cells) > 10 and bgcolor in ['#FFFFFF', '#F0F0F0']:
                        data_rows.append(row)
                
                print(f"🔍 Found {len(data_rows)} data rows (filtered)")
                
                # Debug: Show first few rows structure
                for i, row in enumerate(data_rows[:3]):
                    cells = row.find_all('td')
                    bgcolor = row.get('bgcolor')
                    print(f"  Row {i}: bgcolor='{bgcolor}', cells={len(cells)}")
                    if len(cells) > 14:
                        # Show key cells content
                        rank = cells[5].get_text().strip()  # Rank should be at index 5
                        login = cells[3].get_text().strip()  # Login at index 3
                        record = cells[7].get_text().strip()  # Record at index 7
                        challenge = cells[11].get_text().strip()  # Challenge at index 11
                        print(f"    Rank: '{rank}', Login: '{login}', Record: '{record}', Challenge: '{challenge[:20]}...'")
                
                if data_rows:
                    info['total_records'] = len(data_rows)
                    
                    # Find the rank 1 record (world record)
                    world_record_row = None
                    for row in data_rows:
                        cells = row.find_all('td')
                        if len(cells) > 14:
                            rank_cell = cells[5]  # Rank is at index 5
                            rank = rank_cell.get_text().strip()
                            if rank == '1':
                                world_record_row = row
                                print(f"✅ Found world record row (rank 1)")
                                break
                    
                    # If no rank 1 found, use first row as fallback
                    if not world_record_row:
                        world_record_row = data_rows[0]
                        print(f"⚠️ No rank 1 found, using first row as fallback")
                    
                    cells = world_record_row.find_all('td')
                    print(f"🔍 World record row has {len(cells)} cells")
                    
                    if len(cells) > 14:
                        # Debug: Show all cells in the world record row
                        print(f"📊 World record row cell contents:")
                        for i, cell in enumerate(cells[:15]):  # First 15 cells
                            content = cell.get_text().strip()
                            has_link = cell.find('a') is not None
                            print(f"  Cell {i}: '{content}' (has_link: {has_link})")
                        
                        # Extract data based on correct column indices:
                        # 0-1: spacers, 2: Game, 3: Login, 4: NickName, 5: Rank, 6: Max, 
                        # 7: Record, 8: Mode, 9: CPs, 10: MapCPs, 11: Challenge, 12: Environment, 
                        # 13: RecordDate, 14: #
                        
                        try:
                            # Extract world record holder (Login - index 3)
                            login_cell = cells[3]
                            if login_cell.find('a'):
                                info['world_record_holder'] = login_cell.find('a').get_text().strip()
                            else:
                                info['world_record_holder'] = login_cell.get_text().strip()
                            print(f"✅ Extracted world_record_holder: '{info['world_record_holder']}'")
                            
                            # Extract world record time (Record - index 7)
                            record_cell = cells[7]
                            if record_cell.find('a'):
                                info['world_record'] = record_cell.find('a').get_text().strip()
                            else:
                                info['world_record'] = record_cell.get_text().strip()
                            print(f"✅ Extracted world_record: '{info['world_record']}'")
                            
                            # Extract challenge name (Challenge - index 11)
                            challenge_cell = cells[11]
                            if challenge_cell.find('a'):
                                info['challenge_name'] = challenge_cell.find('a').get_text().strip()
                            else:
                                info['challenge_name'] = challenge_cell.get_text().strip()
                            print(f"✅ Extracted challenge_name: '{info['challenge_name']}'")
                            
                            # Extract environment (Environment - index 12)
                            env_cell = cells[12]
                            info['environment'] = env_cell.get_text().strip()
                            print(f"✅ Extracted environment: '{info['environment']}'")
                            
                            # Extract mode information (Mode - index 8)
                            mode_cell = cells[8]
                            mode = mode_cell.get_text().strip()
                            info['difficulty'] = mode
                            print(f"✅ Extracted difficulty/mode: '{info['difficulty']}'")
                        
                        except Exception as e:
                            print(f"❌ Error extracting data from cells: {str(e)}")
                    
                    else:
                        print(f"❌ World record row doesn't have enough cells ({len(cells)} <= 14)")
                else:
                    print(f"❌ No valid data rows found")
            else:
                print(f"❌ No records table found with data")
                # Debug: Show what tables are available
                all_tables = soup.find_all('table')
                print(f"🔍 Found {len(all_tables)} total tables")
            
            # Clean up any None values to empty strings for database consistency
            for key, value in info.items():
                if value is None:
                    info[key] = ''
            
            print(f"✅ Final extracted info: {info}")
            return info
            
        except Exception as e:
            print(f"❌ Error fetching info for UUID {challenge_uuid}: {str(e)}")
            return None
    
    def save_challenge_info(self, info):
        """Save challenge information to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Insert or update challenge info
            cursor.execute("""
                INSERT OR REPLACE INTO challenge_info 
                (challenge_name, challenge_uuid, environment, mood, difficulty, 
                 world_record, world_record_holder, total_records, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                info['challenge_name'],
                info['challenge_uuid'],
                info['environment'],
                info['mood'],
                info['difficulty'],
                info['world_record'],
                info['world_record_holder'],
                info['total_records'],
                datetime.now()
            ))
            
            conn.commit()
            print(f"✅ Saved info for: {info['challenge_name']}")
            return True
            
        except Exception as e:
            print(f"❌ Error saving info for {info['challenge_name']}: {str(e)}")
            return False
        finally:
            conn.close()
    
    def populate_all_challenges(self):
        """Main function to populate challenge info for all new challenges"""
        print("🚀 Starting Challenge Info Population")
        print("=" * 60)
        
        # Get new challenges
        new_challenges = self.get_new_challenges()
        
        if not new_challenges:
            print("✅ No new challenges found. All challenges are up to date!")
            return
        
        print(f"📋 Found {len(new_challenges)} new challenges to process:")
        for i, challenge in enumerate(new_challenges, 1):
            print(f"  {i}. {challenge}")
        
        print("\n🔄 Processing challenges...")
        
        successful = 0
        failed = 0
        
        for i, challenge_name in enumerate(new_challenges, 1):
            print(f"\n--- Processing {i}/{len(new_challenges)}: {challenge_name} ---")
            
            # Step 1: Find UUID
            uuid = self.search_for_challenge_uuid(challenge_name)
            if not uuid:
                failed += 1
                continue
            
            # Step 2: Get challenge info
            info = self.get_challenge_info(uuid)
            if not info or not info.get('challenge_name'):
                failed += 1
                continue
            
            # Use original name if extraction failed
            if not info['challenge_name']:
                info['challenge_name'] = challenge_name
            
            # Step 3: Save to database
            if self.save_challenge_info(info):
                successful += 1
            else:
                failed += 1
            
            # Be respectful to the server
            time.sleep(2)
        
        print(f"\n🏁 Processing Complete!")
        print(f"✅ Successfully processed: {successful}")
        print(f"❌ Failed: {failed}")
        print(f"📊 Total challenges processed: {successful + failed}")

    def test_single_challenge(self, challenge_name):
        """Test the script with a single challenge for debugging"""
        print(f"🧪 Testing with challenge: {challenge_name}")
        print("=" * 60)
        
        # Step 1: Find UUID
        uuid = self.search_for_challenge_uuid(challenge_name)
        if not uuid:
            print(f"❌ Could not find UUID for: {challenge_name}")
            return False
        
        # Step 2: Get challenge info
        info = self.get_challenge_info(uuid)
        if not info:
            print(f"❌ Could not extract info for UUID: {uuid}")
            return False
        
        # Step 3: Display results (don't save to database in test mode)
        print(f"\n📊 Test Results:")
        print(f"Challenge Name: {info['challenge_name']}")
        print(f"UUID: {info['challenge_uuid']}")
        print(f"Environment: {info['environment']}")
        print(f"Mode/Difficulty: {info['difficulty']}")
        print(f"World Record: {info['world_record']}")
        print(f"World Record Holder: {info['world_record_holder']}")
        print(f"Total Records: {info['total_records']}")
        
        return True

def main():
    import argparse
    import os
    
    # Get absolute path for default database location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_db_path = os.path.abspath(os.path.join(script_dir, '..', '..', 'dedimania_history_master.db'))
    
    parser = argparse.ArgumentParser(description='Populate challenge_info table from Dedimania')
    parser.add_argument('--test', type=str, help='Test with a specific challenge name')
    parser.add_argument('--db', type=str, default=default_db_path, help='Database path')
    
    args = parser.parse_args()
    
    populator = ChallengeInfoPopulator(db_path=args.db)
    
    if args.test:
        # Test mode with specific challenge
        populator.test_single_challenge(args.test)
    else:
        # Normal mode - populate all challenges
        populator.populate_all_challenges()

if __name__ == "__main__":
    main() 