#!/usr/bin/env python3
"""
Server Preference Analysis Script
Analyzes player server preferences over the last 2 months with detailed breakdowns and visual output
"""

import sqlite3
import os
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from PIL import Image, ImageDraw, ImageFont

class ServerAnalyzer:
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
    
    def analyze_server_preferences(self, months_back=2, min_records=5):
        """Analyze server preferences for all players"""
        print(f"🔍 Analyzing server preferences for the last {months_back} months...")
        
        start_date, end_date = self.get_date_range(months_back)
        print(f"📅 Date range: {start_date} to {end_date[:10]}")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Query for record counts per player-server combination (including improvements)
        cursor.execute('''
            SELECT player_login, server, 
                   COUNT(*) as total_records,
                   COUNT(DISTINCT Challenge) as unique_tracks,
                   COUNT(DISTINCT DATE(RecordDate)) as days_played
            FROM dedimania_records 
            WHERE RecordDate >= ? AND RecordDate <= ?
            AND server IS NOT NULL AND server != ''
            GROUP BY player_login, server
            HAVING total_records >= ?
            ORDER BY player_login, total_records DESC
        ''', (start_date, end_date, min_records))
        
        raw_data = cursor.fetchall()
        conn.close()
        
        # Process data into player-centric structure
        player_data = defaultdict(list)
        for login, server, total_records, unique_tracks, days in raw_data:
            improvements = total_records - unique_tracks  # Records beyond first attempt per track
            player_data[login].append({
                'server': server,
                'total_records': total_records,
                'unique_tracks': unique_tracks,
                'improvements': improvements,
                'days': days
            })
        
        print(f"📊 Found {len(player_data)} players with server activity")
        return player_data, start_date, end_date[:10]
    
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
    
    def analyze_preferences(self, player_data):
        """Analyze and format server preferences"""
        results = []
        
        for login, servers in player_data.items():
            nickname = self.get_player_nickname(login)
            total_records = sum(s['total_records'] for s in servers)
            total_unique_tracks = sum(s['unique_tracks'] for s in servers)
            total_improvements = sum(s['improvements'] for s in servers)
            
            # Calculate unique days across all servers (avoid double counting)
            # We need to query the database again to get unique days for this player
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            start_date, end_date = self.get_date_range()
            cursor.execute('''
                SELECT COUNT(DISTINCT DATE(RecordDate)) as unique_days
                FROM dedimania_records 
                WHERE player_login = ? AND RecordDate >= ? AND RecordDate <= ?
                AND server IS NOT NULL AND server != ''
            ''', (login, start_date, end_date))
            result = cursor.fetchone()
            total_days = result[0] if result else 0
            conn.close()
            
            # Sort by total records (primary) and days (secondary)
            servers_by_records = sorted(servers, key=lambda x: x['total_records'], reverse=True)
            servers_by_days = sorted(servers, key=lambda x: x['days'], reverse=True)
            
            # Find top server by records
            top_server_records = servers_by_records[0]
            records_percentage = (top_server_records['total_records'] / total_records) * 100
            
            # Find top server by days
            top_server_days = servers_by_days[0]
            days_percentage = (top_server_days['days'] / total_days) * 100
            
            # Check for ties (within 10% or same count)
            tied_servers_records = []
            tied_servers_days = []
            
            for server in servers_by_records:
                if (server['total_records'] == top_server_records['total_records'] or 
                    abs(server['total_records'] - top_server_records['total_records']) / top_server_records['total_records'] <= 0.1):
                    tied_servers_records.append(server)
                else:
                    break
            
            for server in servers_by_days:
                if (server['days'] == top_server_days['days'] or 
                    abs(server['days'] - top_server_days['days']) / top_server_days['days'] <= 0.1):
                    tied_servers_days.append(server)
                else:
                    break
            
            results.append({
                'login': login,
                'nickname': nickname,
                'total_records': total_records,
                'total_unique_tracks': total_unique_tracks,
                'total_improvements': total_improvements,
                'total_days': total_days,
                'servers': servers,
                'top_server_records': top_server_records,
                'top_server_days': top_server_days,
                'records_percentage': records_percentage,
                'days_percentage': days_percentage,
                'tied_servers_records': tied_servers_records,
                'tied_servers_days': tied_servers_days
            })
        
        # Sort by total activity (records + days)
        results.sort(key=lambda x: x['total_records'] + x['total_days'], reverse=True)
        return results
    
    def generate_text_report(self, results, start_date, end_date):
        """Generate detailed text report"""
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("🏢 SERVER PREFERENCE ANALYSIS")
        report_lines.append(f"📅 Period: {start_date} to {end_date}")
        report_lines.append(f"👥 Players analyzed: {len(results)}")
        report_lines.append("=" * 80)
        report_lines.append("")
        
        for i, player in enumerate(results, 1):
            nickname = player['nickname'][:25]  # Limit length
            total_records = player['total_records']
            total_unique_tracks = player['total_unique_tracks']
            total_improvements = player['total_improvements']
            total_days = player['total_days']
            
            # Calculate enhanced days for display (but cap at reasonable limit)
            improvement_bonus = int(total_improvements * 0.1)
            enhanced_days = total_days + improvement_bonus
            enhanced_days = min(enhanced_days, 62)  # Cap at 2 months max
            report_lines.append(f"{i:2d}. {nickname:<25} | {total_unique_tracks:4d} dedi's, {enhanced_days:3d} days active")
            
            # Most records breakdown
            report_lines.append(f"    📊 RECORDS:")
            for server_data in player['servers'][:3]:  # Top 3 servers
                server = server_data['server'][:20]
                records = server_data['total_records']
                unique_tracks = server_data['unique_tracks']
                percentage = (records / total_records) * 100
                report_lines.append(f"       {server:<20} {records:4d} records ({unique_tracks} dedi's) ({percentage:5.1f}%)")
            
            # Most days breakdown
            report_lines.append(f"    📅 DAYS PLAYED:")
            servers_by_days = sorted(player['servers'], key=lambda x: x['days'], reverse=True)
            for server_data in servers_by_days[:3]:  # Top 3 servers
                server = server_data['server'][:20]
                days = server_data['days']
                percentage = (days / total_days) * 100
                report_lines.append(f"       {server:<20} {days:4d} days    ({percentage:5.1f}%)")
            
            report_lines.append("")
        
        return "\n".join(report_lines)
    
    def generate_visual_report(self, results, start_date, end_date, output_file='server_analysis.png'):
        """Generate clean, modern visual report"""
        print("🎨 Generating clean visual report...")
        
        # Clean, modern dimensions
        width = 1000
        height = min(1400, 180 + len(results) * 45)
        
        # Create image with clean dark theme
        img = Image.new('RGB', (width, height), (22, 27, 34))
        draw = ImageDraw.Draw(img)
        
        # Load fonts
        try:
            font_title = ImageFont.truetype("DejaVuSans-Bold.ttf", 32)
            font_subtitle = ImageFont.truetype("DejaVuSans-Bold.ttf", 18)
            font_header = ImageFont.truetype("DejaVuSans-Bold.ttf", 16)
            font_text = ImageFont.truetype("DejaVuSans-Bold.ttf", 14)
            font_rank = ImageFont.truetype("DejaVuSans-Bold.ttf", 18)
        except:
            try:
                font_title = ImageFont.truetype("arialbd.ttf", 32)
                font_subtitle = ImageFont.truetype("arialbd.ttf", 18)
                font_header = ImageFont.truetype("arialbd.ttf", 16)
                font_text = ImageFont.truetype("arialbd.ttf", 14)
                font_rank = ImageFont.truetype("arialbd.ttf", 18)
            except:
                font_title = ImageFont.load_default()
                font_subtitle = font_header = font_text = font_rank = font_title
        
        # Clean, professional color scheme
        colors = {
            'title': (255, 255, 255),
            'subtitle': (156, 163, 175),
            'header': (209, 213, 219),
            'text': (156, 163, 175),
            'rank_gold': (251, 191, 36),
            'rank_silver': (156, 163, 175),
            'rank_bronze': (217, 119, 6),
            'rank_normal': (107, 114, 128),
            'accent': (59, 130, 246),
            'records': (239, 68, 68),
            'days': (34, 197, 94),
            'server': (168, 85, 247)
        }
        
        y = 30
        
        # Clean title
        title_text = "🎮 Server Preferences"
        title_bbox = draw.textbbox((0, 0), title_text, font=font_title)
        title_width = title_bbox[2] - title_bbox[0]
        draw.text((width//2 - title_width//2, y), title_text, fill=colors['title'], font=font_title)
        y += 45
        
        # Subtitle
        subtitle_text = f"{start_date} to {end_date} • {len(results)} players"
        subtitle_bbox = draw.textbbox((0, 0), subtitle_text, font=font_subtitle)
        subtitle_width = subtitle_bbox[2] - subtitle_bbox[0]
        draw.text((width//2 - subtitle_width//2, y), subtitle_text, fill=colors['subtitle'], font=font_subtitle)
        y += 40
        
        # Clean headers
        headers = ["Rank", "Player", "Records", "Days", "Top Server", "Preference"]
        x_positions = [40, 100, 250, 320, 390, 600]
        
        # Header separator
        draw.line([(30, y), (width-30, y)], fill=colors['accent'], width=2)
        y += 15
        
        for i, header in enumerate(headers):
            draw.text((x_positions[i], y), header, fill=colors['header'], font=font_header)
        y += 30
        
        # Subtle separator
        draw.line([(30, y), (width-30, y)], fill=(55, 65, 81), width=1)
        y += 15
        
        # Clean player data
        for i, player in enumerate(results[:25]):
            # Subtle alternating backgrounds
            if i % 2 == 0:
                draw.rectangle([(30, y - 5), (width - 30, y + 30)], fill=(31, 41, 55))
            
            rank = str(i + 1)
            nickname = player['nickname'][:16]
            total_records = str(player['total_records'])
            total_days = str(player['total_days'])  # Clean days without artificial enhancement
            
            # Get top server
            top_server = player['servers'][0]
            server_name = top_server['server'][:12]
            server_records = top_server['total_records']
            server_pct = (server_records / player['total_records']) * 100
            
            # Clean rank colors
            if i == 0:
                rank_color = colors['rank_gold']
            elif i == 1:
                rank_color = colors['rank_silver']
            elif i == 2:
                rank_color = colors['rank_bronze']
            else:
                rank_color = colors['rank_normal']
            
            # Draw clean data
            draw.text((x_positions[0], y), rank, fill=rank_color, font=font_rank)
            draw.text((x_positions[1], y), nickname, fill=colors['text'], font=font_text)
            draw.text((x_positions[2], y), total_records, fill=colors['records'], font=font_text)
            draw.text((x_positions[3], y), total_days, fill=colors['days'], font=font_text)
            draw.text((x_positions[4], y), server_name, fill=colors['server'], font=font_text)
            draw.text((x_positions[5], y), f"{server_records} ({server_pct:.0f}%)", fill=colors['text'], font=font_text)
            
            y += 35
        
        # Save image
        img.save(output_file)
        print(f"✅ Clean visual report saved to: {output_file}")
        return output_file
    
    def run_analysis(self, months_back=2, min_records=5, output_prefix="server_analysis"):
        """Run complete server analysis"""
        # Get data
        player_data, start_date, end_date = self.analyze_server_preferences(months_back, min_records)
        
        if not player_data:
            print("❌ No data found for the specified period")
            return
        
        # Analyze preferences
        results = self.analyze_preferences(player_data)
        
        # Generate text report
        text_report = self.generate_text_report(results, start_date, end_date)
        text_file = f"{output_prefix}.txt"
        with open(text_file, 'w', encoding='utf-8') as f:
            f.write(text_report)
        print(f"📄 Text report saved to: {text_file}")
        
        # Generate visual report
        visual_file = f"{output_prefix}.png"
        self.generate_visual_report(results, start_date, end_date, visual_file)
        
        # Print summary
        print("\n🎯 SUMMARY:")
        print(f"   • {len(results)} players analyzed")
        print(f"   • Period: {start_date} to {end_date}")
        print(f"   • Minimum records threshold: {min_records}")
        
        # Top 5 most active players
        print(f"\n🏆 TOP 5 MOST ACTIVE PLAYERS:")
        for i, player in enumerate(results[:5], 1):
            nickname = player['nickname'][:20]
            records = player['total_records']
            tracks = player['total_unique_tracks']
            improvements = player['total_improvements']
            days = player['total_days']
            enhanced_days = days + int(improvements * 0.1)
            top_server = player['top_server_records']['server'][:15]
            print(f"   {i}. {nickname:<20} | {tracks:4d} dedi's, {enhanced_days:3d} days active | {top_server}")

if __name__ == "__main__":
    analyzer = ServerAnalyzer()
    analyzer.run_analysis(months_back=2, min_records=5)
