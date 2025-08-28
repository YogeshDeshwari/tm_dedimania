#!/usr/bin/env python3
"""
Gaming-Style Leaderboard Generator
Based on player_leaderboard_weekly.py with cyberpunk/gaming visual aesthetic
"""

import sqlite3
import matplotlib.pyplot as plt
import sys
from collections import Counter, defaultdict
import re
from datetime import datetime, timedelta
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import textwrap
import io
import numpy as np
import csv
import argparse

# Set matplotlib style and font
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams.update({
    'font.size': 16,
    'axes.titlesize': 20,
    'axes.labelsize': 16,
    'xtick.labelsize': 14,
    'ytick.labelsize': 14,
    'legend.fontsize': 14,
    'figure.titlesize': 24,
    'font.family': 'DejaVu Sans',
})

# Provide a list of player logins here
player_logins = ['yrdk',
                 'niyck',
                 'youngblizzard',
                 'pointiff',
                 '2nd',
                 'yogeshdeshwari', 
                 'bananaapple', 
                 'xxgammelhdxx', 
                 'tzigitzellas', 
                 'fichekk', 
                 'mglulguf', 
                 'knotisaac', 
                 'hoodintm', 
                 'heisenberg01', 
                 'paxinho', 
                 'thewelkuuus',
                 'riza_123',
                 'dejong2',
                 'brunobranco32',
                 'cholub',
                 'certifiednebula',
                 'luka1234car',
                 'sylwson2',
                 'erreerrooo',
                 'declineee',
                 'bojo_interia.eu',
                 'noam3105',
                 'stwko',
                 'mitrug',
                 'bobjegraditelj'
                 ]  # Replace/'add as needed

# Database configuration - use absolute path to ensure consistent location
import os
script_dir = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.abspath(os.path.join(script_dir, '..', '..', 'dedimania_history_master.db'))

# Global variables for custom date range
CUSTOM_START_DATE = None
CUSTOM_END_DATE = None

def get_weekly_date_range():
    """Calculate the most recent Sunday to current day date range, or use custom dates if provided"""
    global CUSTOM_START_DATE, CUSTOM_END_DATE
    
    # Use custom dates if provided
    if CUSTOM_START_DATE and CUSTOM_END_DATE:
        return CUSTOM_START_DATE, CUSTOM_END_DATE
    
    # Default behavior: calculate current week
    today = datetime.now()
    
    # Find the most recent Sunday (but if today is Sunday, go back to previous Sunday)
    # Sunday is weekday 6 (Monday=0, Sunday=6)
    if today.weekday() == 6:
        # Today is Sunday, go back 7 days to get the previous Sunday
        start_date = today - timedelta(days=7)
    else:
        # Go back to the most recent Sunday
        days_since_sunday = (today.weekday() + 1) % 7  # +1 because Sunday is day 6, but we want 0-based from Sunday
        start_date = today - timedelta(days=days_since_sunday)
    
    # End date is always today
    end_date = today
    
    return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')

def get_previous_week_date_range():
    """Calculate the previous Sunday to Saturday date range"""
    current_start, current_end = get_weekly_date_range()
    
    # Convert to datetime objects
    current_start_dt = datetime.strptime(current_start, '%Y-%m-%d')
    
    # Previous week is 7 days before current week's start
    prev_start_dt = current_start_dt - timedelta(days=7)
    prev_end_dt = current_start_dt - timedelta(days=1)  # Saturday before current Sunday
    
    return prev_start_dt.strftime('%Y-%m-%d'), prev_end_dt.strftime('%Y-%m-%d')

def get_specific_past_week_range(weeks_back=1):
    """Calculate a specific past week range (weeks_back=1 for last week, weeks_back=2 for week before last, etc.)"""
    today = datetime.now()
    
    # Find the most recent Sunday
    if today.weekday() == 6:
        # Today is Sunday, this is week 0
        most_recent_sunday = today
    else:
        # Go back to the most recent Sunday
        days_since_sunday = (today.weekday() + 1) % 7
        most_recent_sunday = today - timedelta(days=days_since_sunday)
    
    # Go back the specified number of weeks
    target_week_start = most_recent_sunday - timedelta(days=7 * weeks_back)
    target_week_end = target_week_start + timedelta(days=6)  # Saturday of that week
    
    return target_week_start.strftime('%Y-%m-%d'), target_week_end.strftime('%Y-%m-%d')

def get_custom_week_range(start_date_str, end_date_str):
    """Use a completely custom date range"""
    return start_date_str, end_date_str

