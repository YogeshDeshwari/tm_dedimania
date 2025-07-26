import requests
from bs4 import BeautifulSoup
import sqlite3
from datetime import datetime
import time
import os
import re
import html

player_logins = [
    'yrdk', 'niyck', 'youngblizzard', 'pointiff', 'yogeshdeshwari', 'bananaapple',
    'xxgammelhdxx', 'tzigitzellas', 'fichekk', 'mglulguf', 'knotisaac', 'hoodintm',
    'heisenberg01', 'paxinho', 'thewelkuuus', 'riza_123', 'dejong2', 'brunobranco32',
    'cholub', 'certifiednebula', 'luka1234car', 'sylwson2', 'erreerrooo', 'declineee', 'bojo_interia.eu','noam3105','stwko','mitrug','bobjegraditelj'
]

url = "http://dedimania.net/tmstats/?do=stat"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
}

class ComprehensiveDataFetcher:
    """Fetches UUIDs, challenge info, and server information for player records from Dedimania"""
    
    def __init__(self, db_path, db_connection=None):
        self.db_path = db_path
        self.db_conn = db_connection  # Use shared connection to avoid locks
        self.base_url = "http://dedimania.net/tmstats/"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self._server_cache = {}  # Cache to avoid repeated requests
        self._uuid_cache = {}    # Cache to avoid repeated UUID lookups
        if self.db_conn:
            self._ensure_challenge_info_table()
    
    def _ensure_challenge_info_table(self):
        """Ensure challenge_info table exists"""
        if self.db_conn:
            cursor = self.db_conn.cursor()
        else:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS challenge_info (
                challenge_name TEXT PRIMARY KEY,
                challenge_uuid TEXT,
                environment TEXT,
                mood TEXT,
                difficulty TEXT,
                total_records INTEGER,
                world_record TEXT,
                world_record_holder TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        if self.db_conn:
            self.db_conn.commit()
        else:
            conn.commit()
            conn.close()
    
    def _names_similar(self, name1, name2):
        """Check if two challenge names are similar (basic comparison)"""
        # Remove common punctuation and normalize
        clean1 = re.sub(r'[^\w\s]', '', name1.lower()).strip()
        clean2 = re.sub(r'[^\w\s]', '', name2.lower()).strip()
        
        # Check if one contains the other or if they're very similar
        return (clean1 in clean2 or clean2 in clean1 or
                abs(len(clean1) - len(clean2)) <= 3 and
                sum(c1 == c2 for c1, c2 in zip(clean1, clean2)) >= min(len(clean1), len(clean2)) * 0.8)

    def search_for_challenge_uuid(self, challenge_name):
        """Search for challenge UUID on Dedimania (integrated from populate_challenge_info.py)"""
        if challenge_name in self._uuid_cache:
            return self._uuid_cache[challenge_name]
            
        print(f"🔍 Searching for UUID of challenge: {challenge_name}")
        
        # Decode HTML entities first
        clean_challenge_name = html.unescape(challenge_name)
        
        try:
            # Method 1: Try direct search on Dedimania
            search_url = f"{self.base_url}?do=stat"
            search_data = {
                'Challenge': clean_challenge_name,
                'RGame': 'TMU',
                'Show': 'MAPS'
            }
            
            response = self.session.post(search_url, data=search_data, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for challenge links with UUIDs
            all_links = soup.find_all('a', href=True)
            
            for link in all_links:
                href = link.get('href', '')
                text = link.get_text().strip()
                
                # Check if this link matches our challenge name
                original_match = (challenge_name.lower() in text.lower() or 
                                 text.lower() in challenge_name.lower() or
                                 self._names_similar(challenge_name, text))
                clean_match = (clean_challenge_name.lower() in text.lower() or 
                              text.lower() in clean_challenge_name.lower() or
                              self._names_similar(clean_challenge_name, text))
                
                if 'Uid=' in href and (original_match or clean_match):
                    uuid_match = re.search(r'Uid=([A-Za-z0-9_-]+)', href)
                    if uuid_match:
                        uuid = uuid_match.group(1)
                        print(f"✅ Found UUID: {uuid}")
                        self._uuid_cache[challenge_name] = uuid
                        return uuid
            
            # Method 2: Broader search if direct search fails
            print(f"🔍 Trying broader search for: {challenge_name}")
            
            # Search with just the challenge name
            search_data = {'Challenge': challenge_name[:20], 'Show': 'MAPS', 'RGame': 'TMU'}
            response = self.session.post(search_url, data=search_data, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            all_links = soup.find_all('a', href=True)
            for link in all_links:
                href = link.get('href', '')
                text = link.get_text().strip()
                
                if ('Uid=' in href and 
                    len(text) > 3 and
                    (self._names_similar(challenge_name, text) or 
                     self._names_similar(clean_challenge_name, text))):
                    uuid_match = re.search(r'Uid=([A-Za-z0-9_-]+)', href)
                    if uuid_match:
                        uuid = uuid_match.group(1)
                        print(f"✅ Found UUID with broader search: {uuid}")
                        self._uuid_cache[challenge_name] = uuid
                        return uuid
            
            print(f"❌ Could not find UUID for: {challenge_name}")
            self._uuid_cache[challenge_name] = None
            return None
            
        except Exception as e:
            print(f"❌ Error searching for UUID: {e}")
            self._uuid_cache[challenge_name] = None
            return None

    def get_challenge_info(self, challenge_uuid):
        """Fetch basic challenge information using UUID"""
        try:
            stats_url = f"{self.base_url}?do=stat&RGame=TMU&Uid={challenge_uuid}&Show=RECORDS"
            response = self.session.get(stats_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Count records in the table
            records_tables = soup.find_all('table', class_='tabl')
            total_records = 0
            
            for table in records_tables:
                data_rows = table.find_all('tr', class_='tabl')
                if len(data_rows) > 1:  # Has header + data rows
                    total_records = len(data_rows) - 1  # Subtract header row
                    break
            
            return {
                'challenge_uuid': challenge_uuid,
                'total_records': total_records,
                'environment': '',
                'mood': '',
                'difficulty': '',
                'world_record': '',
                'world_record_holder': ''
            }
            
        except Exception as e:
            print(f"❌ Error fetching challenge info: {e}")
            return None

    def ensure_challenge_uuid_and_info(self, challenge_name):
        """Ensure we have UUID and basic info for a challenge"""
        # Use shared connection or create new one
        if self.db_conn:
            cursor = self.db_conn.cursor()
        else:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
        
        # Check if we already have it in database
        cursor.execute('''
            SELECT challenge_uuid 
            FROM challenge_info 
            WHERE challenge_name = ?
        ''', (challenge_name,))
        
        result = cursor.fetchone()
        if result and result[0]:
            if not self.db_conn:
                conn.close()
            return result[0]  # Already have UUID
        
        # Need to fetch UUID
        uuid = self.search_for_challenge_uuid(challenge_name)
        if not uuid:
            if not self.db_conn:
                conn.close()
            return None
        
        # Get challenge info
        info = self.get_challenge_info(uuid)
        if info:
            # Store in database
            cursor.execute('''
                INSERT OR REPLACE INTO challenge_info 
                (challenge_name, challenge_uuid, environment, mood, difficulty, 
                 total_records, world_record, world_record_holder, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                challenge_name, info['challenge_uuid'], info['environment'],
                info['mood'], info['difficulty'], info['total_records'],
                info['world_record'], info['world_record_holder']
            ))
            
            if self.db_conn:
                self.db_conn.commit()
            else:
                conn.commit()
            print(f"💾 Stored challenge info for: {challenge_name}")
        
        if not self.db_conn:
            conn.close()
        return uuid

    def get_challenge_uuid(self, challenge_name):
        """Get challenge UUID, fetching if necessary"""
        return self.ensure_challenge_uuid_and_info(challenge_name)
    
    def fetch_server_info(self, player_login, challenge_uuid):
        """Fetch server info for a specific player and challenge"""
        cache_key = f"{player_login}_{challenge_uuid}"
        if cache_key in self._server_cache:
            return self._server_cache[cache_key]
        
        try:
            url = f"{self.base_url}?do=stat&Login={player_login}&Uid={challenge_uuid}&Show=RECORD"
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for "account" field in the HTML table structure
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                if len(rows) < 2:
                    continue
                
                # Find the Account column
                account_col_index = -1
                header_row = None
                
                for row_idx, row in enumerate(rows):
                    cells = row.find_all(['td', 'th'])
                    for col_idx, cell in enumerate(cells):
                        cell_text = cell.get_text(strip=True)
                        if cell_text == 'Account':
                            account_col_index = col_idx
                            header_row = row_idx
                            break
                    if account_col_index >= 0:
                        break
                
                # Extract server name from data rows
                if account_col_index >= 0 and header_row is not None:
                    for data_row in rows[header_row + 1:]:
                        data_cells = data_row.find_all(['td', 'th'])
                        if account_col_index < len(data_cells):
                            server_name = data_cells[account_col_index].get_text(strip=True)
                            if (server_name and 
                                server_name.lower() not in ['account', '', '-', '&nbsp;'] and
                                not server_name.startswith('&nbsp;') and
                                len(server_name) > 1):
                                self._server_cache[cache_key] = server_name
                                return server_name
            
            self._server_cache[cache_key] = "Unknown"
            return "Unknown"
            
        except Exception as e:
            print(f"    ❌ Server fetch error for {player_login}: {e}")
            self._server_cache[cache_key] = "Error"
            return "Error"
    
    def get_server_for_record(self, player_login, challenge_name):
        """Get server info for a player's record on a specific challenge"""
        challenge_uuid = self.get_challenge_uuid(challenge_name)
        if not challenge_uuid:
            return "No UUID"
        
        server = self.fetch_server_info(player_login, challenge_uuid)
        time.sleep(0.1)  # Small delay to be respectful
        return server

def get_all_headers():
    # Fetch one player's data to get all possible headers
    params = {
        "RGame": "TMU",
        "Login": player_logins[0],
        "Show": "RECORDS",
        "LIMIT": 100
    }
    resp = requests.get(url, params=params, headers=headers)
    soup = BeautifulSoup(resp.text, 'html.parser')
    tables = soup.find_all('table', class_='tabl')
    if len(tables) < 2:
        raise Exception("No data table found!")
    data_table = tables[1]
    rows = data_table.find_all('tr', class_='tabl')
    if not rows:
        raise Exception("No header row found!")
    
    header_cells = rows[0].find_all('td')
    headers_row = [cell.get_text(strip=True) for cell in header_cells]
    
    # Debug: Print the headers to see what we're getting
    print(f"Found {len(headers_row)} headers:")
    for i, header in enumerate(headers_row):
        print(f"  {i}: '{header}'")
    
    # Filter out bad headers (concatenated ones and empty ones)
    valid_headers = []
    for header in headers_row:
        # Skip empty headers and concatenated headers (longer than 20 chars usually indicates concatenation)
        if header and len(header) <= 20 and not any(h in header for h in ['GameLoginNickName', 'RecordDate#']):
            valid_headers.append(header)
    
    print(f"Valid headers after filtering: {valid_headers}")
    
    # Check if we got valid headers
    if len(valid_headers) == 0:
        raise Exception("No valid headers found after filtering!")
    
    return valid_headers

def create_table_if_needed(conn, headers_row):
    c = conn.cursor()
    # Build SQL for dynamic columns
    columns = ',\n'.join([f'"{h}" TEXT' for h in headers_row])
    
    # Find the RecordDate column name
    recorddate_col = None
    for h in headers_row:
        if h.lower().startswith('recorddate'):
            recorddate_col = h
            break
    
    if not recorddate_col:
        raise Exception("Could not find RecordDate column in headers!")
    
    # Add UNIQUE constraint on player_login and RecordDate (original full datetime)
    sql = f'''
    CREATE TABLE IF NOT EXISTS dedimania_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player_login TEXT,
        {columns},
        record_date_only TEXT,
        record_time_only TEXT,
        fetch_timestamp TEXT,
        UNIQUE(player_login, "{recorddate_col}")
    )
    '''
    c.execute(sql)
    conn.commit()

def fetch_and_store(conn, headers_row):
    c = conn.cursor()
    total_records_inserted = 0
    server_fetched_count = 0
    server_skipped_count = 0
    
    # Initialize comprehensive data fetcher (UUIDs + server info) with shared connection
    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(script_dir, '..', '..', 'dedimania_history_master.db')
    db_path = os.path.abspath(db_path)
    data_fetcher = ComprehensiveDataFetcher(db_path, db_connection=conn)
    
    print("🔍 Will fetch UUIDs + server info for new records (shared connection)...")
    print("⚡ Optimization: Skipping records that already have server info")
    
    for login in player_logins:
        params = {
            "RGame": "TMU",
            "Login": login,
            "Show": "RECORDS",
            "LIMIT": 100
        }
        print(f"Fetching Dedimania data for {login}...")
        resp = requests.get(url, params=params, headers=headers)
        if resp.status_code != 200:
            print(f"Failed to fetch data for {login}: {resp.status_code}")
            continue

        soup = BeautifulSoup(resp.text, 'html.parser')
        tables = soup.find_all('table', class_='tabl')
        if len(tables) < 2:
            print(f"No data table found for {login}!")
            continue

        data_table = tables[1]
        rows = data_table.find_all('tr', class_='tabl')
        if not rows:
            print(f"No data rows found for {login}!")
            continue

        records_for_player = 0
        # Prepare data extraction
        for row in rows[1:]:  # Skip header row
            cells = row.find_all('td')
            
            # Apply the same filtering logic as headers
            cell_texts = [cell.get_text(strip=True) for cell in cells]
            
            # Filter cells to match the header filtering logic
            valid_cells = []
            for i, cell_text in enumerate(cell_texts):
                # Use the same indices that produced our valid headers
                if i < len(cell_texts):
                    # Skip the same problematic columns we skipped in headers
                    if i >= 2 and i <= 14:  # This should match our valid header indices
                        valid_cells.append(cell_text)
            
            if len(valid_cells) != len(headers_row):
                print(f"  Skipping row with {len(valid_cells)} valid cells, expected {len(headers_row)}")
                continue
                
            record = {headers_row[i]: valid_cells[i] for i in range(len(headers_row))}
            record['player_login'] = login
            record['fetch_timestamp'] = datetime.now().isoformat(timespec='seconds')
            
            # Check if this record already has server info
            challenge_name = record.get('Challenge', '')
            recorddate_col = None
            for h in headers_row:
                if h.lower().startswith('recorddate'):
                    recorddate_col = h
                    break
            
            # Check if record already exists and has server info
            existing_server = None
            if recorddate_col and record.get(recorddate_col):
                # Build query with column name (can't use parameter for column names)
                query = f'''
                    SELECT server FROM dedimania_records 
                    WHERE player_login = ? AND "{recorddate_col}" = ?
                '''
                c.execute(query, (login, record[recorddate_col]))
                
                existing_record = c.fetchone()
                if existing_record:
                    existing_server = existing_record[0]
            
            # Only fetch server info if we don't already have it
            if existing_server and existing_server not in ['', 'No UUID', 'No Challenge', 'Unknown', 'Error']:
                print(f"    ✅ Server already exists: {existing_server}")
                record['server'] = existing_server
                server_skipped_count += 1
            elif challenge_name:
                print(f"    🔍 Processing challenge: {challenge_name[:40]}")
                
                # First ensure we have UUID (this may fetch and store challenge info)
                uuid = data_fetcher.get_challenge_uuid(challenge_name)
                if uuid:
                    print(f"    🆔 UUID: {uuid[:12]}...")
                    
                    # Now fetch server info using the UUID
                    server = data_fetcher.get_server_for_record(login, challenge_name)
                    record['server'] = server
                    print(f"    🏢 Server: {server}")
                    server_fetched_count += 1
                else:
                    print(f"    ❌ No UUID found for challenge")
                    record['server'] = 'No UUID'
                    server_fetched_count += 1
            else:
                record['server'] = 'No Challenge'
                server_fetched_count += 1
            
            # Extract date part from RecordDate for the record_date_only column
            recorddate_col = None
            for h in headers_row:
                if h.lower().startswith('recorddate'):
                    recorddate_col = h
                    break
            
            if recorddate_col and record.get(recorddate_col):
                # Extract just the date part (assuming format like "2023-12-25 14:30:15" or "2023-12-25")
                full_datetime = record[recorddate_col]
                try:
                    # Try to parse and extract date part
                    if ' ' in full_datetime:
                        date_part = full_datetime.split(' ')[0]  # Get date before space
                        time_part = full_datetime.split(' ')[1] if len(full_datetime.split(' ')) > 1 else ''  # Get time after space
                    else:
                        date_part = full_datetime  # Already just date
                        time_part = ''  # No time component
                    record['record_date_only'] = date_part
                    record['record_time_only'] = time_part
                except:
                    record['record_date_only'] = full_datetime  # Fallback to full value
                    record['record_time_only'] = ''  # Empty time on error
            else:
                record['record_date_only'] = ''
                record['record_time_only'] = ''
            
            # Build insert statement dynamically (including server column)
            columns = ', '.join(['player_login'] + [f'"{h}"' for h in headers_row] + ['record_date_only', 'record_time_only', 'fetch_timestamp', 'server'])
            placeholders = ', '.join(['?'] * (len(headers_row) + 5))
            values = [record.get('player_login')] + [record.get(h, '') for h in headers_row] + [record.get('record_date_only')] + [record.get('record_time_only')] + [record.get('fetch_timestamp')] + [record.get('server')]
            
            try:
                c.execute(f'INSERT OR IGNORE INTO dedimania_records ({columns}) VALUES ({placeholders})', values)
                if c.rowcount > 0:
                    records_for_player += 1
                    total_records_inserted += 1
            except Exception as e:
                print(f"  Error inserting record for {login}: {e}")
                print(f"  Record: {record}")
                break
        
        print(f"  Inserted {records_for_player} records for {login}")
        conn.commit()
        time.sleep(1)  # Be nice to the server
    
    print(f"\n📊 PROCESSING SUMMARY:")
    print(f"   Total records inserted: {total_records_inserted}")
    print(f"   Server info fetched: {server_fetched_count}")
    print(f"   Server info skipped (already existed): {server_skipped_count}")
    print(f"   Efficiency: {server_skipped_count/(server_fetched_count + server_skipped_count)*100:.1f}% records skipped" if (server_fetched_count + server_skipped_count) > 0 else "   No server processing needed")

if __name__ == '__main__':
    headers_row = get_all_headers()
    # Use absolute path to ensure consistent database location regardless of where script is run
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(script_dir, '..', '..', 'dedimania_history_master.db')
    db_path = os.path.abspath(db_path)
    print(f"Connecting to database: {db_path}")
    conn = sqlite3.connect(db_path)
    
    # Count existing records before fetching
    c = conn.cursor()
    try:
        c.execute("SELECT COUNT(*) FROM dedimania_records")
        result = c.fetchone()
        records_before = result[0] if result else 0
    except sqlite3.OperationalError:
        # Table doesn't exist yet
        records_before = 0
    
    create_table_if_needed(conn, headers_row)
    fetch_and_store(conn, headers_row)
    
    # Count total records after fetching
    c.execute("SELECT COUNT(*) FROM dedimania_records")
    records_after = c.fetchone()[0]
    
    new_records = records_after - records_before
    
    print(f"\n📊 Summary:")
    print(f"Records before: {records_before}")
    print(f"Records after: {records_after}")
    print(f"New records added: {new_records}")
    
    conn.close()
    print("Done! All data saved with all fields.")