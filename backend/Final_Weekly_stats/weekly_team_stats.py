#!/usr/bin/env python3
"""
Weekly Team Statistics Generator
Creates engaging weekly reports for TrackMania team performance
"""

import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import os
import argparse
import requests
from bs4 import BeautifulSoup
import time

# Configuration
PLAYER_LOGINS = [
    'yrdk', 'niyck', 'youngblizzard', 'pointiff', 'yogeshdeshwari', 'bananaapple',
    'xxgammelhdxx', 'tzigitzellas', 'fichekk', 'mglulguf', 'knotisaac', 'hoodintm',
    'heisenberg01', 'paxinho', 'thewelkuuus', 'riza_123', 'dejong2', 'brunobranco32',
    'cholub', 'certifiednebula', 'luka1234car', 'sylwson2', 'erreerrooo', 'declineee', 
    'bojo_interia.eu', 'noam3105', 'stwko', 'mitrug', 'bobjegraditelj'
]

def get_weekly_date_range():
    """Calculate the most recent Thursday to current day date range"""
    today = datetime.now()
    
    # Find the most recent Thursday (but if today is Thursday, go back to previous Thursday)
    # Thursday is weekday 3 (Monday=0, Sunday=6)
    if today.weekday() == 3:
        # Today is Thursday, go back 7 days to get the previous Thursday
        start_date = today - timedelta(days=7)
    else:
        # Go back to the most recent Thursday
        days_since_thursday = (today.weekday() - 3) % 7
        start_date = today - timedelta(days=days_since_thursday)
    
    # End date is always today
    end_date = today
    
    return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')