def get_player_records_from_db(login, date_range_func=get_weekly_date_range):
    """Get player records from database for the specified date range"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Get date range
    start_date, end_date = date_range_func()
    
    # Ensure end_date includes the full day (23:59:59)
    if len(end_date) == 10:  # Format: YYYY-MM-DD
        end_date = end_date + " 23:59:59"
    
    cursor.execute("""
        SELECT player_login, NickName, Challenge, Record, Rank, RecordDate, Envir, Mode
        FROM dedimania_records 
        WHERE player_login = ? AND RecordDate >= ? AND RecordDate <= ?
        ORDER BY RecordDate DESC
    """, (login, start_date, end_date))
    
    records = cursor.fetchall()
    conn.close()
    
    # Convert to dictionary format for compatibility
    record_dicts = []
    for record in records:
        record_dict = {
            'Login': record[0],
            'NickName': record[1], 
            'Challenge': record[2],
            'Record': record[3],
            'Rank': record[4],
            'RecordDate': record[5],
            'Envir': record[6],
            'Mode': record[7]
        }
        record_dicts.append(record_dict)
    
    return record_dicts

def calculate_previous_week_leaderboard():
    """Calculate previous week's leaderboard positions"""
    print("📈 Calculating previous week's leaderboard for trend analysis...")
    
    challenge_cache = get_challenge_info_cache()
    prev_player_table = []
    
    for login in player_logins:
        # Get previous week's records
        prev_records = get_player_records_from_db(login, get_previous_week_date_range)
        
        if not prev_records:
            continue
        
        # Deduplicate records
        prev_records = deduplicate_player_records(prev_records)
        
        # Calculate points for previous week
        prev_points = calculate_points(prev_records, challenge_cache)
        
        # Get nickname
        def get_latest_nickname_for_login(login, records):
            latest_nick = login
            latest_date = ""
            
            for r in records:
                if r.get('NickName') and r.get('RecordDate', '') > latest_date:
                    latest_date = r.get('RecordDate', '')
                    latest_nick = r.get('NickName')
            
            return latest_nick
        
        nickname = get_latest_nickname_for_login(login, prev_records)
        total_records = len(prev_records)
        top1 = sum(1 for r in prev_records if r.get('Rank', '') == '1')
        top3 = sum(1 for r in prev_records if r.get('Rank', '').isdigit() and 1 <= int(r.get('Rank', '0')) <= 3)
        top5 = sum(1 for r in prev_records if r.get('Rank', '').isdigit() and 1 <= int(r.get('Rank', '0')) <= 5)
        
        prev_player_table.append((nickname, top5, top3, top1, total_records, 0, prev_points, login))  # Added login for matching
    
    # Sort previous week's data the same way as current week
    prev_player_table.sort(key=lambda x: (x[6], x[3], x[2], x[1]), reverse=True)
    
    # Create a mapping from login to previous rank position
    prev_rankings = {}
    for i, player in enumerate(prev_player_table):
        login = player[7]  # login is at index 7
        prev_rankings[login] = i + 1  # Rank position (1-based)
    
    print(f"📊 Previous week leaderboard calculated with {len(prev_rankings)} players")
    return prev_rankings

def deduplicate_player_records(records):
    """
    Deduplicate records to keep only the best rank for each player-track combination.
    If a player has multiple records on the same track, only keep the one with the best (lowest) rank.
    """
    # Group records by (player_login, track) combination
    track_records = {}
    
    for record in records:
        login = record.get('Login', '')
        track = record.get('Challenge', '')
        rank_str = record.get('Rank', '')
        
        if not login or not track:
            continue
            
        # Convert rank to integer for comparison (higher values for non-numeric ranks)
        try:
            rank = int(rank_str) if rank_str.isdigit() else 999
        except:
            rank = 999
        
        key = (login, track)
        
        if key not in track_records:
            track_records[key] = record
        else:
            # Keep the record with the better (lower) rank
            existing_rank_str = track_records[key].get('Rank', '')
            try:
                existing_rank = int(existing_rank_str) if existing_rank_str.isdigit() else 999
            except:
                existing_rank = 999
            
            if rank < existing_rank:
                track_records[key] = record
    
    # Return deduplicated records
    return list(track_records.values())

# Create a single output directory for all summaries
summaries_dir = os.path.join(os.getcwd(), 'summaries')
os.makedirs(summaries_dir, exist_ok=True)

# Initialize data collection for highlights
all_player_data = {}

