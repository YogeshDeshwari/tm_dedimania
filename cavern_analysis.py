#!/usr/bin/env python3
"""
Cavern Server Analysis Script
Analyzes player activity specifically on tzig_server (displayed as "Cavern") over the last 2 months
"""

import sqlite3
import os
from datetime import datetime, timedelta
from collections import defaultdict
from PIL import Image, ImageDraw, ImageFont

class CavernAnalyzer:
    def __init__(self, db_path=None):
        if db_path is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(script_dir, 'dedimania_history_master.db')
        self.db_path = db_path
        
    def get_date_range(self, months_back=2):
        """Calculate date range for the last N months"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=months_back * 30)  # Approximate 2 months
        return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d %H:%M:%S')
    
    def analyze_cavern_activity(self, months_back=2, min_records=3):
        """Analyze player activity specifically on tzig_server (Cavern)"""
        print(f"🏔️ Analyzing Cavern server activity for the last {months_back} months...")
        
        start_date, end_date = self.get_date_range(months_back)
        print(f"📅 Date range: {start_date} to {end_date[:10]}")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Query for records specifically on tzig_server
        cursor.execute('''
            SELECT player_login, 
                   COUNT(*) as total_records,
                   COUNT(DISTINCT Challenge) as unique_tracks,
                   COUNT(DISTINCT DATE(RecordDate)) as days_active,
                   MIN(RecordDate) as first_record,
                   MAX(RecordDate) as last_record
            FROM dedimania_records 
            WHERE server = 'tzig_server'
            AND RecordDate >= ? AND RecordDate <= ?
            GROUP BY player_login
            HAVING total_records >= ?
            ORDER BY total_records DESC, days_active DESC
        ''', (start_date, end_date, min_records))
        
        raw_data = cursor.fetchall()
        conn.close()
        
        print(f"🏔️ Found {len(raw_data)} players active on Cavern server")
        return raw_data, start_date, end_date[:10]
    
    def get_player_nickname(self, login):
        """Get the latest nickname for a player login"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT NickName FROM dedimania_records 
            WHERE player_login = ? AND NickName IS NOT NULL AND NickName != ''
            ORDER BY RecordDate DESC LIMIT 1
        ''', (login,))
        
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else login
    
    def process_cavern_data(self, raw_data):
        """Process and format cavern server data"""
        results = []
        
        for login, total_records, unique_tracks, days_active, first_record, last_record in raw_data:
            nickname = self.get_player_nickname(login)
            improvements = total_records - unique_tracks
            
            # Calculate activity span
            first_dt = datetime.strptime(first_record[:10], '%Y-%m-%d')
            last_dt = datetime.strptime(last_record[:10], '%Y-%m-%d')
            activity_span = (last_dt - first_dt).days + 1
            
            results.append({
                'login': login,
                'nickname': nickname,
                'total_records': total_records,
                'unique_tracks': unique_tracks,
                'improvements': improvements,
                'days_active': days_active,
                'first_record': first_record[:10],
                'last_record': last_record[:10],
                'activity_span': activity_span,
                'records_per_day': round(total_records / max(days_active, 1), 1)
            })
        
        return results
    
    def generate_text_report(self, results, start_date, end_date):
        """Generate detailed text report for Cavern server"""
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("🏔️ CAVERN SERVER ACTIVITY ANALYSIS")
        report_lines.append(f"📅 Period: {start_date} to {end_date}")
        report_lines.append(f"👥 Players analyzed: {len(results)}")
        report_lines.append("=" * 80)
        report_lines.append("")
        
        for i, player in enumerate(results, 1):
            nickname = player['nickname'][:25]
            total_records = player['total_records']
            unique_tracks = player['unique_tracks']
            improvements = player['improvements']
            days_active = player['days_active']
            records_per_day = player['records_per_day']
            
            report_lines.append(f"{i:2d}. {nickname:<25} | {total_records:4d} records ({unique_tracks} dedi's, {improvements} improvements) | {days_active:3d} days active")
            report_lines.append(f"    📊 Activity: {records_per_day} records/day | First: {player['first_record']} | Last: {player['last_record']}")
            report_lines.append("")
        
        return "\n".join(report_lines)
    
    def generate_visual_report(self, results, start_date, end_date, output_file='cavern_analysis.png'):
        """Generate visual report for Cavern server activity"""
        print("🎨 Generating Cavern visual report...")
        
        # Image dimensions
        width = 1400
        height = min(2000, 200 + len(results) * 80)
        
        # Create image with mountain/cavern theme
        img = Image.new('RGB', (width, height), (15, 25, 35))
        draw = ImageDraw.Draw(img)
        
        # Add gradient background with cavern theme
        for y in range(height):
            gradient_factor = y / height
            r = int(15 + gradient_factor * 20)
            g = int(25 + gradient_factor * 30)
            b = int(35 + gradient_factor * 40)
            draw.line([(0, y), (width, y)], fill=(r, g, b))
        
        # Load fonts
        try:
            font_title = ImageFont.truetype("DejaVuSans-Bold.ttf", 48)
            font_subtitle = ImageFont.truetype("DejaVuSans-Bold.ttf", 26)
            font_header = ImageFont.truetype("DejaVuSans-Bold.ttf", 22)
            font_text = ImageFont.truetype("DejaVuSans-Bold.ttf", 18)
            font_small = ImageFont.truetype("DejaVuSans-Bold.ttf", 15)
            font_rank = ImageFont.truetype("DejaVuSans-Bold.ttf", 24)
        except:
            try:
                font_title = ImageFont.truetype("arialbd.ttf", 48)
                font_subtitle = ImageFont.truetype("arialbd.ttf", 26)
                font_header = ImageFont.truetype("arialbd.ttf", 22)
                font_text = ImageFont.truetype("arialbd.ttf", 18)
                font_small = ImageFont.truetype("arialbd.ttf", 15)
                font_rank = ImageFont.truetype("arialbd.ttf", 24)
            except:
                font_title = ImageFont.load_default()
                font_subtitle = font_header = font_text = font_small = font_rank = font_title
        
        # Cavern-themed colors
        colors = {
            'title': (100, 200, 255),       # Ice blue
            'subtitle': (255, 215, 0),      # Gold
            'header': (255, 255, 255),      # White
            'text': (220, 220, 220),        # Light gray
            'rank_gold': (255, 215, 0),     # Gold
            'rank_silver': (192, 192, 192), # Silver
            'rank_bronze': (205, 127, 50),  # Bronze
            'rank_normal': (150, 200, 255), # Light blue
            'records': (255, 140, 0),       # Dark orange
            'tracks': (100, 255, 200),      # Aqua
            'days': (150, 255, 150),        # Light green
            'improvements': (255, 180, 100), # Light orange
            'separator': (100, 200, 255),   # Ice blue
        }
        
        y = 40
        
        # Header background
        header_bg_height = 120
        draw.rectangle([(0, 0), (width, header_bg_height)], fill=(30, 45, 65))
        
        # Title
        title_text = "🏔️ CAVERN SERVER ACTIVITY"
        title_bbox = draw.textbbox((0, 0), title_text, font=font_title)
        title_width = title_bbox[2] - title_bbox[0]
        draw.text((width//2 - title_width//2, y), title_text, fill=colors['title'], font=font_title)
        y += 65
        
        # Subtitle
        subtitle_text = f"📅 {start_date} to {end_date} | 👥 {len(results)} Players"
        subtitle_bbox = draw.textbbox((0, 0), subtitle_text, font=font_subtitle)
        subtitle_width = subtitle_bbox[2] - subtitle_bbox[0]
        draw.text((width//2 - subtitle_width//2, y), subtitle_text, fill=colors['subtitle'], font=font_subtitle)
        y += 60
        
        # Headers
        headers = ["#", "Player", "Records", "Dedi's", "Improvements", "Days Active", "Records/Day"]
        x_positions = [60, 120, 300, 400, 500, 620, 750]
        
        # Header background
        header_y = y
        draw.rectangle([(30, header_y - 10), (width - 30, header_y + 45)], fill=(40, 55, 75))
        
        for i, header in enumerate(headers):
            draw.text((x_positions[i], y), header, fill=colors['header'], font=font_header)
        y += 50
        
        # Separator line
        for offset in range(3):
            draw.line([(40, y + offset), (width-40, y + offset)], fill=colors['separator'], width=1)
        y += 25
        
        # Player data
        for i, player in enumerate(results[:25]):  # Show top 25 players
            # Alternating row backgrounds
            row_bg_color = (25, 35, 50) if i % 2 == 0 else (20, 30, 45)
            draw.rectangle([(30, y - 5), (width - 30, y + 65)], fill=row_bg_color)
            
            rank = str(i + 1)
            nickname = player['nickname'][:18]
            total_records = str(player['total_records'])
            unique_tracks = str(player['unique_tracks'])
            improvements = str(player['improvements'])
            days_active = str(player['days_active'])
            records_per_day = str(player['records_per_day'])
            
            # Rank colors
            if i == 0:
                rank_color = colors['rank_gold']
                rank_font = font_rank
            elif i == 1:
                rank_color = colors['rank_silver']
                rank_font = font_rank
            elif i == 2:
                rank_color = colors['rank_bronze']
                rank_font = font_rank
            else:
                rank_color = colors['rank_normal']
                rank_font = font_text
            
            # Draw data
            draw.text((x_positions[0], y + 10), rank, fill=rank_color, font=rank_font)
            draw.text((x_positions[1], y + 10), nickname, fill=colors['header'], font=font_text)
            draw.text((x_positions[2], y + 10), total_records, fill=colors['records'], font=font_text)
            draw.text((x_positions[3], y + 10), unique_tracks, fill=colors['tracks'], font=font_text)
            draw.text((x_positions[4], y + 10), improvements, fill=colors['improvements'], font=font_text)
            draw.text((x_positions[5], y + 10), days_active, fill=colors['days'], font=font_text)
            draw.text((x_positions[6], y + 10), records_per_day, fill=colors['text'], font=font_text)
            
            y += 70
        
        # Save image
        img.save(output_file)
        print(f"✅ Cavern visual report saved to: {output_file}")
        return output_file
    
    def run_analysis(self, months_back=2, min_records=3, output_prefix="cavern_analysis"):
        """Run complete Cavern server analysis"""
        # Get data
        raw_data, start_date, end_date = self.analyze_cavern_activity(months_back, min_records)
        
        if not raw_data:
            print("❌ No data found for Cavern server in the specified period")
            return
        
        # Process data
        results = self.process_cavern_data(raw_data)
        
        # Generate text report
        text_report = self.generate_text_report(results, start_date, end_date)
        text_file = f"{output_prefix}.txt"
        with open(text_file, 'w', encoding='utf-8') as f:
            f.write(text_report)
        print(f"📄 Cavern text report saved to: {text_file}")
        
        # Generate visual report
        visual_file = f"{output_prefix}.png"
        self.generate_visual_report(results, start_date, end_date, visual_file)
        
        # Print summary
        print("\n🏔️ CAVERN SERVER SUMMARY:")
        print(f"   • {len(results)} players analyzed")
        print(f"   • Period: {start_date} to {end_date}")
        print(f"   • Minimum records threshold: {min_records}")
        
        # Top 5 most active players on Cavern
        print(f"\n🏆 TOP 5 MOST ACTIVE ON CAVERN:")
        for i, player in enumerate(results[:5], 1):
            nickname = player['nickname'][:20]
            records = player['total_records']
            tracks = player['unique_tracks']
            days = player['days_active']
            rate = player['records_per_day']
            print(f"   {i}. {nickname:<20} | {records:4d} records ({tracks} dedi's), {days:3d} days active | {rate} rec/day")

if __name__ == "__main__":
    analyzer = CavernAnalyzer()
    analyzer.run_analysis(months_back=2, min_records=3)