class WeeklyStatsGenerator:
    def __init__(self, db_path=None):
        if db_path is None:
            # Use absolute path to ensure consistent database location regardless of where script is run
            import os
            script_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(script_dir, '..', '..', 'dedimania_history_master.db')
            db_path = os.path.abspath(db_path)
        self.db_path = db_path
        self._latest_nicks_cache = None
        
    def format_time(self, time_str):
        """Convert time string to seconds for comparison"""
        if not time_str:
            return float('inf')
        
        try:
            if ':' in time_str:
                parts = time_str.split(':')
                if len(parts) == 2:
                    minutes, seconds = parts
                    return float(minutes) * 60 + float(seconds)
            return float(time_str)
        except:
            return float('inf')
    
    def get_latest_data(self):
        """Get latest data from database for the most recent Thursday to current day range"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get most recent Thursday to current day date range
        start_date, end_date = get_weekly_date_range()
        
        cursor.execute("""
            SELECT player_login, NickName, Challenge, Record, Rank, RecordDate, Envir, Mode, server
            FROM dedimania_records 
            WHERE RecordDate >= ? AND RecordDate <= ?
            ORDER BY RecordDate DESC
        """, (start_date, end_date))
        
        records = cursor.fetchall()
        conn.close()
        
        return records
    
    def deduplicate_records(self, records):
        """
        Deduplicate records to keep only the best rank for each player-track combination.
        If a player has multiple records on the same track, only keep the one with the best (lowest) rank.
        """
        # Group records by (player_login, track) combination
        track_records = {}
        
        for record in records:
            login, nick, track, time, rank, date, envir, mode, server = record
            
            if not login or not track:
                continue
                
            # Convert rank to integer for comparison (higher values for non-numeric ranks)
            try:
                rank_int = int(rank) if rank else 999
            except:
                rank_int = 999
            
            key = (login, track)
            
            if key not in track_records:
                track_records[key] = record
            else:
                # Keep the record with the better (lower) rank
                existing_record = track_records[key]
                existing_rank = existing_record[4]  # rank is at index 4
                try:
                    existing_rank_int = int(existing_rank) if existing_rank else 999
                except:
                    existing_rank_int = 999
                
                if rank_int < existing_rank_int:
                    track_records[key] = record
        
        # Return deduplicated records
        return list(track_records.values())
    
    def analyze_track_ownership(self, records):
        """Analyze who owns which tracks (#1 positions)"""
        track_owners = {}
        
        # Get latest nicknames for all logins
        latest_nicks = self.get_all_latest_nicknames(records)
        
        for record in records:
            login, nick, track, time, rank, date, envir, mode, server = record
            
            if rank == '1':  # World record holder
                if track not in track_owners:
                    track_owners[track] = {
                        'owner': latest_nicks.get(login, login),
                        'login': login,
                        'time': time,
                        'envir': envir,
                        'date': date
                    }
                else:
                    # Keep most recent #1
                    if date > track_owners[track]['date']:
                        track_owners[track] = {
                            'owner': latest_nicks.get(login, login),
                            'login': login,
                            'time': time,
                            'envir': envir,
                            'date': date
                        }
        
        return track_owners
    
    def get_all_latest_nicknames(self, records):
        """Get a mapping of all logins to their most recent nicknames"""
        if self._latest_nicks_cache is not None:
            return self._latest_nicks_cache
            
        login_to_nick = {}
        login_to_latest_date = {}
        
        for record in records:
            login, nick, track, time, rank, date, envir, mode, server = record
            if nick:  # Only update if we have a nickname
                if login not in login_to_latest_date or date > login_to_latest_date[login]:
                    login_to_latest_date[login] = date
                    login_to_nick[login] = nick
        
        self._latest_nicks_cache = login_to_nick
        return login_to_nick
    
    def detect_rivalries(self, records):
        """Detect ongoing rivalries between players with win/loss records"""
        # Track wins per login directly - much simpler approach
        rivalry_data = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))  # rivalry_key -> track -> login -> wins
        
        # Get latest nicknames for all logins
        login_to_nick = self.get_all_latest_nicknames(records)
        
        # Group records by track to compare players
        track_records = defaultdict(list)
        
        for record in records:
            login, nick, track, time, rank, date, envir, mode, server = record
            
            try:
                rank_int = int(rank) if rank else 999
                track_records[track].append({
                    'login': login,
                    'nick': nick,
                    'rank': rank_int,
                    'time': time
                })
            except:
                continue
        
        # Find head-to-head comparisons on each track
        for track, records_list in track_records.items():
            if len(records_list) >= 2:
                # Get best record for each player on this track
                player_best = {}
                for record in records_list:
                    login = record['login']
                    if login not in player_best or record['rank'] < player_best[login]['rank']:
                        player_best[login] = record
                
                # Compare all player pairs (exclude yogeshdeshwari from rivalries)
                players = [login for login in player_best.keys() if login != 'yogeshdeshwari']
                for i in range(len(players)):
                    for j in range(i + 1, len(players)):
                        p1_login = players[i]
                        p2_login = players[j]
                        
                        p1_record = player_best[p1_login]
                        p2_record = player_best[p2_login]
                        
                        # Create rivalry key (consistent ordering)
                        rivalry_key = tuple(sorted([p1_login, p2_login]))
                        
                        # Determine winner (lower rank wins) and directly track wins per login
                        if p1_record['rank'] < p2_record['rank']:
                            rivalry_data[rivalry_key][track][p1_login] += 1
                        elif p2_record['rank'] < p1_record['rank']:
                            rivalry_data[rivalry_key][track][p2_login] += 1
                        # If ranks are equal, it's a tie (no points awarded)
        
        # Calculate overall rivalries
        rivalries = []
        
        for rivalry_key, track_data in rivalry_data.items():
            # Calculate total wins per login
            login1, login2 = rivalry_key
            total_wins_login1 = sum(track_wins.get(login1, 0) for track_wins in track_data.values())
            total_wins_login2 = sum(track_wins.get(login2, 0) for track_wins in track_data.values())
            shared_tracks = len(track_data)
            
            if shared_tracks >= 3:  # Significant rivalry
                # Get current nicknames
                nick1 = login_to_nick.get(login1, login1)
                nick2 = login_to_nick.get(login2, login2)
                
                # Determine leader and order names (leader first)
                if total_wins_login1 > total_wins_login2:
                    leader_name = nick1
                    loser_name = nick2
                    leader = leader_name
                    player1_wins = total_wins_login1
                    player2_wins = total_wins_login2
                elif total_wins_login2 > total_wins_login1:
                    leader_name = nick2
                    loser_name = nick1
                    leader = leader_name
                    player1_wins = total_wins_login2
                    player2_wins = total_wins_login1
                else:
                    # For ties, use alphabetical order
                    leader_name = nick1 if nick1 < nick2 else nick2
                    loser_name = nick2 if nick1 < nick2 else nick1
                    leader = "Tied"
                    if nick1 < nick2:
                        player1_wins = total_wins_login1
                        player2_wins = total_wins_login2
                    else:
                        player1_wins = total_wins_login2
                        player2_wins = total_wins_login1
                
                # Score always matches player order: Player1 vs Player2 (Player1_wins-Player2_wins)
                score = f"{player1_wins}-{player2_wins}"
                
                rivalries.append({
                    'player1': leader_name,  # Leader always first
                    'player2': loser_name,   # Loser always second
                    'shared_tracks': shared_tracks,
                    'p1_wins': player1_wins,  # Wins for player1 (as displayed)
                    'p2_wins': player2_wins,  # Wins for player2 (as displayed)
                    'leader': leader,
                    'score': score,
                    'tracks': list(track_data.keys())
                })
        
        return sorted(rivalries, key=lambda x: x['shared_tracks'], reverse=True)
    
    def get_challenge_info_cache(self):
        """Get challenge info from database and cache it"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT challenge_name, total_records
            FROM challenge_info
            WHERE total_records IS NOT NULL AND total_records > 0
        """)
        
        challenge_cache = {}
        for row in cursor.fetchall():
            challenge_name, total_records = row
            challenge_cache[challenge_name] = total_records
        
        conn.close()
        return challenge_cache
    
    def create_report_folder(self):
        """Create a timestamped folder for the weekly report"""
        # Create folder name with current date
        folder_name = f"weekly_report_{datetime.now().strftime('%Y_%m_%d')}"
        
        # Get the root directory path (go up two levels from current script location)
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        folder_path = os.path.join(root_dir, folder_name)
        
        # Create the folder if it doesn't exist
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            print(f"📁 Created folder: {folder_path}")
        else:
            print(f"📁 Using existing folder: {folder_path}")
        
        return folder_path
    
    def generate_report(self, output_file=None):
        """Generate the full weekly report"""
        # Create folder for this report
        folder = self.create_report_folder()
        
        if output_file:
            output_file = os.path.join(folder, os.path.basename(output_file))
        else:
            output_file = os.path.join(folder, 'weekly_stats.txt')
        
        # Create output buffer
        output_lines = []
        
        def write_line(text=""):
            output_lines.append(text)
            if not output_file:  # Only print if not saving to file
                print(text)
        
        write_line("🏁 TRACKMANIA TEAM WEEKLY HIGHLIGHTS")
        write_line("=" * 60)
        
        # Get most recent Thursday to current day date range
        start_date, end_date = get_weekly_date_range()
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        
        # Print the date range being used
        print(f"📅 Using most recent Thursday to current day range: {start_date} to {end_date}")
        
        write_line(f"📅 Week of {start_dt.strftime('%B %d')} - {end_dt.strftime('%B %d, %Y')}")
        write_line(f"👥 Team: {len(PLAYER_LOGINS)} Active Players")
        write_line()
        
        # Get data
        raw_records = self.get_latest_data()
        
        if not raw_records:
            write_line("❌ No data available for this week")
            return
        
        # Deduplicate records to keep only best rank per player-track combination
        # (for statistics that should count unique track achievements)
        deduplicated_records = self.deduplicate_records(raw_records)
        
        write_line(f"📊 Analyzing {len(deduplicated_records)} unique records from {len(raw_records)} total dedi's this week...")
        write_line()
        
        # Get all analysis results
        # Time masters uses raw data to track activity patterns across time
        time_masters = self.analyze_time_masters(raw_records)
        # Performance stats use deduplicated data (only best rank per track matters)
        performance_elite = self.analyze_performance_elite(deduplicated_records)
        # Solo explorer analysis (most solo tracks)
        solo_explorer_results = self.analyze_solo_explorer(raw_records)
        performance_elite.update(solo_explorer_results)
        # Volume stats use deduplicated data (unique track counts)
        volume_champions = self.analyze_volume_champions(deduplicated_records)
        # Lolsport analysis uses deduplicated data (unique track achievements)
        lolsport_stats = self.analyze_lolsport_addict(deduplicated_records)
        
        # 1. TRACK OWNERSHIP
        write_line("🏆 TRACK OWNERSHIP - WHO'S THE KING?")
        write_line("-" * 40)
        
        # Track ownership uses deduplicated data (only best records matter for WR)
        track_owners = self.analyze_track_ownership(deduplicated_records)
        
        if track_owners:
            # Group by login for consistent counting, but use most recent nickname for display
            login_ownership = defaultdict(lambda: {'count': 0, 'nick': ''})
            for owner in track_owners.values():
                login = owner['login']
                login_ownership[login]['count'] += 1
                login_ownership[login]['nick'] = owner['owner']  # Keep most recent nickname
            
            # Sort by count and convert to display format
            ownership_list = [(data['nick'], data['count']) for data in login_ownership.values()]
            ownership_list.sort(key=lambda x: x[1], reverse=True)
            
            write_line(f"👑 TRACK ROYALTY (Most WRs):")
            for i, (player, count) in enumerate(ownership_list[:5]):
                crown = "👑" if i == 0 else "🥇" if i == 1 else "🥈" if i == 2 else "🥉"
                write_line(f"  {crown} {player}: {count} track(s)")
        else:
            write_line("  No world dedi's found this week")
        
        write_line()
        
        # 2. TIME MASTERS
        write_line("🕐 TIME MASTERS")
        write_line("-" * 40)
        
        if 'night_owl' in time_masters:
            write_line(f"🦉 Night Owl: {time_masters['night_owl']['player']} ({time_masters['night_owl']['count']} late-night dedi's, 0:00-6:00 EU)")
        
        if 'weekend_warrior' in time_masters:
            write_line(f"🕺 Saturday Night Fever: {time_masters['weekend_warrior']['player']} ({time_masters['weekend_warrior']['count']} weekend dedi's, {time_masters['weekend_warrior']['percentage']:.0f}%)")
        
        if 'binge_racer' in time_masters:
            date_obj = datetime.strptime(time_masters['binge_racer']['date'], '%Y-%m-%d')
            date_formatted = date_obj.strftime('%A, %b %d')
            write_line(f"🎮 Just One More: {time_masters['binge_racer']['player']} ({time_masters['binge_racer']['count']} dedi's on {date_formatted})")
        
        if 'daily_grinder' in time_masters:
            write_line(f"🔄 Creature of Habit: {time_masters['daily_grinder']['player']} (played {time_masters['daily_grinder']['days_played']}/7 days this week)")
        
        write_line()
        
        # 3. PERFORMANCE ELITE
        write_line("🏆 PERFORMANCE ELITE")
        write_line("-" * 40)
        
        if 'solo_explorer' in performance_elite:
            explorer = performance_elite['solo_explorer']
            write_line(f"🏝️ Solo Explorer: {explorer['player']} ({explorer['solo_tracks']} solo tracks - where they're the only player)")
        
        if 'lucky_number' in performance_elite:
            lucky = performance_elite['lucky_number']
            write_line(f"🍀 Lucky Number: {lucky['player']} (Rank 1 x {lucky['rank_1_count']} times)")
        
        if 'always_the_bridesmaid' in performance_elite:
            bridesmaid = performance_elite['always_the_bridesmaid']
            write_line(f"🥈 Always the Bridesmaid: {bridesmaid['player']} ({bridesmaid['rank_2_count']} second place finishes)")
        
        if 'third_times_the_charm' in performance_elite:
            third = performance_elite['third_times_the_charm']
            write_line(f"🥉 Third Time's the Charm: {third['player']} ({third['rank_3_count']} third place finishes)")
        
        write_line()
        
        # 4. MIXED BAG
        write_line("🎯 MIXED BAG")
        write_line("-" * 40)
        
        if 'no_lifer' in volume_champions:
            vol = volume_champions['no_lifer']
            write_line(f"👑 No-Lifer: {vol['player']} ({vol['total_dedi']} total dedi's)")
        
        if 'lolsport_addict' in lolsport_stats:
            lolsport = lolsport_stats['lolsport_addict']
            write_line(f"🏃 Lolsport Addict: {lolsport['player']} ({lolsport['lolsport_count']} lolsport dedi's)")
        
        # Server-specific stats use raw data
        server_stats = self.analyze_server_stats(raw_records)
        if 'minilol_champion' in server_stats:
            minilol = server_stats['minilol_champion']
            write_line(f"🏆 MiniLol FreeZone Champion: {minilol['player']} ({minilol['unique_tracks']} unique minilol tracks)")
        
        # Humorous stats use raw data (some need improvement tracking)
        humorous_stats = self.analyze_humorous_stats(raw_records)
        if 'benchwarmer' in humorous_stats:
            bench = humorous_stats['benchwarmer']
            write_line(f"🪑 The Benchwarmer: {bench['player']} ({bench['total_records']} dedi's total - where you at?)")
        
        if 'rage_quit_candidate' in humorous_stats:
            rage = humorous_stats['rage_quit_candidate']
            write_line(f"😤 Rage Quit Candidate: {rage['player']} ({rage['original_rank']} → {rage['final_rank']} on {rage['track'][:25]})")
        
        write_line()
        
        # 5. DETECTED RIVALRIES
        write_line("🔥 DETECTED RIVALRIES")
        write_line("-" * 40)
        
        # Rivalries use deduplicated data (head-to-head best records)
        rivalries = self.detect_rivalries(deduplicated_records)
        
        if rivalries:
            write_line("⚡ ONGOING RIVALRIES:")
            
            # Calculate maximum length for proper alignment
            max_winner_length = 0
            max_loser_length = 0
            for rivalry in rivalries[:10]:
                max_winner_length = max(max_winner_length, len(rivalry['player1']))
                max_loser_length = max(max_loser_length, len(rivalry['player2']))
            
            # Ensure minimum padding
            max_winner_length = max(max_winner_length, 15)
            max_loser_length = max(max_loser_length, 15)
            
            for rivalry in rivalries[:10]:  # Show top 10 rivalries instead of 5
                # Format: Winner (score) Loser - tracks
                winner = rivalry['player1']
                loser = rivalry['player2']
                score = f"({rivalry['score']})"
                tracks = f"{rivalry['shared_tracks']} shared tracks"
                
                if rivalry['leader'] != "Tied":
                    write_line(f"  🥊 {winner:<{max_winner_length}} {score:<8} {loser:<{max_loser_length}} - {tracks}")
                else:
                    write_line(f"  🥊 {winner:<{max_winner_length}} {score:<8} {loser:<{max_loser_length}} - {tracks} (Tied)")
        else:
            write_line("  No significant rivalries detected")
        
        write_line()
        
        # 6. FUN STATS & TRIVIA
        write_line("🎪 FUN STATS & TRIVIA")
        write_line("-" * 40)
        
        total_records = len(deduplicated_records)  # Unique track achievements
        unique_tracks = len(set(record[2] for record in deduplicated_records))  # Unique tracks with records
        unique_players = len(set(record[0] for record in deduplicated_records))  # Unique players with records
        
        write_line(f"📈 {total_records} total dedi's set this week")
        write_line(f"🏁 {unique_tracks} different tracks conquered")
        write_line(f"👥 {unique_players} players participated")
        
        # Most popular track
        track_popularity = Counter(record[2] for record in deduplicated_records)
        if track_popularity:
            hottest_track = track_popularity.most_common(1)[0]
            write_line(f"🔥 Hottest track: {hottest_track[0]} ({hottest_track[1]} dedi's)")
        
        write_line()
        write_line("=" * 60)
        write_line("🏁 Keep pushing those limits, team! See you next week!")
        write_line("=" * 60)
        
        # Save to file if requested
        if output_file:
            try:
                # Delete existing file if it exists
                if os.path.exists(output_file):
                    os.remove(output_file)
                    print(f"🗑️ Deleted existing file: {output_file}")
                
                # Create new file
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(output_lines))
                print(f"✅ Weekly report saved to: {output_file}")
            except Exception as e:
                print(f"❌ Error saving to file: {e}")
        
        return output_lines

    def generate_discord_summary(self, output_file=None):
        """Generate a condensed Discord-friendly version of the report"""
        # Create folder for this report
        folder = self.create_report_folder()
        
        if output_file:
            output_file = os.path.join(folder, os.path.basename(output_file))
        else:
            output_file = os.path.join(folder, 'weekly_stats_discord.txt')
        
        # Create output buffer
        output_lines = []
        
        def write_line(text=""):
            output_lines.append(text)
            if not output_file:
                print(text)
        
        # Get data
        raw_records = self.get_latest_data()
        
        if not raw_records:
            write_line("❌ No data available for this week")
            return output_lines
        
        # Deduplicate records for statistics that need unique track achievements
        deduplicated_records = self.deduplicate_records(raw_records)
        
        # Get analysis results
        time_masters = self.analyze_time_masters(raw_records)
        performance_elite = self.analyze_performance_elite(deduplicated_records)
        # Solo explorer analysis (most solo tracks)
        solo_explorer_results = self.analyze_solo_explorer(raw_records)
        performance_elite.update(solo_explorer_results)
        volume_champions = self.analyze_volume_champions(deduplicated_records)
        lolsport_stats = self.analyze_lolsport_addict(deduplicated_records)
        track_owners = self.analyze_track_ownership(deduplicated_records)
        
        write_line("🏁 **WEEKLY TRACKMANIA HIGHLIGHTS**")
        
        # Use consistent date range with main report
        start_date_str, end_date_str = get_weekly_date_range()
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        
        write_line(f"📅 {start_date.strftime('%b %d')} - {end_date.strftime('%b %d')}")
        write_line()
        
        # 🏆 CHAMPIONS OF THE WEEK
        write_line("🏆 **CHAMPIONS OF THE WEEK**")
        
        # Track King
        if track_owners:
            # Group by login for consistent counting, but use most recent nickname for display
            login_ownership = defaultdict(lambda: {'count': 0, 'nick': ''})
            for owner in track_owners.values():
                login = owner['login']
                login_ownership[login]['count'] += 1
                login_ownership[login]['nick'] = owner['owner']  # Keep most recent nickname
            
            # Find the top owner
            top_owner = max(login_ownership.values(), key=lambda x: x['count'])
            write_line(f"👑 **Track King:** {top_owner['nick']} ({top_owner['count']} WRs)")
        
        # No-Lifer
        if 'no_lifer' in volume_champions:
            write_line(f"📊 **No-Lifer:** {volume_champions['no_lifer']['player']} ({volume_champions['no_lifer']['total_dedi']} dedi's)")
        
        # Lolsport Addict
        if 'lolsport_addict' in lolsport_stats:
            lolsport = lolsport_stats['lolsport_addict']
            write_line(f"🏃 **Lolsport Addict:** {lolsport['player']} ({lolsport['lolsport_count']} lolsport dedi's)")
        
        # Server stats
        server_stats = self.analyze_server_stats(raw_records)
        if 'minilol_champion' in server_stats:
            minilol = server_stats['minilol_champion']
            write_line(f"🏆 **MiniLol Champion:** {minilol['player']} ({minilol['unique_tracks']} unique minilol tracks)")
        
        write_line()
        
        # 🎯 SPECIAL ACHIEVEMENTS
        write_line("🎯 **SPECIAL ACHIEVEMENTS**")
        
        if 'solo_explorer' in performance_elite:
            explorer = performance_elite['solo_explorer']
            write_line(f"🏝️ **Solo Explorer:** {explorer['player']} ({explorer['solo_tracks']} solo tracks - where they're the only player)")
        
        if 'night_owl' in time_masters and time_masters['night_owl']['count'] > 0:
            write_line(f"🦉 **Night Owl:** {time_masters['night_owl']['player']} ({time_masters['night_owl']['count']} late-night)")
        
        if 'weekend_warrior' in time_masters and time_masters['weekend_warrior']['count'] > 0:
            write_line(f"🕺 **Saturday Night Fever:** {time_masters['weekend_warrior']['player']} ({time_masters['weekend_warrior']['percentage']:.0f}% weekend)")
        
        if 'binge_racer' in time_masters and time_masters['binge_racer']['count'] > 0:
            write_line(f"🎮 **Just One More:** {time_masters['binge_racer']['player']} ({time_masters['binge_racer']['count']} in one day)")
        
        write_line()
        
        # 📈 QUICK STATS
        write_line("📈 **QUICK STATS**")
        total_records = len(deduplicated_records)  # Unique track achievements
        unique_tracks = len(set(record[2] for record in deduplicated_records))  # Unique tracks with records
        unique_players = len(set(record[0] for record in deduplicated_records))  # Unique players with records
        
        write_line(f"📊 {total_records} dedi's • {unique_tracks} tracks • {unique_players} players")
        
        # Most popular track
        track_popularity = Counter(record[2] for record in deduplicated_records)
        if track_popularity:
            hottest_track = track_popularity.most_common(1)[0]
            write_line(f"🔥 Hottest: {hottest_track[0][:25]} ({hottest_track[1]} dedi's)")
        
        write_line()
        write_line("📋 *Full detailed report available in weekly_stats.txt*")
        
        # Save to file if requested
        if output_file:
            try:
                if os.path.exists(output_file):
                    os.remove(output_file)
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(output_lines))
                print(f"✅ Discord summary saved to: {output_file}")
            except Exception as e:
                print(f"❌ Error saving summary: {e}")
        
        return output_lines
    
    def analyze_time_masters(self, records):
        """Analyze time-based patterns: Night Owl, Weekend Warrior, Binge Racer, Daily Grinder"""
        time_stats = {
            'night_owl': defaultdict(int),
            'weekend_warrior': defaultdict(int),
            'binge_racer': defaultdict(lambda: defaultdict(int)),
            'daily_grinder': defaultdict(lambda: set())
        }
        
        # Get latest nicknames for all logins
        player_nicks = self.get_all_latest_nicknames(records)
        
        for record in records:
            login, nick, track, time, rank, date, envir, mode, server = record
            
            try:
                # Parse date and time
                if ' ' in date:
                    date_part, time_part = date.split(' ', 1)
                    record_datetime = datetime.strptime(f"{date_part} {time_part}", '%Y-%m-%d %H:%M:%S')
                else:
                    record_datetime = datetime.strptime(date, '%Y-%m-%d')
                
                # Only count records within the weekly date range (Thursday to current day)
                start_date_str, end_date_str = get_weekly_date_range()
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                record_date = record_datetime.date()
                if not (start_date <= record_date <= end_date):
                    continue
                
                # Night Owl: 0:00 to 6:00 EU time
                if 0 <= record_datetime.hour <= 6:
                    time_stats['night_owl'][login] += 1
                
                # Weekend Warrior: Saturday (5) and Sunday (6)
                if record_datetime.weekday() in [5, 6]:
                    time_stats['weekend_warrior'][login] += 1
                
                # Binge Racer: records per day
                day_key = record_datetime.strftime('%Y-%m-%d')
                time_stats['binge_racer'][login][day_key] += 1
                
                # Daily Grinder: unique days played
                time_stats['daily_grinder'][login].add(day_key)
                
            except:
                continue
        
        # Process results
        results = {}
        
        # Night Owl
        if time_stats['night_owl']:
            best_night_owl = max(time_stats['night_owl'].items(), key=lambda x: x[1])
            results['night_owl'] = {
                'player': player_nicks.get(best_night_owl[0], best_night_owl[0]),
                'count': best_night_owl[1]
            }
        
        # Weekend Warrior
        if time_stats['weekend_warrior']:
            weekend_totals = []
            for login, weekend_count in time_stats['weekend_warrior'].items():
                total_records = sum(1 for r in records if r[0] == login)
                percentage = (weekend_count / total_records * 100) if total_records > 0 else 0
                weekend_totals.append((login, weekend_count, percentage))
            
            best_weekend = max(weekend_totals, key=lambda x: x[1])
            results['weekend_warrior'] = {
                'player': player_nicks.get(best_weekend[0], best_weekend[0]),
                'count': best_weekend[1],
                'percentage': best_weekend[2]
            }
        
        # Binge Racer
        best_binge = {'player': '', 'count': 0, 'date': '', 'percentage': 0}
        for login, daily_records in time_stats['binge_racer'].items():
            for day, count in daily_records.items():
                if count > best_binge['count']:
                    total_records = sum(1 for r in records if r[0] == login)
                    percentage = (count / total_records * 100) if total_records > 0 else 0
                    best_binge = {
                        'player': player_nicks.get(login, login),
                        'count': count,
                        'date': day,
                        'percentage': percentage
                    }
        
        if best_binge['count'] > 0:
            results['binge_racer'] = best_binge
        
        # Daily Grinder
        if time_stats['daily_grinder']:
            best_grinder = max(time_stats['daily_grinder'].items(), key=lambda x: len(x[1]))
            results['daily_grinder'] = {
                'player': player_nicks.get(best_grinder[0], best_grinder[0]),
                'days_played': len(best_grinder[1])
            }
        
        return results
    
    def analyze_performance_elite(self, records):
        """Analyze performance-based stats: Perfectionist, Consistency King, Quality over Quantity, etc."""
        player_stats = defaultdict(lambda: {
            'total_records': 0,
            'rank_1': 0,
            'rank_2': 0,
            'rank_3': 0,
            'top_3': 0,
            'ranks': [],
            'weighted_ranks': [],  # Ranks weighted by track competition
            'competitive_records': 0,  # Records on tracks with 3+ players
            'nick': ''
        })
        
        # Get latest nicknames for all logins
        latest_nicks = self.get_all_latest_nicknames(records)
        
        # Get challenge competition data
        challenge_cache = self.get_challenge_info_cache()
        
        for record in records:
            login, nick, track, time, rank, date, envir, mode, server = record
            
            try:
                rank_int = int(rank) if rank else 999
                player_stats[login]['total_records'] += 1
                player_stats[login]['nick'] = latest_nicks.get(login, login)
                player_stats[login]['ranks'].append(rank_int)
                
                # Get track competition level
                total_players = challenge_cache.get(track, 1)  # Default to 1 if unknown
                
                # Only include competitive tracks (3+ players) for Steady Eddie calculation
                if total_players >= 3:
                    player_stats[login]['competitive_records'] += 1
                    # Weight the rank by competition level (more competitive = more weight)
                    competition_weight = min(total_players / 10.0, 2.0)  # Cap at 2x weight for 10+ players
                    weighted_rank = rank_int / competition_weight
                    player_stats[login]['weighted_ranks'].append(weighted_rank)
                
                if rank_int == 1:
                    player_stats[login]['rank_1'] += 1
                elif rank_int == 2:
                    player_stats[login]['rank_2'] += 1
                elif rank_int == 3:
                    player_stats[login]['rank_3'] += 1
                
                if rank_int <= 3:
                    player_stats[login]['top_3'] += 1
                    
            except:
                continue
        
        results = {}
        
        # Steady Eddie: Weighted consistency score based on competitive tracks only
        steady_candidates = []
        
        # Calculate dynamic threshold based on competitive records (at least 3 competitive records)
        min_competitive_records = 3
        
        for login, stats in player_stats.items():
            # Only consider players with sufficient competitive records
            if stats['competitive_records'] >= min_competitive_records and stats['weighted_ranks']:
                # Calculate weighted average rank (better performance on more competitive tracks)
                weighted_avg_rank = sum(stats['weighted_ranks']) / len(stats['weighted_ranks'])
                

        
        # Lucky Number: Most rank 1s
        if player_stats:
            best_lucky = max(player_stats.items(), key=lambda x: x[1]['rank_1'])
            if best_lucky[1]['rank_1'] > 0:
                results['lucky_number'] = {
                    'player': best_lucky[1]['nick'],
                    'rank_1_count': best_lucky[1]['rank_1']
                }
        
        # Always the Bridesmaid: Most 2nd place finishes
        if player_stats:
            best_second = max(player_stats.items(), key=lambda x: x[1]['rank_2'])
            if best_second[1]['rank_2'] > 0:
                results['always_the_bridesmaid'] = {
                    'player': best_second[1]['nick'],
                    'rank_2_count': best_second[1]['rank_2']
                }
        
        # Third Time's the Charm: Most 3rd place finishes
        if player_stats:
            best_third = max(player_stats.items(), key=lambda x: x[1]['rank_3'])
            if best_third[1]['rank_3'] > 0:
                results['third_times_the_charm'] = {
                    'player': best_third[1]['nick'],
                    'rank_3_count': best_third[1]['rank_3']
                }
        
        return results
    

    
    def analyze_solo_explorer(self, records):
        """Find player who played the most solo tracks (tracks with only 1 total player)"""
        # Get challenge info cache for track populations
        challenge_cache = self.get_challenge_info_cache()
        
        # Get latest nicknames
        latest_nicks = self.get_all_latest_nicknames(records)
        
        # Group records by player and track (deduplicate)
        deduplicated_records = self.deduplicate_records(records)
        
        player_solo_tracks = defaultdict(set)
        
        for record in deduplicated_records:
            login, nick, track, time, rank, date, envir, mode, server = record
            
            # Check if this track has only 1 total player
            total_records = challenge_cache.get(track, 999)
            if total_records == 1:
                player_solo_tracks[login].add(track)
        
        if player_solo_tracks:
            # Find player with most solo tracks
            best_explorer = max(player_solo_tracks.items(), key=lambda x: len(x[1]))
            
            return {
                'solo_explorer': {
                    'player': latest_nicks.get(best_explorer[0], best_explorer[0]),
                    'solo_tracks': len(best_explorer[1]),
                    'track_list': list(best_explorer[1])
                }
            }
        
        return {}
    
    def analyze_volume_champions(self, records):
        """Analyze volume-based stats: Volume King, Spread Master"""
        player_stats = defaultdict(lambda: {
            'total_records': 0,
            'ranks': [],
            'nick': ''
        })
        
        # Get latest nicknames for all logins
        latest_nicks = self.get_all_latest_nicknames(records)
        
        for record in records:
            login, nick, track, time, rank, date, envir, mode, server = record
            
            try:
                rank_int = int(rank) if rank else 999
                player_stats[login]['total_records'] += 1
                player_stats[login]['nick'] = latest_nicks.get(login, login)
                player_stats[login]['ranks'].append(rank_int)
            except:
                continue
        
        results = {}
        
        # No-Lifer: Most total records
        if player_stats:
            best_volume = max(player_stats.items(), key=lambda x: x[1]['total_records'])
            results['no_lifer'] = {
                'player': best_volume[1]['nick'],
                'total_dedi': best_volume[1]['total_records']
            }
        
        return results
    
    def analyze_lolsport_addict(self, records):
        """Analyze lolsport-specific track records (deduplicated)"""
        player_stats = defaultdict(lambda: {
            'lolsport_records': 0,
            'nick': ''
        })
        
        # Get latest nicknames for all logins
        latest_nicks = self.get_all_latest_nicknames(records)
        
        for record in records:
            login, nick, track, time, rank, date, envir, mode, server = record
            
            # Check if track name contains "lolsport" (case insensitive)
            if 'lolsport' in track.lower():
                player_stats[login]['lolsport_records'] += 1
                player_stats[login]['nick'] = latest_nicks.get(login, login)
        
        results = {}
        
        # Find player with most lolsport records
        if player_stats:
            best_lolsport = max(player_stats.items(), key=lambda x: x[1]['lolsport_records'])
            if best_lolsport[1]['lolsport_records'] > 0:
                results['lolsport_addict'] = {
                    'player': best_lolsport[1]['nick'],
                    'lolsport_count': best_lolsport[1]['lolsport_records']
                }
        
        return results
    
    def analyze_humorous_stats(self, records):
        """Analyze humorous/fun statistics for entertainment"""
        results = {}
        
        # Get latest nicknames for all logins
        latest_nicks = self.get_all_latest_nicknames(records)
        
        # Group records by player
        player_data = defaultdict(lambda: {
            'records': [],
            'ranks': [],
            'times': [],
            'tracks': set(),
            'hours': set(),
            'nick': ''
        })
        
        for record in records:
            login, nick, track, time, rank, date, envir, mode, server = record
            player_data[login]['records'].append(record)
            player_data[login]['nick'] = latest_nicks.get(login, login)
            player_data[login]['tracks'].add(track)
            
            try:
                if rank:
                    player_data[login]['ranks'].append(int(rank))
                if time:
                    player_data[login]['times'].append(self.format_time(time))
                
                # Extract hour from date
                if ' ' in date:
                    hour = int(date.split(' ')[1].split(':')[0])
                    player_data[login]['hours'].add(hour)
            except:
                continue
        
        # The Benchwarmer - least active player (fewest UNIQUE tracks, with avg rank tiebreaker)
        if player_data:
            # Find minimum number of unique tracks
            min_tracks = min(len(data['tracks']) for data in player_data.values())
            
            # Find all players tied for fewest tracks
            tied_players = [(login, data) for login, data in player_data.items() 
                           if len(data['tracks']) == min_tracks]
            
            # If multiple players tied, use average rank as tiebreaker (higher avg rank = worse performance)
            if len(tied_players) > 1:
                def get_avg_rank(login_data):
                    login, data = login_data
                    if data['ranks']:
                        return sum(data['ranks']) / len(data['ranks'])
                    return 999  # Default high rank for players with no ranks
                
                benchwarmer = max(tied_players, key=get_avg_rank)  # Max because higher rank = worse
            else:
                benchwarmer = tied_players[0]
            
            results['benchwarmer'] = {
                'player': benchwarmer[1]['nick'],
                'total_records': len(benchwarmer[1]['tracks'])  # Count unique tracks, not total records
            }
        
        # Rage Quit Candidate - biggest rank drop between attempts on same track
        rage_quit_candidates = []
        for login, data in player_data.items():
            track_records = defaultdict(list)
            for record in data['records']:
                track_records[record[2]].append(record)
            
            max_drop = 0
            worst_track = ""
            original_rank = 0
            final_rank = 0
            for track, track_recs in track_records.items():
                if len(track_recs) >= 2:
                    # Sort by date
                    track_recs.sort(key=lambda x: x[5])
                    for i in range(len(track_recs) - 1):
                        try:
                            rank1 = int(track_recs[i][4]) if track_recs[i][4] else 999
                            rank2 = int(track_recs[i+1][4]) if track_recs[i+1][4] else 999
                            drop = rank2 - rank1
                            if drop > max_drop:
                                max_drop = drop
                                worst_track = track
                                original_rank = rank1
                                final_rank = rank2
                        except:
                            continue
            
            if max_drop > 0:
                rage_quit_candidates.append((login, data, max_drop, worst_track, original_rank, final_rank))
        
        if rage_quit_candidates:
            rage_quitter = max(rage_quit_candidates, key=lambda x: x[2])
            results['rage_quit_candidate'] = {
                'player': rage_quitter[1]['nick'],
                'rank_drop': rage_quitter[2],
                'track': rage_quitter[3],
                'original_rank': rage_quitter[4],
                'final_rank': rage_quitter[5]
            }
        
        # Keep caffeine addict for Part 1 (Time Masters)
        caffeine_candidates = []
        for login, data in player_data.items():
            if data['hours']:
                caffeine_candidates.append((login, data, len(data['hours'])))
        
        if caffeine_candidates:
            best_caffeine = max(caffeine_candidates, key=lambda x: x[2])
            results['caffeine_addict'] = {
                'player': best_caffeine[1]['nick'],
                'hours': best_caffeine[2],
                'total_records': len(best_caffeine[1]['records'])
            }
        

        
        return results
    
    def analyze_server_stats(self, records):
        """Analyze server-specific statistics"""
        results = {}
        
        # Get latest nicknames for all logins
        latest_nicks = self.get_all_latest_nicknames(records)
        
        # First, identify which tracks are "minilol tracks" from database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        minilol_server_names = [
            'minilol_freezone', 'minilol_freezone.', 'minilol freezone',
            'Mini Lol FreeZone', 'MiniLol FreeZone', 'MINILOL_FREEZONE'
        ]
        
        # Find all tracks that have ever been on minilol servers
        minilol_tracks = set()
        for variant in minilol_server_names:
            cursor.execute("""
                SELECT DISTINCT Challenge 
                FROM dedimania_records 
                WHERE server LIKE ?
            """, (f"%{variant}%",))
            
            for row in cursor.fetchall():
                minilol_tracks.add(row[0])
        
        conn.close()
        
        # Now count unique minilol tracks played by each player (regardless of server played on)
        minilol_records = defaultdict(set)
        
        for record in records:
            login, nick, track, time, rank, date, envir, mode, server = record
            # If this track is a minilol track, count it regardless of which server it was played on
            if track in minilol_tracks:
                minilol_records[login].add(track)
        
        if minilol_records:
            # Convert sets to counts and find the player with most unique minilol tracks
            minilol_counts = {login: len(track_set) for login, track_set in minilol_records.items()}
            best_minilol = max(minilol_counts.items(), key=lambda x: x[1])
            results['minilol_champion'] = {
                'player': latest_nicks.get(best_minilol[0], best_minilol[0]),
                'unique_tracks': best_minilol[1]  # Unique minilol tracks played this week
            }
        
        return results
    
    def print_minilol_champion_details(self):
        """Print detailed breakdown of MiniLol Champion's performance"""
        print("\n" + "="*80)
        print("🏆 MINILOL CHAMPION DETAILED ANALYSIS")
        print("="*80)
        
        # Get data
        raw_records = self.get_latest_data()
        if not raw_records:
            print("❌ No data available")
            return
        
        # Get date range
        start_date, end_date = get_weekly_date_range()
        print(f"📅 Analyzing period: {start_date} to {end_date}")
        print()
        
        # Identify minilol tracks from database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        minilol_server_names = [
            'minilol_freezone', 'minilol_freezone.', 'minilol freezone',
            'Mini Lol FreeZone', 'MiniLol FreeZone', 'MINILOL_FREEZONE'
        ]
        
        # Find all tracks that have ever been on minilol servers
        minilol_tracks = set()
        print("🔍 IDENTIFYING MINILOL TRACKS FROM DATABASE:")
        print("-" * 50)
        
        for variant in minilol_server_names:
            cursor.execute("""
                SELECT DISTINCT Challenge 
                FROM dedimania_records 
                WHERE server LIKE ?
            """, (f"%{variant}%",))
            
            tracks_found = [row[0] for row in cursor.fetchall()]
            for track in tracks_found:
                minilol_tracks.add(track)
        
        conn.close()
        
        print(f"Found {len(minilol_tracks)} unique minilol tracks in database")
        for track in sorted(minilol_tracks)[:10]:  # Show first 10
            print(f"  • {track}")
        if len(minilol_tracks) > 10:
            print(f"  ... and {len(minilol_tracks) - 10} more")
        print()
        
        # Count unique minilol tracks played by each player this week
        from collections import defaultdict
        minilol_records = defaultdict(list)
        latest_nicks = self.get_all_latest_nicknames(raw_records)
        
        for record in raw_records:
            login, nick, track, time, rank, date, envir, mode, server = record
            # If this track is a minilol track, count it regardless of which server it was played on
            if track in minilol_tracks:
                minilol_records[login].append({
                    'track': track,
                    'nick': latest_nicks.get(login, login),
                    'time': time,
                    'rank': rank,
                    'date': date,
                    'server': server or 'Unknown',
                    'envir': envir,
                    'mode': mode
                })
        
        # Find champion (player with most unique minilol tracks)
        champion_login = None
        max_unique_tracks = 0
        
        for login, records in minilol_records.items():
            # Count unique tracks the same way we'll display them (exclude records with invalid data)
            valid_tracks = set()
            for record in records:
                try:
                    int(record['rank'])  # Test if rank is valid
                    valid_tracks.add(record['track'])
                except:
                    continue  # Skip records with invalid rank data
            
            unique_tracks = len(valid_tracks)
            if unique_tracks > max_unique_tracks:
                max_unique_tracks = unique_tracks
                champion_login = login
        
        if not champion_login:
            print("❌ No minilol champion found this week")
            return
        
        champion_records = minilol_records[champion_login]
        champion_nick = latest_nicks.get(champion_login, champion_login)
        
        print(f"🏆 MINILOL CHAMPION: {champion_nick} ({champion_login})")
        print(f"📊 Unique minilol tracks played: {max_unique_tracks}")

        print("=" * 80)
        print()
        
        # Group by unique tracks (deduplicate improvements)
        track_records = {}
        excluded_tracks = []
        
        for record in champion_records:
            track = record['track']
            rank_value = record['rank']
            
            try:
                int(rank_value)  # Test if rank is valid
                if track not in track_records:
                    track_records[track] = record
                else:
                    # Keep the best rank (lowest number)
                    if int(rank_value) < int(track_records[track]['rank']):
                        track_records[track] = record
            except:
                excluded_tracks.append((track, rank_value))
                continue
        
        # Show excluded tracks if any
        if excluded_tracks:
            print(f"⚠️  EXCLUDED TRACKS (invalid rank data):")
            for track, rank in excluded_tracks:
                print(f"  • {track} (rank: '{rank}')")
            print()
        
        print(f"📋 DETAILED BREAKDOWN ({len(track_records)} unique tracks):")
        print("-" * 80)
        print(f"{'Track':<35} {'Server':<20} {'Rank':<6} {'Time':<12} {'Date':<12}")
        print("-" * 80)
        
        all_tracks_output = []
        for track, record in sorted(track_records.items()):
            track_short = track[:33] + '..' if len(track) > 35 else track
            server_short = record['server'][:18] + '..' if len(record['server']) > 20 else record['server']
            
            line = f"{track_short:<35} {server_short:<20} #{record['rank']:<5} {record['time']:<12} {record['date'][:10]}"
            print(line)
            all_tracks_output.append(line)
        
        # Also save to file to ensure we can see all tracks
        with open('minilol_champion_full_details.txt', 'w', encoding='utf-8') as f:
            f.write(f"MINILOL CHAMPION: {champion_nick} ({champion_login})\n")
            f.write(f"Unique minilol tracks played: {max_unique_tracks}\n\n")
            f.write(f"DETAILED BREAKDOWN ({len(track_records)} unique tracks):\n")
            f.write("-" * 80 + "\n")
            f.write(f"{'Track':<35} {'Server':<20} {'Rank':<6} {'Time':<12} {'Date':<12}\n")
            f.write("-" * 80 + "\n")
            for line in all_tracks_output:
                f.write(line + "\n")
        
        print(f"\n📁 Full details saved to: minilol_champion_full_details.txt")
        
        print()
        print("🔍 VERIFICATION:")
        print(f"• Total minilol tracks in database: {len(minilol_tracks)}")
        print(f"• Champion played: {len(track_records)} unique minilol dedis")
        print(f"• Champion's coverage: {len(track_records)/len(minilol_tracks)*100:.1f}% of all minilol tracks")
        print("="*80)
    
    def generate_rivalry_heatmap(self, output_file='weekly_rivalry_heatmap.png'):
        """Generate a focused rivalry heatmap and weekly pulse visualization"""
        from PIL import Image, ImageDraw, ImageFont
        
        # Create folder for this report
        folder = self.create_report_folder()
        
        if output_file:
            output_file = os.path.join(folder, os.path.basename(output_file))
        else:
            output_file = os.path.join(folder, 'weekly_rivalry_heatmap.png')
        
        # Get data
        records = self.get_latest_data()
        
        if not records:
            print("❌ No data available for generating rivalry heatmap")
            return
        
        # Get analysis results
        deduplicated_records = self.deduplicate_records(records)
        rivalries = self.detect_rivalries(deduplicated_records)
        
        # Image dimensions and setup - make it taller for more rivalries
        width = 1200
        height = 850  # Reduced height since we're removing content
        
        # Create image with dark background for heat map effect
        img = Image.new('RGB', (width, height), (25, 25, 35))
        draw = ImageDraw.Draw(img)
        
        # Load fonts with better sizing
        try:
            font_title = ImageFont.truetype("DejaVuSans-Bold.ttf", 36)  # Smaller title
            font_heading = ImageFont.truetype("DejaVuSans-Bold.ttf", 34)
            font_text = ImageFont.truetype("DejaVuSans-Bold.ttf", 20)
            font_large = ImageFont.truetype("DejaVuSans-Bold.ttf", 30)  # Slightly smaller for cards
            font_medium = ImageFont.truetype("DejaVuSans-Bold.ttf", 24)
            font_small = ImageFont.truetype("DejaVuSans-Bold.ttf", 15)  # Smaller labels
            font_player_names = ImageFont.truetype("DejaVuSans-Bold.ttf", 22)  # Larger bold font for player names
        except:
            try:
                font_title = ImageFont.truetype("arialbd.ttf", 36)
                font_heading = ImageFont.truetype("arialbd.ttf", 34)
                font_text = ImageFont.truetype("arialbd.ttf", 20)
                font_large = ImageFont.truetype("arialbd.ttf", 30)
                font_medium = ImageFont.truetype("arialbd.ttf", 24)
                font_small = ImageFont.truetype("arialbd.ttf", 15)
                font_player_names = ImageFont.truetype("arialbd.ttf", 22)  # Larger bold font for player names
            except:
                font_title = ImageFont.load_default()
                font_heading = ImageFont.load_default()
                font_text = ImageFont.load_default()
                font_large = ImageFont.load_default()
                font_medium = ImageFont.load_default()
                font_small = ImageFont.load_default()
                font_player_names = ImageFont.load_default()
        
        # Enhanced colors for heat map theme
        colors = {
            'title': (255, 255, 255),
            'heading': (255, 255, 255),
            'text': (220, 220, 220),
            'accent': (255, 100, 100),      # Red for heat/world records
            'secondary': (100, 150, 255),   # Blue for tracks/cool stats
            'success': (100, 255, 150),     # Green for volume/success
            'warning': (255, 200, 100),     # Yellow for highlights/players
            'purple': (180, 100, 255),      # Purple for special stats
            'cyan': (100, 255, 255),        # Cyan for activity
            'bar_bg': (45, 45, 55),         # Lighter bar background
            'card_bg': (35, 35, 45),        # Slightly lighter card background
        }
        
        # Helper function to draw rounded rectangles
        def draw_rounded_rectangle(draw_obj, coords, fill, outline=None, radius=8):
            x1, y1, x2, y2 = coords[0][0], coords[0][1], coords[1][0], coords[1][1]
            
            # Ensure coordinates are valid
            if x1 > x2:
                x1, x2 = x2, x1
            if y1 > y2:
                y1, y2 = y2, y1
            
            # Ensure minimum size
            if x2 - x1 < 2 * radius:
                radius = max(1, (x2 - x1) // 2)
            if y2 - y1 < 2 * radius:
                radius = max(1, (y2 - y1) // 2)
            
            # Draw main rectangle
            if x2 - x1 > 2 * radius:
                draw_obj.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
            if y2 - y1 > 2 * radius:
                draw_obj.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)
            
            # Draw corners only if there's enough space
            if x2 - x1 >= 2 * radius and y2 - y1 >= 2 * radius:
                draw_obj.pieslice([x1, y1, x1 + 2*radius, y1 + 2*radius], 180, 270, fill=fill)
                draw_obj.pieslice([x2 - 2*radius, y1, x2, y1 + 2*radius], 270, 360, fill=fill)
                draw_obj.pieslice([x1, y2 - 2*radius, x1 + 2*radius, y2], 90, 180, fill=fill)
                draw_obj.pieslice([x2 - 2*radius, y2 - 2*radius, x2, y2], 0, 90, fill=fill)
            
            # Draw outline if specified
            if outline:
                draw_obj.rectangle([x1, y1, x2, y2], outline=outline, width=1)
        
        y = 20
        
        # Title with ĊĦ Team prefix
        title_text = "ĊĦ Team — Weekly Rivalries & Pulse"
        title_bbox = draw.textbbox((0, 0), title_text, font=font_title)
        title_width = title_bbox[2] - title_bbox[0]
        title_x = (width - title_width) // 2
        draw.text((title_x, y), title_text, fill=colors['title'], font=font_title)
        
        y += 55
        
        # RIVALRY HEAT MAP Section
        if rivalries:
            # Add section heading
            heading_text = "TOP RIVALRIES (SHARED TRACKS)"
            draw.text((70, y), heading_text, fill=colors['heading'], font=font_text)
            y += 35
            # Show top 15 rivalries with visual heat bars (increased from 12)
            max_shared_tracks = max(rivalry['shared_tracks'] for rivalry in rivalries[:15]) if rivalries else 1
            
            for i, rivalry in enumerate(rivalries[:15]):
                # Calculate bar intensity based on shared tracks
                intensity = rivalry['shared_tracks'] / max_shared_tracks
                
                # Heat color based on intensity - improved gradient
                heat_red = min(255, int(80 + (intensity * 175)))
                heat_green = max(40, int(120 - (intensity * 80)))
                heat_blue = max(40, int(80 - (intensity * 40)))
                heat_color = (heat_red, heat_green, heat_blue)
                
                # Draw rivalry bar - slightly smaller spacing
                bar_y = y + (i * 40)
                bar_height = 32
                
                # Background bar
                draw_rounded_rectangle(draw, [(70, bar_y), (width - 70, bar_y + bar_height)], 
                                     fill=colors['bar_bg'], radius=6)
                
                # Bar length based on winner dominance percentage
                winner_wins = rivalry['p1_wins']
                total_battles = winner_wins + rivalry['p2_wins']
                dominance_ratio = winner_wins / total_battles if total_battles > 0 else 0.5
                
                bar_width = int((width - 140) * dominance_ratio)
                if bar_width > 0:
                    draw_rounded_rectangle(draw, [(70, bar_y), (70 + bar_width, bar_y + bar_height)], 
                                         fill=heat_color, radius=6)
                
                # Winner | Score | Loser with fixed column alignment
                winner = rivalry['player1']
                loser = rivalry['player2']
                score_text = f"({rivalry['score']})"
                tracks_text = f"{rivalry['shared_tracks']} tracks"
                
                # Fixed positions for perfect column alignment
                winner_x = 90
                score_x = 460  # Fixed center position for scores
                loser_x = 630  # Moved further right for better spacing
                tracks_x = width - 100
                
                # Center the score text around the fixed position
                score_bbox = draw.textbbox((0, 0), score_text, font=font_text)
                score_width = score_bbox[2] - score_bbox[0]
                score_centered_x = score_x - (score_width // 2)
                
                # Draw elements with brighter colors
                draw.text((winner_x, bar_y + 6), winner, fill=(255, 255, 255), font=font_player_names)  # Bright white, larger bold
                draw.text((score_centered_x, bar_y + 6), score_text, fill=(255, 255, 100), font=font_text)  # Bright yellow
                draw.text((loser_x, bar_y + 6), loser, fill=(255, 255, 255), font=font_player_names)  # Bright white, larger bold
                draw.text((tracks_x, bar_y + 6), tracks_text, fill=colors['secondary'], font=font_text)
            
            y += (len(rivalries[:15]) * 40) + 40
        
        # Weekly Pulse Section (no heading)
        
        # Calculate stats
        total_records = len(deduplicated_records)
        unique_tracks = len(set(record[2] for record in deduplicated_records))
        unique_players = len(set(record[0] for record in deduplicated_records))
        
        # Calculate additional stats
        top1_records = len([r for r in deduplicated_records if r[4] == '1'])
        top5_records = len([r for r in deduplicated_records if r[4] and r[4].isdigit() and int(r[4]) <= 5])
        
        top1_percentage = (top1_records / len(deduplicated_records) * 100) if len(deduplicated_records) > 0 else 0
        top5_percentage = (top5_records / len(deduplicated_records) * 100) if len(deduplicated_records) > 0 else 0
        
        # 5 stat cards in one row (reordered as requested)
        stats = [
            ("ACTIVE PLAYERS", str(unique_players), colors['warning']),
            ("TRACKS PLAYED", str(unique_tracks), colors['secondary']),
            ("TOTAL DEDI'S", str(total_records), colors['success']),
            ("WORLD RECORDS", f"{top1_records} ({top1_percentage:.1f}%)", colors['accent']),
            ("TOP 5 RECORDS", f"{top5_records} ({top5_percentage:.1f}%)", colors['success'])
        ]
        
        # Single row layout for 5 cards
        card_width = 200
        card_height = 85
        cards_per_row = 5
        card_spacing_x = 220  # Spacing between cards
        start_x = (width - (cards_per_row * card_spacing_x - 20)) // 2
        
        for i, (label, value, color) in enumerate(stats):
            card_x = start_x + (i * card_spacing_x)
            card_y = y
            
            # Draw card background with subtle shadow effect
            shadow_offset = 3
            draw_rounded_rectangle(draw, [(card_x + shadow_offset, card_y + shadow_offset), 
                                        (card_x + card_width + shadow_offset, card_y + card_height + shadow_offset)], 
                                 fill=(15, 15, 20), radius=10)
            
            # Draw main card
            draw_rounded_rectangle(draw, [(card_x, card_y), (card_x + card_width, card_y + card_height)], 
                                 fill=colors['card_bg'], radius=10)
            
            # Draw accent stripe - thicker
            draw_rounded_rectangle(draw, [(card_x, card_y), (card_x + card_width, card_y + 12)], 
                                 fill=color, radius=10)
            
            # Draw value (large and bold)
            value_bbox = draw.textbbox((0, 0), value, font=font_large)
            value_width = value_bbox[2] - value_bbox[0]
            value_x = card_x + (card_width - value_width) // 2
            draw.text((value_x, card_y + 18), value, fill=colors['title'], font=font_large)
            
            # Draw label (small size)
            label_bbox = draw.textbbox((0, 0), label, font=font_small)
            label_width = label_bbox[2] - label_bbox[0]
            label_x = card_x + (card_width - label_width) // 2
            draw.text((label_x, card_y + 62), label, fill=colors['text'], font=font_small)
        
        # Save image
        try:
            if os.path.exists(output_file):
                os.remove(output_file)
            img.save(output_file, 'PNG', quality=95)
            print(f"✅ Rivalry heatmap saved to: {output_file}")
        except Exception as e:
            print(f"❌ Error saving rivalry heatmap: {e}")
        
        return output_file
    
    def generate_image_report(self, output_file='weekly_highlights.png'):
        """Generate all parts of the weekly image report"""
        # Create folder for this report
        folder = self.create_report_folder()
        
        # Update output file paths to be in the folder
        if output_file:
            base_name = os.path.splitext(os.path.basename(output_file))[0]
            part1_file = os.path.join(folder, f"{base_name}_part1.png")
            part2_file = os.path.join(folder, f"{base_name}_part2.png")
            heatmap_file = os.path.join(folder, f"{base_name}_heatmap.png")
            dashboard_file = os.path.join(folder, f"{base_name}_dashboard.png")
        else:
            part1_file = os.path.join(folder, 'weekly_highlights_part1.png')
            part2_file = os.path.join(folder, 'weekly_highlights_part2.png')
            heatmap_file = os.path.join(folder, 'weekly_highlights_heatmap.png')
            dashboard_file = os.path.join(folder, 'weekly_highlights_dashboard.png')
        
        part1 = self.generate_image_part1(part1_file)
        part2 = self.generate_image_part2(part2_file)
        heatmap = self.generate_rivalry_heatmap(heatmap_file)
        dashboard = self.generate_achievement_dashboard(dashboard_file)
        return [part1, part2, heatmap, dashboard]
    
    def generate_image_part1(self, output_file='weekly_highlights_part1.png'):
        """Generate Part 1: Champions & Performance"""
        from PIL import Image, ImageDraw, ImageFont
        
        # Get data
        raw_records = self.get_latest_data()
        
        if not raw_records:
            print("❌ No data available for generating image")
            return
        
        # Deduplicate records for performance and volume stats
        deduplicated_records = self.deduplicate_records(raw_records)
        
        # Get analysis results
        time_masters = self.analyze_time_masters(raw_records)
        performance_elite = self.analyze_performance_elite(deduplicated_records)
        # Solo explorer analysis (most solo tracks)
        solo_explorer_results = self.analyze_solo_explorer(raw_records)
        performance_elite.update(solo_explorer_results)
        volume_champions = self.analyze_volume_champions(deduplicated_records)
        lolsport_stats = self.analyze_lolsport_addict(deduplicated_records)
        
        # Image dimensions and setup
        width = 1200
        height = 1400  # Shorter height for part 1
        
        # Create image with light background
        img = Image.new('RGB', (width, height), (245, 245, 250))
        draw = ImageDraw.Draw(img)
        
        # Load fonts - bold and prominent like reference
        try:
            font_title = ImageFont.truetype("DejaVuSans-Bold.ttf", 50)
            font_heading = ImageFont.truetype("DejaVuSans-Bold.ttf", 36)
            font_subheading = ImageFont.truetype("DejaVuSans-Bold.ttf", 28)
            font_text = ImageFont.truetype("DejaVuSans-Bold.ttf", 24)
            font_small = ImageFont.truetype("DejaVuSans-Bold.ttf", 20)
        except:
            try:
                font_title = ImageFont.truetype("arialbd.ttf", 50)
                font_heading = ImageFont.truetype("arialbd.ttf", 36)
                font_subheading = ImageFont.truetype("arialbd.ttf", 28)
                font_text = ImageFont.truetype("arialbd.ttf", 24)
                font_small = ImageFont.truetype("arialbd.ttf", 20)
            except:
                font_title = ImageFont.load_default()
                font_heading = ImageFont.load_default()
                font_subheading = ImageFont.load_default()
                font_text = ImageFont.load_default()
                font_small = ImageFont.load_default()
        
        # Colors matching the reference image exactly
        colors = {
            'header_bg': (49, 68, 119),          # Dark blue header
            'orange_stripe': (255, 165, 0),      # Orange accent stripe
            'title_text': (255, 255, 255),       # White title text
            'activity_patterns': (0, 150, 136),  # Modern teal
            'performance': (255, 140, 0),        # Orange  
            'volume': (60, 179, 113),           # Green
            'general': (100, 100, 100),         # Gray
            'text': (40, 40, 40),               # Dark text
            'header_text': (255, 255, 255),     # White section headers
            'section_title': (70, 130, 180),    # Blue section titles
        }
        
        y = 0
        
        # Create ĊĦ Team header like reference image
        header_height = 85
        # Dark blue background
        draw.rectangle([(0, 0), (width, header_height)], fill=colors['header_bg'])
        # Orange accent stripe
        draw.rectangle([(0, header_height-8), (width, header_height)], fill=colors['orange_stripe'])
        
        # ĊĦ Team title
        title_text = "ĊĦ Team — Weekly Highlights"
        title_bbox = draw.textbbox((0, 0), title_text, font=font_title)
        title_width = title_bbox[2] - title_bbox[0]
        title_x = (width - title_width) // 2
        draw.text((title_x, 20), title_text, fill=colors['title_text'], font=font_title)
        
        y = header_height + 30
        
        # Helper function to draw rounded rectangles
        def draw_rounded_rectangle(draw_obj, coords, fill, radius=8):
            x1, y1, x2, y2 = coords[0][0], coords[0][1], coords[1][0], coords[1][1]
            
            # Draw main rectangle
            draw_obj.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
            draw_obj.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)
            
            # Draw corners
            draw_obj.pieslice([x1, y1, x1 + 2*radius, y1 + 2*radius], 180, 270, fill=fill)
            draw_obj.pieslice([x2 - 2*radius, y1, x2, y1 + 2*radius], 270, 360, fill=fill)
            draw_obj.pieslice([x1, y2 - 2*radius, x1 + 2*radius, y2], 90, 180, fill=fill)
            draw_obj.pieslice([x2 - 2*radius, y2 - 2*radius, x2, y2], 0, 90, fill=fill)
        
        # Helper function to draw section with perfect alignment
        def draw_section_aligned(title, items, bg_color, text_color, y_pos):
            # Section title with colored background (like reference)
            title_height = 50
            draw_rounded_rectangle(draw, [(40, y_pos), (width-40, y_pos + title_height)], fill=text_color, radius=12)
            draw.text((60, y_pos + 14), title, fill=colors['header_text'], font=font_heading)
            y_pos += title_height + 15
            
            # Calculate maximum pixel width for proper alignment
            max_prefix_width = 0
            max_player_width = 0
            
            for item in items:
                if item['type'] == 'aligned':
                    # Calculate prefix width (e.g., "• Night Owl: ")
                    prefix_bbox = draw.textbbox((0, 0), item['prefix'], font=font_text)
                    prefix_width = prefix_bbox[2] - prefix_bbox[0]
                    max_prefix_width = max(max_prefix_width, prefix_width)
                    
                    # Calculate player name width
                    player_bbox = draw.textbbox((0, 0), item['player'], font=font_text)
                    player_width = player_bbox[2] - player_bbox[0]
                    max_player_width = max(max_player_width, player_width)
            
            # Add padding
            max_prefix_width += 20
            max_player_width += 20
            
            # Draw items with perfect alignment
            for item in items:
                item_height = 40
                # Create rounded rectangle for each item (like reference)
                draw_rounded_rectangle(draw, [(60, y_pos), (width-60, y_pos + item_height)], fill=bg_color, radius=10)
                
                if item['type'] == 'aligned':
                    # Draw prefix at standard position
                    draw.text((80, y_pos + 12), item['prefix'], fill=colors['text'], font=font_text)
                    # Draw player name at calculated position
                    player_x = 80 + max_prefix_width
                    draw.text((player_x, y_pos + 12), item['player'], fill=colors['text'], font=font_text)
                    # Draw details at calculated position
                    details_x = player_x + max_player_width
                    draw.text((details_x, y_pos + 12), item['details'], fill=colors['text'], font=font_text)
                else:
                    # Fallback to regular text
                    draw.text((80, y_pos + 12), item['text'], fill=colors['text'], font=font_text)
                
                y_pos += item_height + 8
            
            return y_pos + 30
        
        # TIME MASTERS Section
        time_items = []
        if 'night_owl' in time_masters:
            time_items.append({
                'type': 'aligned',
                'prefix': '• Night Owl: ',
                'player': time_masters['night_owl']['player'],
                'details': f"({time_masters['night_owl']['count']} late-night dedi's, 0:00-6:00 EU)"
            })
        if 'weekend_warrior' in time_masters:
            time_items.append({
                'type': 'aligned',
                'prefix': '• Saturday Night Fever: ',
                'player': time_masters['weekend_warrior']['player'],
                'details': f"({time_masters['weekend_warrior']['count']} weekend dedi's, {time_masters['weekend_warrior']['percentage']:.0f}%)"
            })
        if 'binge_racer' in time_masters:
            date_obj = datetime.strptime(time_masters['binge_racer']['date'], '%Y-%m-%d')
            date_formatted = date_obj.strftime('%A, %b %d')
            time_items.append({
                'type': 'aligned',
                'prefix': '• Just One More: ',
                'player': time_masters['binge_racer']['player'],
                'details': f"({time_masters['binge_racer']['count']} dedi's on {date_formatted})"
            })
        if 'daily_grinder' in time_masters:
            time_items.append({
                'type': 'aligned',
                'prefix': '• Creature of Habit: ',
                'player': time_masters['daily_grinder']['player'],
                'details': f"(played {time_masters['daily_grinder']['days_played']}/7 days this week)"
            })
        
        # Add Caffeine Addict from humorous stats
        # Humorous stats use raw data (some need improvement tracking)
        humorous_stats = self.analyze_humorous_stats(raw_records)
        if 'caffeine_addict' in humorous_stats:
            caffeine = humorous_stats['caffeine_addict']
            time_items.append({
                'type': 'aligned',
                'prefix': '• Caffeine Addict: ',
                'player': caffeine['player'],
                'details': f"(active {caffeine['hours']} different hours)"
            })
        
        if time_items:
            y = draw_section_aligned("Activity Patterns", time_items, colors['activity_patterns'], colors['activity_patterns'], y)
        
        # PERFORMANCE ELITE Section
        perf_items = []
        if 'solo_explorer' in performance_elite:
            explorer = performance_elite['solo_explorer']
            perf_items.append({
                'type': 'aligned',
                'prefix': '• Solo Explorer: ',
                'player': explorer['player'],
                'details': f"({explorer['solo_tracks']} solo tracks)"
            })
        if 'lucky_number' in performance_elite:
            lucky = performance_elite['lucky_number']
            perf_items.append({
                'type': 'aligned',
                'prefix': '• Lucky Number: ',
                'player': lucky['player'],
                'details': f"(Rank 1 x {lucky['rank_1_count']} times)"
            })
        if 'always_the_bridesmaid' in performance_elite:
            bridesmaid = performance_elite['always_the_bridesmaid']
            perf_items.append({
                'type': 'aligned',
                'prefix': '• Always the Bridesmaid: ',
                'player': bridesmaid['player'],
                'details': f"({bridesmaid['rank_2_count']} second place finishes)"
            })
        if 'third_times_the_charm' in performance_elite:
            third = performance_elite['third_times_the_charm']
            perf_items.append({
                'type': 'aligned',
                'prefix': '• Third Time\'s the Charm: ',
                'player': third['player'],
                'details': f"({third['rank_3_count']} third place finishes)"
            })
        
        if perf_items:
            y = draw_section_aligned("Performance Elite", perf_items, colors['performance'], colors['performance'], y)
        
        # MIXED BAG Section
        mixed_items = []
        if 'no_lifer' in volume_champions:
            vol = volume_champions['no_lifer']
            mixed_items.append({
                'type': 'aligned',
                'prefix': '• No-Lifer: ',
                'player': vol['player'],
                'details': f"({vol['total_dedi']} total dedi's)"
            })
        
        if 'lolsport_addict' in lolsport_stats:
            lolsport = lolsport_stats['lolsport_addict']
            mixed_items.append({
                'type': 'aligned',
                'prefix': '• Lolsport Addict: ',
                'player': lolsport['player'],
                'details': f"({lolsport['lolsport_count']} lolsport dedi's)"
            })
        
        # Add humorous stats from Image 3
        if 'benchwarmer' in humorous_stats:
            bench = humorous_stats['benchwarmer']
            mixed_items.append({
                'type': 'aligned',
                'prefix': '• The Benchwarmer: ',
                'player': bench['player'],
                'details': f"({bench['total_records']} dedi's total - where you at?)"
            })
        
        if 'rage_quit_candidate' in humorous_stats:
            rage = humorous_stats['rage_quit_candidate']
            mixed_items.append({
                'type': 'aligned',
                'prefix': '• Rage Quit Candidate: ',
                'player': rage['player'],
                'details': f"({rage['original_rank']} → {rage['final_rank']} on {rage['track'][:25]})"
            })
        
        if mixed_items:
            y = draw_section_aligned("Mixed Bag", mixed_items, colors['volume'], colors['volume'], y)
        
        # Add rounded corners and save
        return self._finalize_image(img, y, width, height, output_file)
    
    def generate_image_part2(self, output_file='weekly_highlights_part2.png'):
        """Generate Part 2: Activity & Community"""
        from PIL import Image, ImageDraw, ImageFont
        
        # Get data
        records = self.get_latest_data()
        
        if not records:
            print("❌ No data available for generating image")
            return
        
        # Get analysis results
        # First deduplicate records for track ownership and rivalries
        deduplicated_records = self.deduplicate_records(records)
        track_owners = self.analyze_track_ownership(deduplicated_records)
        rivalries = self.detect_rivalries(deduplicated_records)
        
        # Image dimensions and setup
        width = 1200
        height = 1600  # Taller for part 2 with more sections
        
        # Create image with light background
        img = Image.new('RGB', (width, height), (245, 245, 250))
        draw = ImageDraw.Draw(img)
        
        # Load fonts - bold and prominent like reference
        try:
            font_title = ImageFont.truetype("DejaVuSans-Bold.ttf", 50)
            font_heading = ImageFont.truetype("DejaVuSans-Bold.ttf", 36)
            font_subheading = ImageFont.truetype("DejaVuSans-Bold.ttf", 28)
            font_text = ImageFont.truetype("DejaVuSans-Bold.ttf", 24)
            font_small = ImageFont.truetype("DejaVuSans-Bold.ttf", 20)
        except:
            try:
                font_title = ImageFont.truetype("arialbd.ttf", 50)
                font_heading = ImageFont.truetype("arialbd.ttf", 36)
                font_subheading = ImageFont.truetype("arialbd.ttf", 28)
                font_text = ImageFont.truetype("arialbd.ttf", 24)
                font_small = ImageFont.truetype("arialbd.ttf", 20)
            except:
                font_title = ImageFont.load_default()
                font_heading = ImageFont.load_default()
                font_subheading = ImageFont.load_default()
                font_text = ImageFont.load_default()
                font_small = ImageFont.load_default()
        
        # Colors matching the reference image exactly
        colors = {
            'header_bg': (49, 68, 119),          # Dark blue header
            'orange_stripe': (255, 165, 0),      # Orange accent stripe
            'title_text': (255, 255, 255),       # White title text
            'time_masters': (70, 130, 180),      # Blue
            'performance': (255, 140, 0),        # Orange  
            'volume': (60, 179, 113),           # Green
            'general': (60, 179, 113),          # Green for Quick Stats (was Track Ownership color)
            'text': (40, 40, 40),               # Dark text
            'header_text': (255, 255, 255),     # White section headers
            'section_title': (70, 130, 180),    # Blue section titles
        }
        
        y = 0
        
        # Create ĊĦ Team header like reference image
        header_height = 85
        # Dark blue background
        draw.rectangle([(0, 0), (width, header_height)], fill=colors['header_bg'])
        # Orange accent stripe
        draw.rectangle([(0, header_height-8), (width, header_height)], fill=colors['orange_stripe'])
        
        # ĊĦ Team title
        title_text = "ĊĦ Team — Weekly Highlights"
        title_bbox = draw.textbbox((0, 0), title_text, font=font_title)
        title_width = title_bbox[2] - title_bbox[0]
        title_x = (width - title_width) // 2
        draw.text((title_x, 20), title_text, fill=colors['title_text'], font=font_title)
        
        y = header_height + 30
        
        # Helper function to draw rounded rectangles
        def draw_rounded_rectangle(draw_obj, coords, fill, radius=8):
            x1, y1, x2, y2 = coords[0][0], coords[0][1], coords[1][0], coords[1][1]
            
            # Draw main rectangle
            draw_obj.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
            draw_obj.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)
            
            # Draw corners
            draw_obj.pieslice([x1, y1, x1 + 2*radius, y1 + 2*radius], 180, 270, fill=fill)
            draw_obj.pieslice([x2 - 2*radius, y1, x2, y1 + 2*radius], 270, 360, fill=fill)
            draw_obj.pieslice([x1, y2 - 2*radius, x1 + 2*radius, y2], 90, 180, fill=fill)
            draw_obj.pieslice([x2 - 2*radius, y2 - 2*radius, x2, y2], 0, 90, fill=fill)
        
        # Helper function to draw section like reference image
        def draw_section(title, items, bg_color, text_color, y_pos):
            # Section title with colored background (like reference)
            title_height = 50
            draw_rounded_rectangle(draw, [(40, y_pos), (width-40, y_pos + title_height)], fill=text_color, radius=12)
            draw.text((60, y_pos + 14), title, fill=colors['header_text'], font=font_heading)
            y_pos += title_height + 15
            
            # Items with rounded rectangles like reference
            for item in items:
                item_height = 40
                # Create rounded rectangle for each item (like reference)
                draw_rounded_rectangle(draw, [(60, y_pos), (width-60, y_pos + item_height)], fill=bg_color, radius=10)
                draw.text((80, y_pos + 12), item, fill=colors['text'], font=font_text)
                y_pos += item_height + 8
            
            return y_pos + 30
        
        # Helper function to draw section with custom positioning for perfect alignment
        def draw_section_custom(title, items, bg_color, text_color, y_pos):
            # Section title with colored background (like reference)
            title_height = 50
            draw_rounded_rectangle(draw, [(40, y_pos), (width-40, y_pos + title_height)], fill=text_color, radius=12)
            draw.text((60, y_pos + 14), title, fill=colors['header_text'], font=font_heading)
            y_pos += title_height + 15
            
            # Items with rounded rectangles like reference, but with custom positioning
            for item in items:
                item_height = 40
                # Create rounded rectangle for each item (like reference)
                draw_rounded_rectangle(draw, [(60, y_pos), (width-60, y_pos + item_height)], fill=bg_color, radius=10)
                
                # Custom positioning for perfect alignment
                if item['type'] == 'custom':
                    # Draw rivalry in Winner (Score) Loser format
                    draw.text((80, y_pos + 12), f"• {item['rivalry_text']}", fill=colors['text'], font=font_text)
                    # Draw tracks at calculated position
                    draw.text((item['tracks_x'], y_pos + 12), item['tracks'], fill=colors['text'], font=font_text)
                else:
                    # Fallback to regular text
                    draw.text((80, y_pos + 12), item, fill=colors['text'], font=font_text)
                
                y_pos += item_height + 8
            
            return y_pos + 30
        
        # RIVALRIES Section
        if rivalries:
            rivalry_items = []
            
            # Calculate maximum pixel width for proper alignment in images
            max_rivalry_width = 0
            for rivalry in rivalries[:12]:
                # Format: Winner (Score) Loser
                rivalry_text = f"{rivalry['player1']} ({rivalry['score']}) {rivalry['player2']}"
                # Use textbbox to get actual pixel width
                bbox = draw.textbbox((0, 0), rivalry_text, font=font_text)
                rivalry_width = bbox[2] - bbox[0]
                max_rivalry_width = max(max_rivalry_width, rivalry_width)
            
            # Add some padding
            max_rivalry_width += 20
            
            for rivalry in rivalries[:12]:  # Top 12 rivalries instead of 6
                # Format: Winner (Score) Loser - tracks
                winner = rivalry['player1']
                loser = rivalry['player2']
                score = f"({rivalry['score']})"
                tracks = f"{rivalry['shared_tracks']} shared tracks"
                
                # New format: Winner (Score) Loser
                rivalry_text = f"{winner} {score} {loser}"
                
                # Calculate positions
                tracks_x = 100 + max_rivalry_width  # Start tracks at fixed position after rivalry text
                
                if rivalry['leader'] != "Tied":
                    rivalry_items.append({
                        'type': 'custom',
                        'rivalry_text': rivalry_text,
                        'tracks': tracks,
                        'tracks_x': tracks_x
                    })
                else:
                    rivalry_items.append({
                        'type': 'custom',
                        'rivalry_text': rivalry_text,
                        'tracks': f"{tracks} (Tied)",
                        'tracks_x': tracks_x
                    })
            
            y = draw_section_custom("Detected Rivalries", rivalry_items, colors['performance'], colors['performance'], y)
        
        # QUICK STATS Section
        total_records = len(deduplicated_records)  # Unique track achievements, not all attempts
        unique_tracks = len(set(record[2] for record in deduplicated_records))  # Unique tracks with records
        unique_players = len(set(record[0] for record in deduplicated_records))  # Unique players with records
        
        # Calculate top1 and top5 statistics based on deduplicated records (best rank per track only)
        top1_records = len([r for r in deduplicated_records if r[4] == '1'])
        top5_records = len([r for r in deduplicated_records if r[4] and r[4].isdigit() and int(r[4]) <= 5])
        
        top1_percentage = (top1_records / len(deduplicated_records) * 100) if len(deduplicated_records) > 0 else 0
        top5_percentage = (top5_records / len(deduplicated_records) * 100) if len(deduplicated_records) > 0 else 0
        
        # Calculate photo finishes (identical times on same track) - use deduplicated data for best times
        photo_finishes = 0
        track_times = defaultdict(lambda: defaultdict(set))  # track -> time -> set of players
        
        for record in deduplicated_records:
            login, nick, track, time, rank, date, envir, mode, server = record
            if time:  # Only count if we have a time
                track_times[track][time].add(login)
        
        for track, times in track_times.items():
            for time, players in times.items():
                if len(players) > 1:  # Multiple players with same time
                    photo_finishes += 1
        
        stats_items = [
            f"• {unique_players} players • {total_records} total dedi's",
            f"• {unique_tracks} tracks • {top1_records} WRs ({top1_percentage:.1f}%) • {top5_records} top5 dedi's ({top5_percentage:.1f}%)",
            f"• {photo_finishes} photo finishes (identical times)"
        ]
        
        # Track popularity uses deduplicated data to show unique records per track
        track_popularity = Counter(record[2] for record in deduplicated_records)
        if track_popularity:
            hottest_track = track_popularity.most_common(1)[0]
            stats_items.append(f"• Hottest track: {hottest_track[0]} ({hottest_track[1]} dedi's)")
        
        y = draw_section("Quick Stats", stats_items, colors['general'], colors['general'], y)
        
        # Add rounded corners and save
        return self._finalize_image(img, y, width, height, output_file)

    def _finalize_image(self, img, y, width, height, output_file):
        """Helper method to finalize and save image"""
        from PIL import Image, ImageDraw
        
        # Add rounded corners and shadow effect
        def add_rounded_corners(im, radius=20):
            circle = Image.new('L', (radius * 2, radius * 2), 0)
            draw_circle = ImageDraw.Draw(circle)
            draw_circle.ellipse((0, 0, radius * 2, radius * 2), fill=255)
            alpha = Image.new('L', im.size, 255)
            w, h = im.size
            alpha.paste(circle.crop((0, 0, radius, radius)), (0, 0))
            alpha.paste(circle.crop((0, radius, radius, radius * 2)), (0, h - radius))
            alpha.paste(circle.crop((radius, 0, radius * 2, radius)), (w - radius, 0))
            alpha.paste(circle.crop((radius, radius, radius * 2, radius * 2)), (w - radius, h - radius))
            im.putalpha(alpha)
            return im
        
        # Crop to actual content height
        content_height = min(y + 50, height)
        img = img.crop((0, 0, width, content_height))
        
        # Add rounded corners
        img = img.convert('RGBA')
        img = add_rounded_corners(img)
        
        # Save image
        try:
            if os.path.exists(output_file):
                os.remove(output_file)
            img.save(output_file, 'PNG', quality=95)
            print(f"✅ Weekly highlights image saved to: {output_file}")
        except Exception as e:
            print(f"❌ Error saving image: {e}")
        
        return output_file

    def generate_achievement_dashboard(self, output_file='weekly_achievement_dashboard.png'):
        """Generate a TrackMania Official themed achievement dashboard for weekly champions"""
        from PIL import Image, ImageDraw, ImageFont, ImageFilter
        
        # Create folder for this report
        folder = self.create_report_folder()
        
        if output_file:
            output_file = os.path.join(folder, os.path.basename(output_file))
        else:
            output_file = os.path.join(folder, 'weekly_achievement_dashboard.png')
        
        # Get data
        raw_records = self.get_latest_data()
        
        if not raw_records:
            print("❌ No data available for generating achievement dashboard")
            return
        
        # Deduplicate records for performance and volume stats
        deduplicated_records = self.deduplicate_records(raw_records)
        
        # Get analysis results
        time_masters = self.analyze_time_masters(raw_records)
        performance_elite = self.analyze_performance_elite(deduplicated_records)
        # Solo explorer analysis (most solo tracks)
        solo_explorer_results = self.analyze_solo_explorer(raw_records)
        performance_elite.update(solo_explorer_results)
        volume_champions = self.analyze_volume_champions(deduplicated_records)
        lolsport_stats = self.analyze_lolsport_addict(deduplicated_records)
        humorous_stats = self.analyze_humorous_stats(raw_records)
        
        # Enhanced gaming dimensions
        width = 1500
        height = 1300
        
        # Create image with heatmap-style dark background
        img = Image.new('RGB', (width, height), (25, 25, 35))
        draw = ImageDraw.Draw(img)
        
        # Add noise texture for enhanced visual depth
        try:
            import random
            random.seed(42)  # Fixed seed for consistent noise pattern
            
            # Generate noise texture overlay
            for _ in range(width * height // 200):  # Adjust density as needed
                x = random.randint(0, width - 1)
                y = random.randint(0, height - 1)
                
                # Create subtle noise with varying intensity
                base_color = (25, 25, 35)
                noise_intensity = random.randint(-15, 15)
                
                r = max(0, min(255, base_color[0] + noise_intensity))
                g = max(0, min(255, base_color[1] + noise_intensity))
                b = max(0, min(255, base_color[2] + noise_intensity))
                
                # Draw small noise pixels
                size = random.choice([1, 1, 1, 2])  # Mostly 1x1 pixels, some 2x2
                draw.rectangle([x, y, x + size, y + size], fill=(r, g, b))
        except ImportError:
            # Fallback to simple pattern if random not available
            for i in range(0, width, 40):
                for j in range(0, height, 40):
                    if (i + j) % 80 == 0:
                        draw.rectangle([i, j, i+2, j+2], fill=(28, 28, 38))
        
        # Gaming-style fonts with enhanced sizes
        try:
            font_title = ImageFont.truetype("DejaVuSans-Bold.ttf", 58)
            font_heading = ImageFont.truetype("DejaVuSans-Bold.ttf", 38)
            font_card_title = ImageFont.truetype("DejaVuSans-Bold.ttf", 32)
            font_player = ImageFont.truetype("DejaVuSans-Bold.ttf", 36)
            font_stats = ImageFont.truetype("DejaVuSans-Bold.ttf", 32)
            font_small = ImageFont.truetype("DejaVuSans-Bold.ttf", 24)
        except:
            try:
                font_title = ImageFont.truetype("arialbd.ttf", 58)
                font_heading = ImageFont.truetype("arialbd.ttf", 38)
                font_card_title = ImageFont.truetype("arialbd.ttf", 32)
                font_player = ImageFont.truetype("arialbd.ttf", 36)
                font_stats = ImageFont.truetype("arialbd.ttf", 32)
                font_small = ImageFont.truetype("arialbd.ttf", 24)
            except:
                font_title = ImageFont.load_default()
                font_heading = ImageFont.load_default()
                font_card_title = ImageFont.load_default()
                font_player = ImageFont.load_default()
                font_stats = ImageFont.load_default()
                font_small = ImageFont.load_default()
        
        # Mystical Power gradient color scheme
        colors = {
            'title': (255, 255, 255),
            'heading': (255, 255, 255),
            'text': (220, 220, 220),
            'card_bg': (30, 30, 40),
            'card_bg_gradient': (40, 40, 55),
            'accent': (52, 152, 219),       # TM Blue accent
            'glow': (52, 152, 219),         # TM Blue glow
            'shadow': (0, 0, 0),            # Black shadow
        }
        
        # Retro Synthwave - 3 Column Gradient Colors
        mystical_gradients = [
            # Column 1: Sunset Pink (Dark Pink to Hot Pink)
            {'start': (80, 0, 40), 'end': (255, 0, 150)},
            # Column 2: Neon Teal (Dark Teal to Electric Cyan)
            {'start': (0, 80, 80), 'end': (0, 255, 255)},
            # Column 3: Electric Violet (Dark Purple to Electric Violet)
            {'start': (60, 0, 80), 'end': (180, 0, 255)}
        ]
        
        # Helper function for minimal glow effect
        def add_neon_glow(draw_obj, text, x, y, font, color, glow_color, glow_size=1):
            """Add minimal glow effect to text"""
            for i in range(glow_size, 0, -1):
                alpha = int(255 * (1 - i / glow_size) * 0.1)  # Minimal glow intensity
                for dx in range(-i, i+1):
                    for dy in range(-i, i+1):
                        if dx*dx + dy*dy <= i*i:
                            draw_obj.text((x + dx, y + dy), text, font=font, fill=glow_color)
            draw_obj.text((x, y), text, font=font, fill=color)
        
        # Enhanced rounded rectangle with horizontal gradient (left to right)
        def draw_rounded_rectangle_gradient(draw_obj, coords, fill_start, fill_end, outline=None, radius=20):
            x1, y1, x2, y2 = coords[0][0], coords[0][1], coords[1][0], coords[1][1]
            
            if x1 > x2:
                x1, x2 = x2, x1
            if y1 > y2:
                y1, y2 = y2, y1
            
            if x2 - x1 < 2 * radius:
                radius = max(1, (x2 - x1) // 2)
            if y2 - y1 < 2 * radius:
                radius = max(1, (y2 - y1) // 2)
            
            # Draw horizontal gradient by vertical lines (left to right)
            for i in range(int(x2 - x1)):
                ratio = i / (x2 - x1)
                r = int(fill_start[0] + (fill_end[0] - fill_start[0]) * ratio)
                g = int(fill_start[1] + (fill_end[1] - fill_start[1]) * ratio)
                b = int(fill_start[2] + (fill_end[2] - fill_start[2]) * ratio)
                
                # Calculate line boundaries for rounded corners
                line_x = x1 + i
                if i < radius:
                    # Left rounded part
                    indent = radius - int((radius**2 - (radius - i)**2)**0.5)
                    line_start = y1 + indent
                    line_end = y2 - indent
                elif i > (x2 - x1) - radius:
                    # Right rounded part
                    right_i = (x2 - x1) - i
                    indent = radius - int((radius**2 - (radius - right_i)**2)**0.5)
                    line_start = y1 + indent
                    line_end = y2 - indent
                else:
                    # Middle straight part
                    line_start = y1
                    line_end = y2
                
                if line_start < line_end:
                    draw_obj.line([(line_x, line_start), (line_x, line_end)], fill=(r, g, b))
        
        # Enhanced achievement card with improved alignment and retro synthwave gradients
        def draw_achievement_card(x, y, width, height, title, player, stats, gradient):
            # Multiple shadow layers for depth
            shadow_layers = [(8, (5, 10, 15)), (6, (10, 15, 25)), (4, (15, 20, 30))]
            for offset, shadow_color in shadow_layers:
                draw_rounded_rectangle_gradient(draw, [(x + offset, y + offset), 
                                               (x + width + offset, y + height + offset)], 
                                              shadow_color, shadow_color, radius=25)
            
            # Main card with gradient background
            draw_rounded_rectangle_gradient(draw, [(x, y), (x + width, y + height)], 
                                          colors['card_bg'], colors['card_bg_gradient'], radius=25)
            
            # Add subtle noise texture to cards
            try:
                import random
                random.seed(hash(title) % 1000)  # Different noise for each card
                
                for _ in range(width * height // 1000):  # Subtle card noise
                    noise_x = random.randint(x + 5, x + width - 5)
                    noise_y = random.randint(y + 5, y + height - 5)
                    
                    # Very subtle noise on cards
                    noise_intensity = random.randint(-8, 8)
                    base_r, base_g, base_b = colors['card_bg']
                    
                    r = max(0, min(255, base_r + noise_intensity))
                    g = max(0, min(255, base_g + noise_intensity))
                    b = max(0, min(255, base_b + noise_intensity))
                    
                    draw.rectangle([noise_x, noise_y, noise_x + 1, noise_y + 1], fill=(r, g, b))
            except ImportError:
                pass  # Skip noise texture if random not available
            
            # Minimal border glow effect using gradient end color
            end_color = gradient['end']
            glow_layers = [(1, (end_color[0]//8, end_color[1]//8, end_color[2]//8))]
            for thickness, glow_color in glow_layers:
                # Top border
                draw.rectangle([x-thickness, y-thickness, x+width+thickness, y+30+thickness], 
                             outline=glow_color, width=thickness)
                # Main border
                draw.rectangle([x-thickness, y-thickness, x+width+thickness, y+height+thickness], 
                             outline=glow_color, width=1)
            
            # Retro synthwave gradient accent header
            draw_rounded_rectangle_gradient(draw, [(x, y), (x + width, y + 35)], 
                                          gradient['start'], gradient['end'], radius=25)
            
            # Minimal inner glow effect using gradient end color
            inner_glow_color = (end_color[0]//8, end_color[1]//8, end_color[2]//8)
            draw.rectangle([x+2, y+2, x+width-2, y+height-2], outline=inner_glow_color, width=1)
            
            # Achievement title with improved alignment and reduced glow
            title_display = title
            title_bbox = draw.textbbox((0, 0), title_display, font=font_card_title)
            title_width = title_bbox[2] - title_bbox[0]
            if title_width > width - 40:
                while title_width > width - 50 and len(title_display) > 0:
                    title_display = title_display[:-1]
                    title_bbox = draw.textbbox((0, 0), title_display + "...", font=font_card_title)
                    title_width = title_bbox[2] - title_bbox[0]
                title_display += "..."
            
            # Centered title with proper alignment
            title_x = x + (width - title_width) // 2
            title_y = y + 55
            add_neon_glow(draw, title_display, title_x, title_y, font_card_title, 
                         colors['heading'], (end_color[0]//4, end_color[1]//4, end_color[2]//4), glow_size=1)
            
            # Player name with improved alignment and reduced glow
            player_display = player
            player_bbox = draw.textbbox((0, 0), player_display, font=font_player)
            player_width = player_bbox[2] - player_bbox[0]
            if player_width > width - 40:
                while player_width > width - 50 and len(player_display) > 0:
                    player_display = player_display[:-1]
                    player_bbox = draw.textbbox((0, 0), player_display + "...", font=font_player)
                    player_width = player_bbox[2] - player_bbox[0]
                player_display += "..."
            
            # Centered player name with proper alignment
            player_x = x + (width - player_width) // 2
            player_y = y + 105
            add_neon_glow(draw, player_display, player_x, player_y, font_player, 
                         colors['accent'], colors['glow'], glow_size=1)
            
            # Stats with improved alignment and reduced glow
            stats_display = stats
            stats_bbox = draw.textbbox((0, 0), stats_display, font=font_stats)
            stats_width = stats_bbox[2] - stats_bbox[0]
            if stats_width > width - 40:
                while stats_width > width - 50 and len(stats_display) > 0:
                    stats_display = stats_display[:-1]
                    stats_bbox = draw.textbbox((0, 0), stats_display + "...", font=font_stats)
                    stats_width = stats_bbox[2] - stats_bbox[0]
                stats_display += "..."
            
            # Centered stats with proper alignment
            stats_x = x + (width - stats_width) // 2
            stats_y = y + 155
            add_neon_glow(draw, stats_display, stats_x, stats_y, font_stats, 
                         colors['text'], (100, 100, 100), glow_size=1)
        
        y = -10
        
        # Enhanced title with cyberpunk banner
        title_text = "ĊĦ Team — Weekly Stats"
        title_bbox = draw.textbbox((0, 0), title_text, font=font_title)
        title_width = title_bbox[2] - title_bbox[0]
        title_x = (width - title_width) // 2
        
        # Create heatmap-style dark banner background
        banner_height = 100
        banner_bg = Image.new('RGB', (width, banner_height), (25, 25, 35))
        banner_draw = ImageDraw.Draw(banner_bg)
        
        # Banner gradient
        for i in range(banner_height - 20):
            r = int(25 + (i / (banner_height - 20)) * 15)
            g = int(25 + (i / (banner_height - 20)) * 15)
            b = int(35 + (i / (banner_height - 20)) * 20)
            banner_draw.line([(0, i), (width, i)], fill=(r, g, b))
        
        # Accent strips removed for cleaner look
        
        # Apply banner
        img.paste(banner_bg, (0, 0))
        
        # Title with minimal glow
        add_neon_glow(draw, title_text, title_x, y + 20, font_title, 
                     colors['title'], colors['glow'], glow_size=1)
        
        y += 120
        
        # Collect all achievements (color will be assigned based on column position)
        achievements = []
        
        # Activity achievements
        if 'night_owl' in time_masters:
            achievements.append({
                'title': 'NIGHT OWL',
                'player': time_masters['night_owl']['player'],
                'stats': f"{time_masters['night_owl']['count']} late-night dedis"
            })
        
        if 'weekend_warrior' in time_masters:
            achievements.append({
                'title': 'SATURDAY NIGHT FEVER',
                'player': time_masters['weekend_warrior']['player'],
                'stats': f"{time_masters['weekend_warrior']['percentage']:.0f}% weekend dedis"
            })
        
        if 'binge_racer' in time_masters:
            achievements.append({
                'title': 'JUST ONE MORE',
                'player': time_masters['binge_racer']['player'],
                'stats': f"{time_masters['binge_racer']['count']} dedis in one day"
            })
        
        if 'daily_grinder' in time_masters:
            achievements.append({
                'title': 'CREATURE OF HABIT',
                'player': time_masters['daily_grinder']['player'],
                'stats': f"{time_masters['daily_grinder']['days_played']}/7 days active"
            })
        
        # Performance achievements
        if 'solo_explorer' in performance_elite:
            explorer = performance_elite['solo_explorer']
            achievements.append({
                'title': 'SOLO EXPLORER',
                'player': explorer['player'],
                'stats': f"{explorer['solo_tracks']} solo tracks"
            })
        
        if 'lucky_number' in performance_elite:
            achievements.append({
                'title': 'LUCKY NUMBER',
                'player': performance_elite['lucky_number']['player'],
                'stats': f"{performance_elite['lucky_number']['rank_1_count']} WRs"
            })
        
        if 'always_the_bridesmaid' in performance_elite:
            achievements.append({
                'title': 'FIRST LOSER',
                'player': performance_elite['always_the_bridesmaid']['player'],
                'stats': f"{performance_elite['always_the_bridesmaid']['rank_2_count']} second places"
            })
        
        # Volume achievements
        if 'no_lifer' in volume_champions:
            achievements.append({
                'title': 'NO-LIFER',
                'player': volume_champions['no_lifer']['player'],
                'stats': f"{volume_champions['no_lifer']['total_dedi']} total dedi's"
            })
        
        if 'track_hunter' in volume_champions:
            achievements.append({
                'title': 'TRACK HUNTER',
                'player': volume_champions['track_hunter']['player'],
                'stats': f"{volume_champions['track_hunter']['unique_tracks']} different tracks"
            })
        
        if 'lolsport_addict' in lolsport_stats:
            achievements.append({
                'title': 'LOLSPORT ADDICT',
                'player': lolsport_stats['lolsport_addict']['player'],
                'stats': f"{lolsport_stats['lolsport_addict']['lolsport_count']} lolsport dedis"
            })
        
        # Server achievements
        server_stats = self.analyze_server_stats(raw_records)
        if 'minilol_champion' in server_stats:
            achievements.append({
                'title': 'MINILOL CHAMPION',
                'player': server_stats['minilol_champion']['player'],
                'stats': f"{server_stats['minilol_champion']['unique_tracks']} unique minilol dedis"
            })
        
        # Special/Fun achievements
        if 'benchwarmer' in humorous_stats:
            achievements.append({
                'title': 'BENCHWARMER',
                'player': humorous_stats['benchwarmer']['player'],
                'stats': f"{humorous_stats['benchwarmer']['total_records']} dedis total"
            })
        
        if 'caffeine_addict' in humorous_stats:
            achievements.append({
                'title': 'CAFFEINE ADDICT',
                'player': humorous_stats['caffeine_addict']['player'],
                'stats': f"{humorous_stats['caffeine_addict']['hours']} diff hours active"
            })
        
        if 'rage_quit_candidate' in humorous_stats:
            achievements.append({
                'title': 'RAGE QUIT CANDIDATE',
                'player': humorous_stats['rage_quit_candidate']['player'],
                'stats': f"{humorous_stats['rage_quit_candidate']['original_rank']} → {humorous_stats['rage_quit_candidate']['final_rank']} on {humorous_stats['rage_quit_candidate']['track'][:20]}"
            })
        
        # Enhanced card layout with better alignment
        card_width = 430
        card_height = 200
        cards_per_row = 3
        card_spacing_x = 470
        card_spacing_y = 300
        
        # Better centering calculation
        total_width = (cards_per_row * card_width) + ((cards_per_row - 1) * (card_spacing_x - card_width))
        start_x = (width - total_width) // 2
        
        for i, achievement in enumerate(achievements[:12]):  # Show up to 12 achievements
            row = i // cards_per_row
            col = i % cards_per_row
            
            card_x = start_x + (col * card_spacing_x)
            card_y = y + (row * card_spacing_y)
            
            # Use retro synthwave gradient based on column position
            gradient = mystical_gradients[col]
            
            draw_achievement_card(
                card_x, card_y, card_width, card_height,
                achievement['title'], achievement['player'], 
                achievement['stats'], gradient
            )
        
        # Grid lines removed for cleaner look
        
        # Save enhanced image
        try:
            if os.path.exists(output_file):
                os.remove(output_file)
            img.save(output_file, 'PNG', quality=95)
            print(f"🎮 Enhanced gaming achievement dashboard saved to: {output_file}")
        except Exception as e:
            print(f"❌ Error saving achievement dashboard: {e}")
        
        return output_file

def main():
    """Main execution"""
    parser = argparse.ArgumentParser(description='Generate weekly TrackMania team statistics')
    parser.add_argument('-o', '--output', type=str, default='weekly_stats.txt', help='Output file path (default: weekly_stats.txt)')
    parser.add_argument('--db', type=str, default='../../dedimania_history_master.db', help='Database file path')
    parser.add_argument('--discord', action='store_true', help='Generate Discord-friendly summary instead of full report')
    parser.add_argument('--image', action='store_true', help='Generate image version of the weekly report')
    parser.add_argument('--heatmap', action='store_true', help='Generate rivalry heatmap and weekly pulse visualization')
    parser.add_argument('--dashboard', action='store_true', help='Generate achievement dashboard visualization')
    parser.add_argument('--minilol-details', action='store_true', help='Show detailed breakdown of MiniLol Champion performance')
    parser.add_argument('--both', action='store_true', help='Generate both full report and Discord summary')
    parser.add_argument('--all', action='store_true', help='Generate all versions (full report, Discord summary, images, heatmap, and dashboard)')
    
    args = parser.parse_args()
    
    generator = WeeklyStatsGenerator(db_path=args.db)
    
    if args.all:
        # Generate all versions
        generator.generate_report(output_file=args.output)
        discord_output = args.output.replace('.txt', '_discord.txt')
        generator.generate_discord_summary(output_file=discord_output)
        image_output = args.output.replace('.txt', '.png')
        generator.generate_image_report(output_file=image_output)
    elif args.dashboard:
        # Generate only achievement dashboard
        dashboard_output = args.output.replace('.txt', '_dashboard.png')
        generator.generate_achievement_dashboard(output_file=dashboard_output)
    elif args.heatmap:
        # Generate only heatmap
        heatmap_output = args.output.replace('.txt', '_heatmap.png')
        generator.generate_rivalry_heatmap(output_file=heatmap_output)
    elif args.image:
        # Generate only image version
        image_output = args.output.replace('.txt', '.png')
        generator.generate_image_report(output_file=image_output)
    elif args.discord:
        # Generate only Discord summary
        discord_output = args.output.replace('.txt', '_discord.txt')
        generator.generate_discord_summary(output_file=discord_output)
    elif args.both:
        # Generate both text versions
        generator.generate_report(output_file=args.output)
        discord_output = args.output.replace('.txt', '_discord.txt')
        generator.generate_discord_summary(output_file=discord_output)
    elif getattr(args, 'minilol_details', False):
        # Show detailed MiniLol Champion analysis
        generator.print_minilol_champion_details()
    else:
        # Generate full report (default)
        generator.generate_report(output_file=args.output)

if __name__ == '__main__':
    main() 