def add_neon_glow(draw, text, x, y, font, color, glow_color, glow_size=3):
    """Add a neon glow effect to text"""
    # Draw glow layers
    for i in range(glow_size, 0, -1):
        alpha = int(255 * (1 - i / glow_size) * 0.4)
        for dx in range(-i, i+1):
            for dy in range(-i, i+1):
                if dx*dx + dy*dy <= i*i:
                    draw.text((x + dx, y + dy), text, font=font, fill=glow_color)
    
    # Draw main text
    draw.text((x, y), text, font=font, fill=color)

def add_rounded_corners(im, radius=24, border=6, border_color=(0, 255, 255), shadow_offset=12, shadow_blur=20, shadow_color=(0, 255, 255, 80)):
    """
    Gaming-style rounded corners with enhanced neon glow effect
    """
    w, h = im.size
    mask = Image.new('L', (w, h), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0, 0, w, h], radius=radius, fill=255)
    rounded = im.convert('RGBA').copy()
    rounded.putalpha(mask)
    final_w = w + shadow_offset + border * 2
    final_h = h + shadow_offset + border * 2
    final_img = Image.new('RGBA', (final_w, final_h), (0,0,0,0))
    if shadow_offset > 0:
        shadow = Image.new('RGBA', (final_w, final_h), (0,0,0,0))
        shadow_mask = Image.new('L', (w+border*2, h+border*2), 0)
        shadow_draw = ImageDraw.Draw(shadow_mask)
        shadow_draw.rounded_rectangle([0, 0, w+border*2-1, h+border*2-1], radius=radius+border, fill=255)
        shadow_layer = Image.new('RGBA', (final_w, final_h), (0,0,0,0))
        shadow_layer.paste(shadow_color, (shadow_offset, shadow_offset), shadow_mask)
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(shadow_blur))
        final_img.paste(shadow_layer, (0,0), shadow_layer)
    if border > 0:
        border_img = Image.new('RGBA', (w + 2 * border, h + 2 * border), (0,0,0,0))
        border_mask_draw = ImageDraw.Draw(border_img)
        border_mask_draw.rounded_rectangle([0,0,w+2*border, h+2*border], radius=radius+border, fill=border_color)
        border_mask_draw.rounded_rectangle([border,border,w+border, h+border], radius=radius, fill=(0,0,0,0))
        final_img.paste(border_img, (0,0), border_img)
    final_img.paste(rounded, (border, border), rounded)
    return final_img

def parse_arguments():
    """Parse command line arguments for custom date ranges"""
    parser = argparse.ArgumentParser(
        description='Generate Gaming Leaderboard with optional custom date range',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python gaming_leaderboard.py                                    # Current week (Sunday to today)
  python gaming_leaderboard.py --start 2025-08-03 --end 2025-08-16  # Custom date range
  python gaming_leaderboard.py --weeks-back 1                     # Last complete week
  python gaming_leaderboard.py --weeks-back 2                     # 2 weeks ago
        """
    )
    
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--start', '--start-date', 
                      help='Start date (YYYY-MM-DD format)')
    group.add_argument('--weeks-back', type=int,
                      help='Generate for N weeks back (1=last week, 2=week before last, etc.)')
    
    parser.add_argument('--end', '--end-date',
                       help='End date (YYYY-MM-DD format, required if --start is used)')
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.start and not args.end:
        parser.error("--end is required when --start is specified")
    
    if args.end and not args.start:
        parser.error("--start is required when --end is specified")
    
    return args

def calculate_weeks_back_dates(weeks_back):
    """Calculate date range for N weeks back"""
    today = datetime.now()
    
    # Find the most recent Sunday
    if today.weekday() == 6:
        most_recent_sunday = today
    else:
        days_since_sunday = (today.weekday() + 1) % 7
        most_recent_sunday = today - timedelta(days=days_since_sunday)
    
    # Go back the specified number of weeks
    target_week_start = most_recent_sunday - timedelta(days=7 * weeks_back)
    target_week_end = target_week_start + timedelta(days=6)  # Saturday of that week
    
    return target_week_start.strftime('%Y-%m-%d'), target_week_end.strftime('%Y-%m-%d')

# Parse command line arguments at startup
args = parse_arguments()

# Set custom dates if provided
if args.start and args.end:
    CUSTOM_START_DATE = args.start
    CUSTOM_END_DATE = args.end
    print(f"📅 Using custom date range: {args.start} to {args.end}")
elif args.weeks_back:
    CUSTOM_START_DATE, CUSTOM_END_DATE = calculate_weeks_back_dates(args.weeks_back)
    print(f"📅 Using {args.weeks_back} week(s) back: {CUSTOM_START_DATE} to {CUSTOM_END_DATE}")

# Data collection (same as original)
print("Collecting data for highlights and points table...")

# Print the date range being used
start_date, end_date = get_weekly_date_range()
print(f"📅 Using date range: {start_date} to {end_date}")

# Initialize data collection for highlights
all_player_data = {}

for login in player_logins:
    print(f"Fetching data from database for {login}...")
    
    # Get records from database
    records = get_player_records_from_db(login)
    
    if not records:
        print(f"No dedi's found for {login}!")
        all_player_data[login] = []
        continue
    
    # Deduplicate records to keep only best rank per track
    records = deduplicate_player_records(records)
    
    # Store data for highlights calculation
    all_player_data[login] = records
    print(f"Found {len(records)} unique tracks with records for {login}")

print("Data collection complete!")

# === POINTS SYSTEM CALCULATION ===
def get_challenge_info_cache():
    """Get challenge info from database and cache it"""
    conn = sqlite3.connect(DATABASE_PATH)
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

def get_competition_multiplier(total_records):
    """Calculate competition multiplier based on total records"""
    if total_records is None or total_records <= 0:
        return 0.5  # Default for unknown challenges (50% points)
    elif total_records == 1:
        return 0.1  # 10% points for solo records
    elif total_records < 5:
        return 0.2  # 20% points for 2-4 players
    elif total_records < 10:
        return 0.4  # 40% points for 5-9 players
    elif total_records < 15:
        return 0.6  # 60% points for 10-14 players
    elif total_records < 20:
        return 0.8  # 80% points for 15-19 players
    else:
        return 1.0  # 100% points for 20+ players

def calculate_points(records, challenge_cache):
    """Calculate points for a player based on their records with competition multipliers
    Base: Top1 = 5 points, Top3 = 3 points, Top5 = 2 points, Any record = 1 point
    Multiplied by competition level based on total players on each challenge"""
    points = 0.0
    
    for record in records:
        challenge_name = record.get('Challenge', '')
        rank_str = record.get('Rank', '')
        
        # Get total records for this challenge
        total_records = challenge_cache.get(challenge_name, None)
        multiplier = get_competition_multiplier(total_records)
        
        # Calculate base points
        base_points = 0
        if rank_str.isdigit():
            rank = int(rank_str)
            if rank == 1:
                base_points = 5    # Top1
            elif rank <= 3:
                base_points = 3    # Top3
            elif rank <= 5:
                base_points = 2    # Top5
            else:
                base_points = 1    # Any record
        elif rank_str:  # Non-numeric rank still counts as a record
            base_points = 1
        
        # Apply competition multiplier
        final_points = base_points * multiplier
        points += final_points
    
    return round(points, 1)  # Round to 1 decimal place

print("Generating player leaderboard table...")

# Load challenge info cache for competition multipliers
print("Loading challenge competition data...")
challenge_cache = get_challenge_info_cache()
print(f"Loaded competition data for {len(challenge_cache)} challenges")

# Calculate previous week's leaderboard for trend analysis
prev_rankings = calculate_previous_week_leaderboard()

# --- Generate CSV Table Report: Player, #Top5, #Top1, #Dedi's (last 7 days) ---
player_table = []
for login in player_logins:
    # Get records from database
    recent_records = get_player_records_from_db(login)
    
    if not recent_records:
        continue
    
    # Deduplicate records to keep only best rank per track
    recent_records = deduplicate_player_records(recent_records)
    
    # Get the latest nickname for this login
    def get_latest_nickname_for_login(login, records):
        latest_nick = login
        latest_date = ""
        
        for r in records:
            if r.get('NickName') and r.get('RecordDate', '') > latest_date:
                latest_date = r.get('RecordDate', '')
                latest_nick = r.get('NickName')
        
        return latest_nick
    
    nickname = get_latest_nickname_for_login(login, recent_records)
    total_records = len(recent_records)
    top1 = sum(1 for r in recent_records if r.get('Rank', '') == '1')
    top3 = sum(1 for r in recent_records if r.get('Rank', '').isdigit() and 1 <= int(r.get('Rank', '0')) <= 3)
    top5 = sum(1 for r in recent_records if r.get('Rank', '').isdigit() and 1 <= int(r.get('Rank', '0')) <= 5)
    points = calculate_points(recent_records, challenge_cache)
    
    # Calculate average rank
    ranks = []
    for r in recent_records:
        if r.get('Rank', '').isdigit():
            ranks.append(int(r.get('Rank', '0')))
    avg_rank = sum(ranks) / len(ranks) if ranks else 0
    
    player_table.append((nickname, top5, top3, top1, total_records, avg_rank, points, login))

# Sort by points first, then by number of Top1s, then Top3s, then Top5s descending
player_table.sort(key=lambda x: (x[6], x[3], x[2], x[1]), reverse=True)

# Add trend information after sorting (so we know current positions)
player_table_with_trends = []
for i, player in enumerate(player_table):
    nickname, top5, top3, top1, total_records, avg_rank, points, login = player
    current_rank = i + 1  # Current position (1-based)
    prev_rank = prev_rankings.get(login, None)  # Previous position
    
    # Calculate trend with bigger, bolder symbols
    trend_symbol = ""
    trend_change = 0
    if prev_rank is not None:
        trend_change = prev_rank - current_rank  # Positive = moved up, negative = moved down
        if trend_change > 0:
            trend_symbol = f"▲({trend_change})"  # Big up triangle
        elif trend_change < 0:
            trend_symbol = f"▼({abs(trend_change)})"  # Big down triangle
        else:
            trend_symbol = "■"  # No change - solid square
    else:
        trend_symbol = "NEW"  # New player this week
    
    player_table_with_trends.append((nickname, top5, top3, top1, total_records, avg_rank, points, trend_symbol))

# Use the table with trends for display
player_table = player_table_with_trends

# Write to CSV
csv_path = os.path.join(summaries_dir, 'player_top5_top3_top1_records_last7d.csv')
with open(csv_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['Player', '#Top5', '#Top3', '#Top1', '#Dedi\'s', 'Avg', 'Points', 'Trend'])
    for row in player_table:
        writer.writerow(row)
print(f"Saved player table report as {csv_path}")

# --- Generate Gaming-Style Table Image ---
# Gaming table parameters (same dimensions as original)
padding = 48
banner_height = 110
subtitle_height = 38
header_height = 62
row_height = 58
bg_color = (8, 12, 20)  # Dark cyberpunk background
img_w = 1700  # Increased width for better column spacing
content_h = header_height + (len(player_table) * row_height)
img_h = banner_height + content_h + padding * 2

final_img = Image.new('RGB', (img_w, img_h), bg_color)
draw = ImageDraw.Draw(final_img)

# Gaming-style fonts - enhanced for better readability
try:
    font_banner = ImageFont.truetype("DejaVuSans-Bold.ttf", 58)  # Bigger banner
    font_sub = ImageFont.truetype("DejaVuSans.ttf", 28)
    font_header = ImageFont.truetype("DejaVuSans-Bold.ttf", 36)  # Bigger headers
    font_points = ImageFont.truetype("DejaVuSans.ttf", 30)       # Much bigger points for better readability
    font_row = ImageFont.truetype("DejaVuSans.ttf", 32)         # Bigger row text
    font_row_bold = ImageFont.truetype("DejaVuSans-Bold.ttf", 34) # Bigger bold text
except IOError:
    try:
        font_banner = ImageFont.truetype("arial.ttf", 58)
        font_sub = ImageFont.truetype("arial.ttf", 28)
        font_header = ImageFont.truetype("arialbd.ttf", 36)
        font_points = ImageFont.truetype("arial.ttf", 30)
        font_row = ImageFont.truetype("arial.ttf", 32)
        font_row_bold = ImageFont.truetype("arialbd.ttf", 34)
    except IOError:
        font_banner = ImageFont.load_default()
        font_sub = ImageFont.load_default()
        font_header = ImageFont.load_default()
        font_points = ImageFont.load_default()
        font_row = ImageFont.load_default()
        font_row_bold = ImageFont.load_default()

# --- Gaming Banner ---
banner_text = "ĊĦ Team — Weekly Leaderboard"
bbox = draw.textbbox((0,0), banner_text, font=font_banner)
text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
banner_bg = Image.new('RGB', (img_w, banner_height), (15, 25, 40))
banner_draw = ImageDraw.Draw(banner_bg)

# Cyberpunk gradient
for i in range(banner_height-18):
    r = int(15 + (i / (banner_height-18)) * 50)
    g = int(25 + (i / (banner_height-18)) * 35)
    b = int(40 + (i / (banner_height-18)) * 65)
    banner_draw.line([(0, i), (img_w, i)], fill=(r, g, b))

# # Neon accent strips
# neon_colors = [(0, 255, 255), (255, 0, 255), (0, 255, 0), (255, 255, 0), (255, 100, 255)]
# strip_height = 1
# for i, color in enumerate(neon_colors):
#     y_pos = banner_height - 18 + (i * strip_height)
#     banner_draw.rectangle([0, y_pos, img_w, y_pos + strip_height], fill=color)

# Gaming title with subtle neon glow
text_x = (img_w - text_w) // 2
text_y = (banner_height - 18 - text_h) // 2
add_neon_glow(banner_draw, banner_text, text_x, text_y, font_banner, (255,255,255), (0,255,255), glow_size=1)
final_img.paste(banner_bg, (0,0))

# Gaming table background
list_bg = Image.new('RGB', (img_w - padding*2, content_h + padding), (25, 35, 50))
list_draw = ImageDraw.Draw(list_bg)

# Neon accent bar under header
list_draw.rectangle([(0, header_height-2), (img_w - padding*2, header_height)], fill=(0, 255, 255))

# Column positions (better spacing to use full width) - spread out more evenly
x_rank = 30
x_player = 90
x_top1 = 450
x_top3 = 580
x_top5 = 710
x_total = 840
x_avg_rank = 970
x_points = 1120
x_trend = 1280
col_xs = [x_rank, x_player, x_top1, x_top3, x_top5, x_total, x_avg_rank, x_points, x_trend, img_w-padding*2-30]

# Gaming-style header colors with subtle neon glow
header_y = 15  # Adjusted for bigger fonts
add_neon_glow(list_draw, "#", x_rank, header_y, font_header, (255, 215, 0), (255, 235, 20), glow_size=1)
add_neon_glow(list_draw, "Player", x_player, header_y, font_header, (255, 255, 255), (0, 255, 255), glow_size=1)
add_neon_glow(list_draw, "Top1", x_top1, header_y, font_header, (255, 69, 0), (255, 100, 0), glow_size=1)
add_neon_glow(list_draw, "Top3", x_top3, header_y, font_header, (30, 144, 255), (50, 164, 255), glow_size=1)
add_neon_glow(list_draw, "Top5", x_top5, header_y, font_header, (50, 205, 50), (70, 225, 70), glow_size=1)
add_neon_glow(list_draw, "Dedi's", x_total, header_y, font_header, (200, 200, 200), (220, 220, 220), glow_size=1)
add_neon_glow(list_draw, "Avg", x_avg_rank, header_y, font_header, (255, 100, 255), (255, 120, 255), glow_size=1)
add_neon_glow(list_draw, "Points", x_points, header_y, font_header, (0, 255, 255), (20, 255, 255), glow_size=1)
add_neon_glow(list_draw, "Trend", x_trend, header_y, font_header, (255, 165, 0), (255, 185, 20), glow_size=1)



# Enhanced gaming-style vertical lines with neon glow
for x in col_xs[1:-1]:
    # Draw glow effect for vertical lines
    list_draw.line([(x-18, header_height-10), (x-18, content_h+padding)], fill=(0, 150, 150), width=4)
    list_draw.line([(x-18, header_height-10), (x-18, content_h+padding)], fill=(0, 200, 200), width=3)
    list_draw.line([(x-18, header_height-10), (x-18, content_h+padding)], fill=(0, 255, 255), width=2)

# Horizontal line under header
header_bottom = header_height
list_draw.line([(30, header_bottom), (img_w - padding*2 - 30, header_bottom)], fill=(0, 255, 255), width=2)

# Gaming-style rows with subtle gradients
row_colors = [(35, 45, 65), (25, 35, 55)]  # Dark alternating colors
gradient_colors = [(40, 50, 70), (30, 40, 60)]  # Subtle gradient variations
for i, row in enumerate(player_table):
    y_offset = header_height + i * row_height
    
    # Draw base row with subtle gradient effect
    base_color = row_colors[i%2]
    gradient_color = gradient_colors[i%2]
    
    # Create subtle gradient by drawing multiple lines
    for j in range(row_height):
        ratio = j / row_height
        r = int(base_color[0] + (gradient_color[0] - base_color[0]) * ratio)
        g = int(base_color[1] + (gradient_color[1] - base_color[1]) * ratio)
        b = int(base_color[2] + (gradient_color[2] - base_color[2]) * ratio)
        list_draw.line([(0, y_offset + j), (img_w - padding*2, y_offset + j)], fill=(r, g, b))
    
    # Special highlighting for top 3 positions with subtle gradients
    if i < 3:
        # Enhanced gaming-style podium colors with subtle gradients
        highlight_colors = [(85, 70, 35), (75, 75, 75), (75, 55, 35)]  # More distinct gold, silver, bronze tints
        list_draw.rectangle([(0, y_offset), (img_w - padding*2, y_offset+row_height)], fill=highlight_colors[i])
        
        # Add subtle inner glow for podium positions
        glow_colors = [(100, 85, 45), (90, 90, 90), (90, 70, 45)]
        list_draw.rectangle([(2, y_offset+2), (img_w - padding*2-2, y_offset+row_height-2)], fill=glow_colors[i])
    
    # Smart truncation with more visible indicators for gaming leaderboard
    raw_name = str(row[0])
    max_length = 20  # Maximum chars to fit in column nicely
    
    if len(raw_name) > max_length:
        # Truncate to max_length-3 + "..." 
        nickname = raw_name[:max_length-3] + "..."
        print(f"🔤 Truncated: '{raw_name}' → '{nickname}' ({len(raw_name)} → {len(nickname)} chars)")
    else:
        nickname = raw_name
    
    # Gaming-style data colors - adjusted positioning for bigger fonts
    text_y = y_offset + 12  # Adjusted for bigger fonts
    
    # Add ranking number with special colors for top 3
    rank_num = str(i + 1)
    if i < 3:
        rank_colors = [(255, 215, 0), (192, 192, 192), (205, 127, 50)]  # Gold, silver, bronze
        list_draw.text((x_rank, text_y), rank_num, font=font_row_bold, fill=rank_colors[i])
    else:
        list_draw.text((x_rank, text_y), rank_num, font=font_row, fill=(255, 215, 0))
    
    list_draw.text((x_player, text_y), nickname, font=font_row_bold, fill=(255, 255, 255))
    list_draw.text((x_top1, text_y), str(row[3]), font=font_row_bold, fill=(255, 69, 0))
    list_draw.text((x_top3, text_y), str(row[2]), font=font_row_bold, fill=(30, 144, 255))
    list_draw.text((x_top5, text_y), str(row[1]), font=font_row_bold, fill=(50, 205, 50))
    list_draw.text((x_total, text_y), str(row[4]), font=font_row, fill=(200, 200, 200))
    list_draw.text((x_avg_rank, text_y), f"{row[5]:.1f}" if row[5] > 0 else "N/A", font=font_row, fill=(255, 100, 255))
    
    # Format points nicely (remove .0 for whole numbers)
    points_value = row[6]
    if points_value == int(points_value):
        points_text = str(int(points_value))
    else:
        points_text = str(points_value)
    list_draw.text((x_points, text_y), points_text, font=font_row_bold, fill=(0, 255, 255))
    
    # Display trend with color coding and bigger symbols
    trend_text = row[7]  # Trend is at index 7
    trend_color = (200, 200, 200)  # Default gray
    if trend_text.startswith("▲"):
        trend_color = (50, 255, 50)  # Bright green for up
    elif trend_text.startswith("▼"):
        trend_color = (255, 69, 0)   # Red for down
    elif trend_text == "NEW":
        trend_color = (255, 215, 0)  # Gold for new
    # else: gray for no change (■)
    
    # Use bold font for better visibility
    list_draw.text((x_trend, text_y), trend_text, font=font_row_bold, fill=trend_color)
    
    # Enhanced gaming-style vertical lines with subtle glow
    for x in col_xs[1:-1]:
        list_draw.line([(x-18, y_offset), (x-18, y_offset+row_height)], fill=(0, 150, 150), width=2)
        list_draw.line([(x-18, y_offset), (x-18, y_offset+row_height)], fill=(0, 255, 255), width=1)

# Apply gaming-style rounded corners with neon glow
styled_list = add_rounded_corners(list_bg)
final_img.paste(styled_list, (padding - 10, banner_height), styled_list)

# Save the gaming leaderboard
out_path = os.path.join(summaries_dir, "gaming_leaderboard.png")
final_img.save(out_path)
print(f"🎮 Gaming leaderboard saved to: {out_path}") 

# === SERVER INFO FETCHING ===
import requests
from bs4 import BeautifulSoup
import time

class ServerInfoFetcher:
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = DATABASE_PATH
        self.db_path = db_path
        
        self.base_url = "http://dedimania.net/tmstats/"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self._server_cache = {}  # Cache to avoid repeated requests

    def get_challenge_uuid(self, challenge_name):
        """Get challenge UUID from challenge_info table"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT challenge_uuid 
            FROM challenge_info 
            WHERE challenge_name = ?
        ''', (challenge_name,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return result[0]
        return None

    def fetch_server_info(self, player_login, challenge_uuid):
        """Fetch server info for a specific player and challenge"""
        cache_key = f"{player_login}_{challenge_uuid}"
        if cache_key in self._server_cache:
            return self._server_cache[cache_key]
        
        try:
            url = f"{self.base_url}?do=stat&Login={player_login}&Uid={challenge_uuid}&Show=RECORD"
            
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for "account" field in the HTML table structure
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                if len(rows) < 2:
                    continue
                
                # Look through all rows to find the one with "Account" header
                account_col_index = -1
                header_row = None
                
                for row_idx, row in enumerate(rows):
                    cells = row.find_all(['td', 'th'])
                    for col_idx, cell in enumerate(cells):
                        cell_text = cell.get_text(strip=True)
                        if cell_text == 'Account':  # Exact match for Account header
                            account_col_index = col_idx
                            header_row = row_idx
                            break
                    if account_col_index >= 0:
                        break
                
                # If found account column, look for data in subsequent rows
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
            print(f"❌ Error fetching server for {player_login}: {e}")
            self._server_cache[cache_key] = "Error"
            return "Error"

    def get_server_for_record(self, player_login, challenge_name):
        """Get server info for a player's record on a specific challenge"""
        challenge_uuid = self.get_challenge_uuid(challenge_name)
        if not challenge_uuid:
            return "No UUID"
        
        server = self.fetch_server_info(player_login, challenge_uuid)
        time.sleep(0.2)  # Small delay to be respectful
        return server

def get_player_records_with_servers(login, fetch_servers=False):
    """Get player records with optional server information"""
    records = get_player_records_from_db(login)
    if not records:
        return []
    
    records = deduplicate_player_records(records)
    
    if fetch_servers:
        print(f"🔍 Fetching server info for {len(records)} records...")
        server_fetcher = ServerInfoFetcher()
        
        for record in records:
            challenge_name = record.get('Challenge', '')
            server = server_fetcher.get_server_for_record(login, challenge_name)
            record['Server'] = server
            print(f"  📍 {challenge_name[:30]:<30} → {server}")
    
    return records

def print_detailed_player_analysis(login, include_servers=True):
    """Print detailed player record analysis with server info"""
    print(f"\n🎯 DETAILED ANALYSIS FOR: {login}")
    print("=" * 80)
    
    records = get_player_records_with_servers(login, fetch_servers=include_servers)
    if not records:
        print(f"No records found for {login}")
        return
    
    challenge_cache = get_challenge_info_cache()
    
    # Print header
    if include_servers:
        print(f"{'Date':<12} {'Challenge':<25} {'Rank':<6} {'Points':<8} {'Total':<6} {'Record':<10} {'Server':<20}")
        print("-" * 95)
    else:
        print(f"{'Date':<12} {'Challenge':<25} {'Rank':<6} {'Points':<8} {'Total':<6} {'Record':<10}")
        print("-" * 75)
    
    total_points = 0.0
    for record in records:
        date = record.get('RecordDate', '')[:10]
        challenge = record.get('Challenge', '')[:24]
        rank_str = record.get('Rank', '')
        time_str = record.get('Record', '')
        server = record.get('Server', 'N/A') if include_servers else None
        
        # Calculate points for this record
        total_records = challenge_cache.get(record.get('Challenge', ''), None)
        multiplier = get_competition_multiplier(total_records)
        
        base_points = 0
        if rank_str.isdigit():
            rank = int(rank_str)
            if rank == 1:
                base_points = 5
            elif rank <= 3:
                base_points = 3
            elif rank <= 5:
                base_points = 2
            else:
                base_points = 1
        elif rank_str:
            base_points = 1
            
        final_points = base_points * multiplier
        total_points += final_points
        
        rank_display = f"#{rank_str}" if rank_str else "N/A"
        points_display = f"{final_points:.2f}"
        total_display = str(total_records) if total_records else "N/A"
        
        if include_servers:
            print(f"{date:<12} {challenge:<25} {rank_display:<6} {points_display:<8} {total_display:<6} {time_str:<10} {server:<20}")
        else:
            print(f"{date:<12} {challenge:<25} {rank_display:<6} {points_display:<8} {total_display:<6} {time_str:<10}")
    
    print(f"\n📊 SUMMARY:")
    print(f"   Total Points: {total_points:.2f}")
    print(f"   Total Records: {len(records)}")
    
    # Server distribution (if servers were fetched)
    if include_servers:
        servers = [r.get('Server', 'Unknown') for r in records]
        server_count = Counter(servers)
        print(f"\n🏢 SERVER DISTRIBUTION:")
        for server, count in server_count.most_common():
            print(f"   {server}: {count} records ({count/len(records)*100:.1f}%)")

 