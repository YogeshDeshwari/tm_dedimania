import streamlit as st
import os
import sys
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
from PIL import Image
from collections import defaultdict, Counter

# Configure Streamlit page
st.set_page_config(
    page_title="🏁 TrackMania Team Stats",
    page_icon="🏁",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state for date filters
if 'dashboard_start_date' not in st.session_state:
    st.session_state.dashboard_start_date = None
if 'dashboard_end_date' not in st.session_state:
    st.session_state.dashboard_end_date = None

if 'stats_start_date' not in st.session_state:
    st.session_state.stats_start_date = None
if 'stats_end_date' not in st.session_state:
    st.session_state.stats_end_date = None

# Add the backend directories to Python path
backend_path = os.path.join(os.path.dirname(__file__), 'backend')
sys.path.append(backend_path)
sys.path.append(os.path.join(backend_path, 'Final_Weekly_stats'))
sys.path.append(os.path.join(backend_path, 'database'))

# Import your existing modules
try:
    from Final_Weekly_stats.weekly_team_stats import WeeklyStatsGenerator
    from Final_Weekly_stats.gaming_leaderboard import *
    from database.dedimania_fetch_to_sqlite import *
except ImportError as e:
    st.error(f"Error importing modules: {e}")
    st.info("Make sure all backend files are in the correct directory structure")

# Database path
DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'dedimania_history_master.db')

# Custom CSS for better styling - ENHANCED BEAUTIFUL DESIGN
st.markdown("""
<style>
    /* Main theme and colors */
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
        padding: 1.5rem 1.5rem;
        border-radius: 15px;
        margin-bottom: 1.5rem;
        text-align: center;
        color: white;
        box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        position: relative;
        overflow: hidden;
    }
    
    .main-header::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: linear-gradient(45deg, rgba(255,255,255,0.1) 25%, transparent 25%), 
                    linear-gradient(-45deg, rgba(255,255,255,0.1) 25%, transparent 25%), 
                    linear-gradient(45deg, transparent 75%, rgba(255,255,255,0.1) 75%), 
                    linear-gradient(-45deg, transparent 75%, rgba(255,255,255,0.1) 75%);
        background-size: 20px 20px;
        background-position: 0 0, 0 10px, 10px -10px, -10px 0px;
        animation: move 20s linear infinite;
    }
    
    @keyframes move {
        0% { background-position: 0 0, 0 10px, 10px -10px, -10px 0px; }
        100% { background-position: 20px 20px, 20px 30px, 30px 10px, 10px 20px; }
    }
    
    .main-header h1 {
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.3);
        position: relative;
        z-index: 1;
    }
    
    .main-header p {
        font-size: 1rem;
        font-weight: 400;
        opacity: 0.9;
        position: relative;
        z-index: 1;
        margin: 0;
    }
    
    /* Enhanced stat cards */
    .stat-card {
        background: linear-gradient(145deg, #ffffff 0%, #f8f9fa 100%);
        padding: 1.5rem;
        border-radius: 15px;
        border: none;
        margin: 1rem 0;
        box-shadow: 0 8px 25px rgba(0,0,0,0.1);
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    }
    
    .stat-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 4px;
        height: 100%;
        background: linear-gradient(to bottom, #007bff, #0056b3);
        border-radius: 0 15px 15px 0;
    }
    
    .stat-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 15px 35px rgba(0,0,0,0.15);
    }
    
    .success-card::before {
        background: linear-gradient(to bottom, #28a745, #20c997);
    }
    
    .warning-card::before {
        background: linear-gradient(to bottom, #ffc107, #fd7e14);
    }
    
    .error-card::before {
        background: linear-gradient(to bottom, #dc3545, #e83e8c);
    }
    
    /* Beautiful champion cards */
    .champion-card {
        background: linear-gradient(135deg, #ff6b6b 0%, #ee5a52 30%, #ff8a80 100%);
        color: white;
        padding: 2rem;
        border-radius: 20px;
        margin: 1rem 0;
        box-shadow: 0 15px 35px rgba(255, 107, 107, 0.3);
        position: relative;
        overflow: hidden;
        transition: all 0.3s ease;
    }
    
    .champion-card:nth-child(2) {
        background: linear-gradient(135deg, #4ecdc4 0%, #44a08d 30%, #6dd5ed 100%);
        box-shadow: 0 15px 35px rgba(78, 205, 196, 0.3);
    }
    
    .champion-card:nth-child(3) {
        background: linear-gradient(135deg, #a8edea 0%, #fed6e3 30%, #d299c2 100%);
        box-shadow: 0 15px 35px rgba(168, 237, 234, 0.3);
    }
    
    .champion-card::before {
        content: '';
        position: absolute;
        top: -50%;
        right: -50%;
        width: 100%;
        height: 100%;
        background: radial-gradient(circle, rgba(255,255,255,0.2) 0%, transparent 70%);
        animation: shimmer 3s ease-in-out infinite;
    }
    
    @keyframes shimmer {
        0%, 100% { transform: rotate(0deg) scale(1); opacity: 0.3; }
        50% { transform: rotate(180deg) scale(1.1); opacity: 0.1; }
    }
    
    .champion-card:hover {
        transform: translateY(-8px) scale(1.02);
        box-shadow: 0 20px 40px rgba(0,0,0,0.2);
    }
    
    .champion-card h2 {
        font-size: 1.8rem;
        margin: 0.5rem 0;
        font-weight: 700;
    }
    
    .champion-card h3 {
        font-size: 1.2rem;
        margin-bottom: 1rem;
        opacity: 0.9;
        font-weight: 500;
    }
    
    /* Enhanced stat highlights - COMPACT VERSION */
    .stat-highlight {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem 0.8rem;
        border-radius: 10px;
        text-align: center;
        margin: 0.5rem 0;
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    }
    
    .stat-highlight::after {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
        animation: slide 2s infinite;
    }
    
    @keyframes slide {
        0% { left: -100%; }
        100% { left: 100%; }
    }
    
    .stat-highlight:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(102, 126, 234, 0.4);
    }
    
    .stat-highlight h3 {
        font-size: 1.6rem;
        margin: 0.2rem 0;
        font-weight: 700;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.2);
    }
    
    .stat-highlight p {
        font-size: 0.85rem;
        margin: 0;
        opacity: 0.95;
        font-weight: 500;
    }
    
    /* Compact rivalry table */
    .rivalry-table {
        background: linear-gradient(145deg, #ffffff 0%, #f8f9fa 100%);
        border-radius: 15px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 8px 25px rgba(0,0,0,0.1);
        overflow: hidden;
    }
    
    .rivalry-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 1rem;
        margin: 0.5rem 0;
        background: linear-gradient(145deg, #fff 0%, #f1f3f4 100%);
        border-radius: 10px;
        border-left: 4px solid #ff6b6b;
        transition: all 0.3s ease;
    }
    
    .rivalry-row:hover {
        transform: translateX(5px);
        box-shadow: 0 5px 15px rgba(255, 107, 107, 0.2);
    }
    
    .rivalry-players {
        font-weight: 700;
        color: #2c3e50;
        font-size: 1.1rem;
    }
    
    .rivalry-score {
        font-weight: 600;
        color: #e74c3c;
        font-size: 1rem;
    }
    
    .rivalry-battles {
        color: #7f8c8d;
        font-size: 0.9rem;
    }
    
    /* Enhanced sidebar */
    .sidebar .sidebar-content {
        background: linear-gradient(180deg, #f8f9fa 0%, #e9ecef 100%);
        border-radius: 15px;
        padding: 1rem;
    }
    
    /* Beautiful buttons - COMPACT VERSION WITH PERFECT ALIGNMENT */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 6px;
        padding: 0.4rem 0.7rem;
        font-weight: 500;
        font-size: 0.75rem;
        transition: all 0.3s ease;
        box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
        height: 2.5rem;
        min-height: 2.5rem;
        margin-top: 1.6rem;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        background: linear-gradient(135deg, #764ba2 0%, #667eea 100%);
    }
    
    /* Even smaller buttons for quick filters */
    .stButton > button[kind="secondary"] {
        padding: 0.3rem 0.6rem;
        font-size: 0.7rem;
        height: 2.3rem;
        min-height: 2.3rem;
        margin-top: 1.6rem;
    }
    
    /* Align date inputs properly */
    .stDateInput > div > div > input {
        height: 2.5rem;
    }
    
    /* Perfect alignment container */
    .date-filter-container {
        display: flex;
        align-items: end;
        gap: 1rem;
    }
    
    /* Enhanced metrics - COMPACT VERSION */
    .metric-container {
        background: linear-gradient(145deg, #ffffff 0%, #f8f9fa 100%);
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        margin: 0.3rem 0;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        transition: all 0.3s ease;
        border-top: 3px solid #667eea;
    }
    
    .metric-container:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 18px rgba(0,0,0,0.15);
    }
    
    .metric-container h3 {
        font-size: 1.4rem;
        margin: 0.2rem 0;
        font-weight: 600;
    }
    
    .metric-container p {
        font-size: 0.8rem;
        margin: 0;
        font-weight: 500;
    }
    
    /* Enhanced dataframes */
    .dataframe {
        border-radius: 15px;
        overflow: hidden;
        box-shadow: 0 8px 25px rgba(0,0,0,0.1);
    }
    
    /* Section headers */
    .section-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem 2rem;
        border-radius: 15px;
        margin: 2rem 0 1rem 0;
        text-align: center;
        box-shadow: 0 8px 25px rgba(102, 126, 234, 0.3);
    }
    
    .section-header h2 {
        margin: 0;
        font-weight: 700;
        font-size: 1.8rem;
    }
    
    /* Page containers */
    .page-container {
        padding: 2rem;
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        border-radius: 20px;
        margin: 1rem 0;
        min-height: 100vh;
    }
    
    /* Enhanced info boxes */
    .info-box {
        background: linear-gradient(135deg, #74b9ff 0%, #0984e3 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 15px;
        margin: 1rem 0;
        box-shadow: 0 8px 25px rgba(116, 185, 255, 0.3);
        border-left: 5px solid #00b894;
    }
    
    /* Responsive design */
    @media (max-width: 768px) {
        .main-header {
            padding: 1rem;
        }
        
        .main-header h1 {
            font-size: 1.8rem;
        }
        
        .main-header p {
            font-size: 0.9rem;
        }
        
        .champion-card {
            padding: 1.5rem;
        }
        
        .stat-highlight {
            padding: 0.8rem 0.6rem;
        }
        
        .stat-highlight h3 {
            font-size: 1.4rem;
        }
        
        .stat-highlight p {
            font-size: 0.8rem;
        }
    }
</style>
""", unsafe_allow_html=True)

def get_database_info():
    """Get basic database information"""
    try:
        if not os.path.exists(DATABASE_PATH):
            return {"exists": False, "records": 0, "players": 0, "last_update": "Never"}
        
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # Get total records
        cursor.execute("SELECT COUNT(*) FROM dedimania_records")
        total_records = cursor.fetchone()[0]
        
        # Get unique players
        cursor.execute("SELECT COUNT(DISTINCT player_login) FROM dedimania_records")
        unique_players = cursor.fetchone()[0]
        
        # Get last update
        cursor.execute("SELECT MAX(fetch_timestamp) FROM dedimania_records")
        last_update = cursor.fetchone()[0] or "Never"
        
        conn.close()
        
        return {
            "exists": True,
            "records": total_records,
            "players": unique_players,
            "last_update": last_update
        }
    except Exception as e:
        return {"exists": False, "error": str(e)}

def get_date_range_from_db():
    """Get the min and max dates from database"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT MIN(DATE(RecordDate)), MAX(DATE(RecordDate)) FROM dedimania_records")
        min_date, max_date = cursor.fetchone()
        conn.close()
        
        if min_date and max_date:
            min_date = datetime.strptime(min_date, '%Y-%m-%d').date()
            max_date = datetime.strptime(max_date, '%Y-%m-%d').date()
            return min_date, max_date
        else:
            fallback_date = datetime.now().date()
            return fallback_date - timedelta(days=30), fallback_date
    except:
        fallback_date = datetime.now().date()
        return fallback_date - timedelta(days=30), fallback_date



def main():
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>🏁 ĊĦ Team TrackMania Statistics Dashboard</h1>
        <p>Weekly leaderboards, player statistics, and performance analytics</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar navigation
    st.sidebar.title("📊 Navigation")
    page = st.sidebar.selectbox("Choose a page:", [
        "🏠 Dashboard", 
        "📈 Team Statistics",
        "🔄 Database Management",
        "📊 Player Analytics"
    ])
    
    # Database info in sidebar
    st.sidebar.markdown("---")
    st.sidebar.subheader("📊 Database Status")
    db_info = get_database_info()
    
    if db_info["exists"]:
        st.sidebar.markdown(f"""
        <div class="stat-card success-card">
            <strong>✅ Database Active</strong><br>
            📝 {db_info['records']:,} total records<br>
            👥 {db_info['players']} unique players<br>
            🕐 Last update: {db_info['last_update'][:19] if db_info['last_update'] != 'Never' else 'Never'}
        </div>
        """, unsafe_allow_html=True)
    else:
        st.sidebar.markdown(f"""
        <div class="stat-card error-card">
            <strong>❌ Database Not Found</strong><br>
            Please update the database first.
        </div>
        """, unsafe_allow_html=True)
    
    # Main content based on selected page
    if page == "🏠 Dashboard":
        show_dashboard()
    elif page == "📈 Team Statistics":
        show_team_statistics()
    elif page == "🔄 Database Management":
        show_database_management()
    elif page == "📊 Player Analytics":
        show_player_analytics()

def show_dashboard():
    """Main dashboard with overview"""
    st.header("📊 Team Overview")
    
    db_info = get_database_info()
    if not db_info["exists"]:
        st.error("Database not found. Please use the Database Management page to fetch data first.")
        return
    
    # Get date range from database
    min_date, max_date = get_date_range_from_db()
    
    # Initialize session state dates if not set
    if st.session_state.dashboard_start_date is None:
        st.session_state.dashboard_start_date = max_date - timedelta(days=7)
    if st.session_state.dashboard_end_date is None:
        st.session_state.dashboard_end_date = max_date
    
    # Perfectly aligned compact date selection
    st.markdown('<div class="date-filter-container">', unsafe_allow_html=True)
    
    with st.container():
        # Single row layout with perfect alignment
        date_col1, date_col2, buttons_col = st.columns([1.5, 1.5, 3])
        
        with date_col1:
            dashboard_start_date = st.date_input(
                "From",
                value=st.session_state.dashboard_start_date,
                min_value=min_date,
                max_value=max_date,
                key="dashboard_start_input"
            )
            st.session_state.dashboard_start_date = dashboard_start_date
        
        with date_col2:
            dashboard_end_date = st.date_input(
                "To", 
                value=st.session_state.dashboard_end_date,
                min_value=min_date,
                max_value=max_date,
                key="dashboard_end_input"
            )
            st.session_state.dashboard_end_date = dashboard_end_date
        
        with buttons_col:
            # Perfectly aligned horizontal quick period buttons
            quick_col1, quick_col2, quick_col3, quick_col4 = st.columns(4)
            
            with quick_col1:
                if st.button("📅 Today", key="dash_today", use_container_width=True):
                    st.session_state.dashboard_start_date = max_date
                    st.session_state.dashboard_end_date = max_date
                    st.rerun()
            
            with quick_col2:
                if st.button("⏰ Week", key="dash_week", use_container_width=True):
                    st.session_state.dashboard_start_date = max_date - timedelta(days=7)
                    st.session_state.dashboard_end_date = max_date
                    st.rerun()
            
            with quick_col3:
                if st.button("📊 Month", key="dash_month", use_container_width=True):
                    st.session_state.dashboard_start_date = max_date - timedelta(days=30)
                    st.session_state.dashboard_end_date = max_date
                    st.rerun()
            
            with quick_col4:
                if st.button("🌍 All", key="dash_all", use_container_width=True):
                    st.session_state.dashboard_start_date = min_date
                    st.session_state.dashboard_end_date = max_date
                    st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Validate date range
    if dashboard_start_date > dashboard_end_date:
        st.error("Start date must be before end date!")
        return
    
    st.caption(f"📊 Period: {dashboard_start_date} to {dashboard_end_date}")
    st.markdown("---")
    
    # Enhanced quick stats using stat-highlight styling
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="stat-highlight">
            <h3>{db_info['records']:,}</h3>
            <p>Total Records</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="stat-highlight">
            <h3>{db_info['players']}</h3>
            <p>Active Players</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        # Get filtered period records
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM dedimania_records 
                WHERE DATE(RecordDate) >= ? AND DATE(RecordDate) <= ?
            """, (dashboard_start_date, dashboard_end_date))
            period_records = cursor.fetchone()[0]
            conn.close()
            period_label = "Selected Period" if (dashboard_end_date - dashboard_start_date).days > 1 else "Selected Day"
            
            st.markdown(f"""
            <div class="stat-highlight">
                <h3>{period_records:,}</h3>
                <p>{period_label}</p>
            </div>
            """, unsafe_allow_html=True)
        except:
            st.markdown(f"""
            <div class="stat-highlight">
                <h3>N/A</h3>
                <p>Selected Period</p>
            </div>
            """, unsafe_allow_html=True)
    
    with col4:
        # Get world records in selected period
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM dedimania_records 
                WHERE DATE(RecordDate) >= ? AND DATE(RecordDate) <= ? AND Rank = '1'
            """, (dashboard_start_date, dashboard_end_date))
            world_records = cursor.fetchone()[0]
            conn.close()
            
            st.markdown(f"""
            <div class="stat-highlight">
                <h3>{world_records}</h3>
                <p>World Records</p>
            </div>
            """, unsafe_allow_html=True)
        except:
            st.markdown(f"""
            <div class="stat-highlight">
                <h3>N/A</h3>
                <p>World Records</p>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Recent activity
    st.subheader("🕐 Recent Activity")
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        df = pd.read_sql_query("""
            SELECT NickName, Challenge, Rank, Record, RecordDate 
            FROM dedimania_records 
            WHERE DATE(RecordDate) >= ? AND DATE(RecordDate) <= ?
            ORDER BY RecordDate DESC 
            LIMIT 20
        """, conn, params=(dashboard_start_date, dashboard_end_date))
        conn.close()
        
        if not df.empty:
            df['RecordDate'] = pd.to_datetime(df['RecordDate']).dt.strftime('%Y-%m-%d %H:%M')
            st.dataframe(df, use_container_width=True)
        else:
            st.info(f"No recent records found for the selected period")
    except Exception as e:
        st.error(f"Error loading recent activity: {e}")


def show_team_statistics():
    """Enhanced team statistics page with comprehensive visualizations and analysis"""
    st.header("📈 Team Statistics")
    
    if not os.path.exists(DATABASE_PATH):
        st.error("Database not found. Please update the database first.")
        return
    
    # Get date range from database
    min_date, max_date = get_date_range_from_db()
    
    # Initialize session state dates if not set
    if st.session_state.stats_start_date is None:
        try:
            default_start, default_end = get_weekly_date_range()
            st.session_state.stats_start_date = datetime.strptime(default_start, '%Y-%m-%d').date()
            st.session_state.stats_end_date = datetime.strptime(default_end, '%Y-%m-%d').date()
        except:
            st.session_state.stats_start_date = max_date - timedelta(days=7)
            st.session_state.stats_end_date = max_date
    
    # Perfectly aligned compact date selection
    st.markdown('<div class="date-filter-container">', unsafe_allow_html=True)
    
    with st.container():
        # Single row layout with perfect alignment
        date_col1, date_col2, buttons_col = st.columns([1.2, 1.2, 4])
        
        with date_col1:
            stats_start_date = st.date_input(
                "From",
                value=st.session_state.stats_start_date,
                min_value=min_date,
                max_value=max_date,
                key="stats_start_input"
            )
            st.session_state.stats_start_date = stats_start_date
        
        with date_col2:
            stats_end_date = st.date_input(
                "To", 
                value=st.session_state.stats_end_date,
                min_value=min_date,
                max_value=max_date,
                key="stats_end_input"
            )
            st.session_state.stats_end_date = stats_end_date
        
        with buttons_col:
            # Perfectly aligned horizontal quick period buttons
            quick_col1, quick_col2, quick_col3, quick_col4, quick_col5 = st.columns(5)
            
            with quick_col1:
                if st.button("📅 Week", key="stats_current_week", use_container_width=True):
                    try:
                        start_date, end_date = get_weekly_date_range()
                        st.session_state.stats_start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                        st.session_state.stats_end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                    except:
                        st.session_state.stats_start_date = max_date - timedelta(days=7)
                        st.session_state.stats_end_date = max_date
                    st.rerun()
            
            with quick_col2:
                if st.button("⏰ 7d", key="stats_last_7", use_container_width=True):
                    st.session_state.stats_start_date = max_date - timedelta(days=7)
                    st.session_state.stats_end_date = max_date
                    st.rerun()
            
            with quick_col3:
                if st.button("📊 30d", key="stats_last_30", use_container_width=True):
                    st.session_state.stats_start_date = max_date - timedelta(days=30)
                    st.session_state.stats_end_date = max_date
                    st.rerun()
            
            with quick_col4:
                if st.button("📆 Month", key="stats_this_month", use_container_width=True):
                    today = datetime.now().date()
                    st.session_state.stats_start_date = today.replace(day=1)
                    st.session_state.stats_end_date = max_date
                    st.rerun()
            
            with quick_col5:
                if st.button("🌍 All", key="stats_all_time", use_container_width=True):
                    st.session_state.stats_start_date = min_date
                    st.session_state.stats_end_date = max_date
                    st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Validate date range
    if stats_start_date > stats_end_date:
        st.error("Start date must be before end date!")
        return
    
    # Compact period display
    period_days = (stats_end_date - stats_start_date).days + 1
    st.caption(f"📊 Period: {stats_start_date} to {stats_end_date} ({period_days} days)")
    
    # ENHANCED STATISTICS ANALYSIS
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT player_login, NickName, Challenge, Record, Rank, RecordDate, Envir, Mode, server
            FROM dedimania_records 
            WHERE DATE(RecordDate) >= ? AND DATE(RecordDate) <= ?
            ORDER BY RecordDate DESC
        """, (stats_start_date, stats_end_date))
        
        raw_records = cursor.fetchall()
        conn.close()
        
        if not raw_records:
            st.warning(f"No data available for the selected period ({stats_start_date} to {stats_end_date})")
            return
        
        # Convert to easier data structure
        records_df = pd.DataFrame(raw_records, columns=[
            'player_login', 'NickName', 'Challenge', 'Record', 'Rank', 
            'RecordDate', 'Envir', 'Mode', 'server'
        ])
        
        # ENHANCED OVERVIEW SECTION
        st.subheader("🏆 Enhanced Performance Overview")
        
        # Top row metrics
        col1, col2, col3, col4, col5 = st.columns(5)
        
        total_records = len(records_df)
        unique_tracks = records_df['Challenge'].nunique()
        unique_players = records_df['player_login'].nunique()
        world_records = len(records_df[records_df['Rank'] == '1'])
        top5_records = len(records_df[records_df['Rank'].astype(str).str.isdigit() & 
                                    (records_df['Rank'].astype(int) <= 5)])
        
        with col1:
            st.markdown("""
            <div class="stat-highlight">
                <h3>📝 {}</h3>
                <p>Total Records</p>
            </div>
            """.format(f"{total_records:,}"), unsafe_allow_html=True)
        
        with col2:
            st.markdown("""
            <div class="stat-highlight">
                <h3>🎯 {}</h3>
                <p>Unique Tracks</p>
            </div>
            """.format(unique_tracks), unsafe_allow_html=True)
        
        with col3:
            st.markdown("""
            <div class="stat-highlight">
                <h3>👥 {}</h3>
                <p>Active Players</p>
            </div>
            """.format(unique_players), unsafe_allow_html=True)
        
        with col4:
            st.markdown("""
            <div class="stat-highlight">
                <h3>🥇 {}</h3>
                <p>World Records</p>
            </div>
            """.format(world_records), unsafe_allow_html=True)
        
        with col5:
            st.markdown("""
            <div class="stat-highlight">
                <h3>🏅 {}</h3>
                <p>Top 5 Records</p>
            </div>
            """.format(top5_records), unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Calculate player statistics for analysis
        player_stats = {}
        for _, record in records_df.iterrows():
            login = record['player_login']
            nick = record['NickName'] if record['NickName'] else login
            rank = record['Rank']
            
            if login not in player_stats:
                player_stats[login] = {
                    'nickname': nick,
                    'total_records': 0,
                    'world_records': 0,
                    'top3_records': 0,
                    'top5_records': 0,
                    'environments': set(),
                    'tracks': set()
                }
            
            player_stats[login]['total_records'] += 1
            player_stats[login]['tracks'].add(record['Challenge'])
            player_stats[login]['environments'].add(record['Envir'])
            
            if rank == '1':
                player_stats[login]['world_records'] += 1
            if rank.isdigit() and int(rank) <= 3:
                player_stats[login]['top3_records'] += 1
            if rank.isdigit() and int(rank) <= 5:
                player_stats[login]['top5_records'] += 1
            
            # Update nickname to latest
            player_stats[login]['nickname'] = nick
        
        # ENHANCED VISUALIZATIONS
        st.subheader("📊 Enhanced Analytics")
        
        viz_col1, viz_col2 = st.columns(2)
        
        with viz_col1:
            st.subheader("🏆 Leaderboard Standings")
            # Create a comprehensive leaderboard
            leaderboard_data = []
            for login, stats in player_stats.items():
                leaderboard_data.append({
                    'Player': stats['nickname'],
                    'WRs': stats['world_records'],
                    'Top 3': stats['top3_records'],
                    'Top 5': stats['top5_records'],
                    'Total': stats['total_records'],
                    'Tracks': len(stats['tracks']),
                    'WR%': f"{stats['world_records']/max(stats['total_records'], 1):.1%}"
                })
            
            df_leaderboard = pd.DataFrame(leaderboard_data)
            df_leaderboard = df_leaderboard.sort_values(['WRs', 'Top 3', 'Top 5'], ascending=False)
            
            # Display top players
            st.dataframe(df_leaderboard.head(10), use_container_width=True, hide_index=True)
        
        with viz_col2:
            st.subheader("🌍 Environment Distribution")
            env_counts = records_df['Envir'].value_counts()
            
            # Create environment chart
            if len(env_counts) > 0:
                st.bar_chart(env_counts)
                
                # Show top environment
                top_env = env_counts.index[0]
                top_env_count = env_counts.iloc[0]
                env_percentage = (top_env_count / total_records * 100)
                st.success(f"🏆 **Top Environment**: {top_env} ({top_env_count} records, {env_percentage:.1f}%)")
        

        # PLAYER RIVALRIES - STREAMLINED
        st.subheader("🔥 Player Rivalries")
        
        # Find rivalries based on shared tracks
        rivalries = []
        players_list = list(player_stats.keys())
        
        for i in range(len(players_list)):
            for j in range(i + 1, len(players_list)):
                player1_login = players_list[i]
                player2_login = players_list[j]
                
                player1_tracks = player_stats[player1_login]['tracks']
                player2_tracks = player_stats[player2_login]['tracks']
                shared_tracks = player1_tracks.intersection(player2_tracks)
                
                if len(shared_tracks) >= 3:  # At least 3 shared tracks for rivalry
                    # Calculate head-to-head on shared tracks
                    p1_wins = 0
                    p2_wins = 0
                    
                    for track in shared_tracks:
                        p1_records = records_df[(records_df['player_login'] == player1_login) & 
                                              (records_df['Challenge'] == track)]
                        p2_records = records_df[(records_df['player_login'] == player2_login) & 
                                              (records_df['Challenge'] == track)]
                        
                        if not p1_records.empty and not p2_records.empty:
                            p1_best_rank = p1_records['Rank'].astype(str)
                            p2_best_rank = p2_records['Rank'].astype(str)
                            
                            # Convert to numeric for comparison (handle non-numeric ranks)
                            try:
                                p1_rank = min([int(r) for r in p1_best_rank if r.isdigit()] or [999])
                                p2_rank = min([int(r) for r in p2_best_rank if r.isdigit()] or [999])
                                
                                if p1_rank < p2_rank:
                                    p1_wins += 1
                                elif p2_rank < p1_rank:
                                    p2_wins += 1
                            except:
                                continue
                    
                    total_battles = p1_wins + p2_wins
                    if total_battles >= 2:  # At least 2 head-to-head battles
                        rivalries.append({
                            'player1': player_stats[player1_login]['nickname'],
                            'player2': player_stats[player2_login]['nickname'],
                            'shared_tracks': len(shared_tracks),
                            'p1_wins': p1_wins,
                            'p2_wins': p2_wins,
                            'total_battles': total_battles,
                            'score': f"{p1_wins}-{p2_wins}",
                            'leader': player_stats[player1_login]['nickname'] if p1_wins > p2_wins 
                                     else player_stats[player2_login]['nickname'] if p2_wins > p1_wins 
                                     else 'Tied'
                        })
        
        # Sort rivalries by number of battles
        rivalries.sort(key=lambda x: x['total_battles'], reverse=True)
        
        if rivalries:
            # Create a clean table-like format
            st.markdown("### 🏆 Top Rivalries")
            
            # Create rivalries in a cleaner format with proper spacing
            for i, rivalry in enumerate(rivalries[:15], 1):  # Show top 15 rivalries
                intensity = "🔥🔥🔥" if rivalry['total_battles'] >= 8 else "🔥🔥" if rivalry['total_battles'] >= 5 else "🔥"
                
                # Create individual rivalry cards
                st.markdown(f"""
                <div style="
                    background: linear-gradient(145deg, #ffffff 0%, #f8f9fa 100%);
                    padding: 0.8rem 1.2rem;
                    margin: 0.5rem 0;
                    border-radius: 8px;
                    border-left: 3px solid #ff6b6b;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                ">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div style="font-weight: 600; color: #2c3e50;">
                            {intensity} <strong>{rivalry['player1']}</strong> vs <strong>{rivalry['player2']}</strong>
                        </div>
                        <div style="display: flex; gap: 1rem; align-items: center;">
                            <span style="background: #e74c3c; color: white; padding: 0.2rem 0.5rem; border-radius: 4px; font-weight: 600;">
                                {rivalry['score']}
                            </span>
                            <span style="color: #7f8c8d; font-size: 0.9rem;">
                                {rivalry['shared_tracks']} battles
                            </span>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            if len(rivalries) > 15:
                st.caption(f"📊 Showing top 15 rivalries out of {len(rivalries)} total detected")
        else:
            st.info("🤝 No significant rivalries detected in this period - everyone's playing nice!")
        
        st.markdown("---")
        
        # SUMMARY INSIGHTS
        st.subheader("🎯 Period Insights")
        
        insights_col1, insights_col2, insights_col3 = st.columns(3)
        
        with insights_col1:
            # Most improved (placeholder - would need historical comparison)
            st.markdown(f"""
            <div class="stat-card success-card">
                <h4>📊 Period Summary</h4>
                <p><strong>Duration:</strong> {period_days} days</p>
                <p><strong>Daily Average:</strong> {total_records/period_days:.1f} records</p>
                <p><strong>WR Rate:</strong> {world_records/max(total_records,1):.1%}</p>
            </div>
            """, unsafe_allow_html=True)
        
        with insights_col2:
            # Competition level
            avg_players_per_track = total_records / max(unique_tracks, 1)
            competition_level = "🔥 High" if avg_players_per_track > 3 else "⚡ Medium" if avg_players_per_track > 2 else "🎯 Low"
            
            st.markdown(f"""
            <div class="stat-card warning-card">
                <h4>🏁 Competition Level</h4>
                <p><strong>Level:</strong> {competition_level}</p>
                <p><strong>Avg Players/Track:</strong> {avg_players_per_track:.1f}</p>
                <p><strong>Track Variety:</strong> {unique_tracks} tracks</p>
            </div>
            """, unsafe_allow_html=True)
        
        with insights_col3:
            # Activity distribution
            weekend_records = 0
            weekday_records = 0
            
            for _, record in records_df.iterrows():
                record_date = pd.to_datetime(record['RecordDate'])
                if record_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
                    weekend_records += 1
                else:
                    weekday_records += 1
            
            weekend_pct = weekend_records / max(total_records, 1) * 100
            
            st.markdown(f"""
            <div class="stat-card">
                <h4>📅 Activity Pattern</h4>
                <p><strong>Weekend:</strong> {weekend_pct:.1f}% ({weekend_records})</p>
                <p><strong>Weekday:</strong> {100-weekend_pct:.1f}% ({weekday_records})</p>
                <p><strong>Style:</strong> {'Weekend Warriors' if weekend_pct > 60 else 'Consistent Grinders' if weekend_pct < 40 else 'Balanced'}</p>
            </div>
            """, unsafe_allow_html=True)
        
    except Exception as e:
        st.error(f"❌ Error generating enhanced stats: {e}")
        st.info("Please check your data and try refreshing the page.")

def show_database_management():
    """Database management page"""
    st.header("🔄 Database Management")
    
    # Database status
    db_info = get_database_info()
    
    if db_info["exists"]:
        st.success(f"✅ Database found with {db_info['records']:,} records from {db_info['players']} players")
    else:
        st.warning("⚠️ Database not found or empty")
    
    st.markdown("---")
    
    # Update database
    st.subheader("🔄 Update Database")
    st.info("This will fetch the latest data from Dedimania for all team players. This may take several minutes.")
    
    if st.button("🚀 Fetch Latest Data", type="primary"):
        with st.spinner("Fetching data from Dedimania... This may take several minutes."):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                # Redirect stdout to capture print statements
                import io
                import contextlib
                
                old_stdout = sys.stdout
                f = io.StringIO()
                
                with contextlib.redirect_stdout(f):
                    # Run your existing fetch script
                    headers_row = get_all_headers()
                    conn = sqlite3.connect(DATABASE_PATH)
                    create_table_if_needed(conn, headers_row)
                    fetch_and_store(conn, headers_row)
                    conn.close()
                
                # Restore stdout
                sys.stdout = old_stdout
                output = f.getvalue()
                
                progress_bar.progress(100)
                st.success("✅ Database updated successfully!")
                
                # Show the output in an expander
                with st.expander("📋 Update Details"):
                    st.text(output)
                
                # Refresh database info
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Error updating database: {e}")
                progress_bar.empty()
                status_text.empty()
    
    # Database statistics
    if db_info["exists"]:
        st.markdown("---")
        st.subheader("📊 Database Statistics")
        
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            
            # Records per player
            df_players = pd.read_sql_query("""
                SELECT NickName, COUNT(*) as record_count
                FROM dedimania_records 
                GROUP BY player_login, NickName
                ORDER BY record_count DESC
                LIMIT 10
            """, conn)
            
            # Records over time
            df_timeline = pd.read_sql_query("""
                SELECT DATE(RecordDate) as date, COUNT(*) as daily_records
                FROM dedimania_records 
                WHERE RecordDate >= date('now', '-30 days')
                GROUP BY DATE(RecordDate)
                ORDER BY date
            """, conn)
            
            conn.close()
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("🏆 Top Players by Records")
                st.dataframe(df_players, use_container_width=True)
            
            with col2:
                st.subheader("📈 Records Over Time (Last 30 Days)")
                if not df_timeline.empty:
                    st.line_chart(df_timeline.set_index('date'))
                else:
                    st.info("No recent data available")
                    
        except Exception as e:
            st.error(f"Error loading statistics: {e}")

def show_player_analytics():
    """Player analytics page"""
    st.header("📊 Player Analytics")
    
    if not os.path.exists(DATABASE_PATH):
        st.error("Database not found. Please update the database first.")
        return
    
    # Get date range from database
    min_date, max_date = get_date_range_from_db()
    
    # Initialize session state for player analytics
    if 'player_analytics_start_date' not in st.session_state:
        st.session_state.player_analytics_start_date = max_date - timedelta(days=30)
    if 'player_analytics_end_date' not in st.session_state:
        st.session_state.player_analytics_end_date = max_date
    
    # Perfectly aligned compact date selection
    st.markdown('<div class="date-filter-container">', unsafe_allow_html=True)
    
    with st.container():
        # Single row layout with perfect alignment
        date_col1, date_col2, buttons_col = st.columns([1.2, 1.2, 3.5])
        
        with date_col1:        
            start_date = st.date_input(
                "From",
                value=st.session_state.player_analytics_start_date,
                min_value=min_date,
                max_value=max_date,
                key="player_analytics_start_input"
            )
            st.session_state.player_analytics_start_date = start_date
        
        with date_col2:
            end_date = st.date_input(
                "To", 
                value=st.session_state.player_analytics_end_date,
                min_value=min_date,
                max_value=max_date,
                key="player_analytics_end_input"
            )
            st.session_state.player_analytics_end_date = end_date
        
        with buttons_col:
            # Perfectly aligned horizontal quick period buttons
            quick_col1, quick_col2, quick_col3, quick_col4 = st.columns(4)
            
            with quick_col1:
                if st.button("⏰ 7d", key="player_last_7", use_container_width=True):
                    st.session_state.player_analytics_start_date = max_date - timedelta(days=7)
                    st.session_state.player_analytics_end_date = max_date
                    st.rerun()
            
            with quick_col2:
                if st.button("📆 30d", key="player_last_30", use_container_width=True):
                    st.session_state.player_analytics_start_date = max_date - timedelta(days=30)
                    st.session_state.player_analytics_end_date = max_date
                    st.rerun()
            
            with quick_col3:
                if st.button("📊 90d", key="player_last_90", use_container_width=True):
                    st.session_state.player_analytics_start_date = max_date - timedelta(days=90)
                    st.session_state.player_analytics_end_date = max_date
                    st.rerun()
            
            with quick_col4:
                if st.button("🌍 All", key="player_all_time", use_container_width=True):
                    st.session_state.player_analytics_start_date = min_date
                    st.session_state.player_analytics_end_date = max_date
                    st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Validate date range
    if start_date > end_date:
        st.error("Start date must be before end date!")
        return
    
    # Compact period display
    st.caption(f"📊 Period: {start_date} to {end_date} ({(end_date - start_date).days + 1} days)")
    
    st.markdown("---")
    
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # Get ALL unique players with their most recent nicknames (not filtered by date range)
        cursor.execute("""
            SELECT 
                player_login,
                NickName,
                RecordDate,
                ROW_NUMBER() OVER (PARTITION BY player_login ORDER BY RecordDate DESC) as rn
            FROM dedimania_records 
            WHERE NickName IS NOT NULL AND NickName != ''
        """)
        
        all_records = cursor.fetchall()
        
        # Get the most recent nickname for each unique login
        unique_players = {}
        for login, nick, date, rn in all_records:
            if rn == 1:  # Most recent record for this login
                unique_players[login] = nick
        
        if not unique_players:
            st.warning("No players found in database")
            conn.close()
            return
        
        # Sort players by their current nickname
        sorted_players = sorted(unique_players.items(), key=lambda x: x[1].lower())
        
        # Initialize session state for selected player
        if 'selected_player_login' not in st.session_state:
            st.session_state.selected_player_login = None
        
        # Player selection dropdown - persistent across date changes
        player_options = [f"{nick} ({login})" for login, nick in sorted_players]
        
        # Find current selection index
        current_index = 0
        if st.session_state.selected_player_login:
            for i, (login, nick) in enumerate(sorted_players):
                if login == st.session_state.selected_player_login:
                    current_index = i + 1  # +1 because of empty option
                    break
        
        selected_player = st.selectbox(
            "🎮 Select a player:", 
            [""] + player_options,
            index=current_index,
            key="player_selector"
        )
        
        # Update session state when selection changes
        if selected_player and selected_player != "":
            player_login = selected_player.split('(')[1].rstrip(')')
            player_name = selected_player.split(' (')[0]
            st.session_state.selected_player_login = player_login
        else:
            st.session_state.selected_player_login = None
            player_login = None
            player_name = None
        
        if player_login:
            
            st.subheader(f"📊 Analytics for {player_name}")
            
            # Get all player stats within selected date range
            df_player = pd.read_sql_query("""
                SELECT Challenge, Rank, Record, RecordDate, Envir, Mode, NickName
                FROM dedimania_records 
                WHERE player_login = ?
                    AND DATE(RecordDate) >= ? AND DATE(RecordDate) <= ?
                ORDER BY RecordDate DESC
            """, conn, params=(player_login, start_date, end_date))
            
            if df_player.empty:
                st.warning(f"📭 No records found for **{player_name}** in the selected time period ({start_date} to {end_date})")
                st.info("💡 Try expanding your date range or select a different time period.")
                conn.close()
                return
            
            # Player metrics in cards
            col1, col2, col3, col4 = st.columns(4)
            
            total_records = len(df_player)
            world_records = len(df_player[df_player['Rank'] == '1'])
            top5_records = len(df_player[df_player['Rank'].astype(str).str.isdigit() & 
                                       (df_player['Rank'].astype(int) <= 5)])
            unique_tracks = df_player['Challenge'].nunique()
            
            with col1:
                st.metric("Total Records", f"{total_records:,}")
            
            with col2:
                st.metric("World Records", world_records)
            
            with col3:
                st.metric("Top 5 Records", top5_records)
            
            with col4:
                st.metric("Unique Tracks", unique_tracks)
            
            # Additional metrics row
            col5, col6, col7, col8 = st.columns(4)
            
            # Calculate average rank (only for numeric ranks)
            numeric_ranks = df_player[df_player['Rank'].astype(str).str.isdigit()]['Rank'].astype(int)
            avg_rank = numeric_ranks.mean() if len(numeric_ranks) > 0 else 0
            
            # Calculate top 3 records
            top3_records = len(df_player[df_player['Rank'].astype(str).str.isdigit() & 
                                       (df_player['Rank'].astype(int) <= 3)])
            
            # Get activity span
            if len(df_player) > 0:
                first_record = pd.to_datetime(df_player['RecordDate']).min()
                last_record = pd.to_datetime(df_player['RecordDate']).max()
                activity_days = (last_record - first_record).days + 1
            else:
                activity_days = 0
            
            # Most common environment
            most_common_env = df_player['Envir'].mode()
            favorite_env = most_common_env.iloc[0] if len(most_common_env) > 0 else "Unknown"
            
            with col5:
                st.metric("Average Rank", f"{avg_rank:.1f}" if avg_rank > 0 else "N/A")
            
            with col6:
                st.metric("Top 3 Records", top3_records)
            
            with col7:
                st.metric("Activity Span", f"{activity_days} days")
            
            with col8:
                st.metric("Favorite Environment", favorite_env[:8])
            
            st.markdown("---")
            
            # Performance trends
            col_left, col_right = st.columns(2)
            
            with col_left:
                st.subheader("📊 Rank Distribution")
                # Only show ranks 1-20 for better visualization
                rank_counts = df_player[df_player['Rank'].astype(str).str.isdigit()]['Rank'].astype(int)
                rank_counts = rank_counts[rank_counts <= 20].value_counts().sort_index()
                
                if len(rank_counts) > 0:
                    st.bar_chart(rank_counts)
                else:
                    st.info("No numeric ranks to display")
            
            with col_right:
                st.subheader("🌍 Environment Breakdown")
                env_counts = df_player['Envir'].value_counts()
                
                if len(env_counts) > 0:
                    # Create a pie-like visualization using metrics
                    total_env_records = len(df_player)
                    for env, count in env_counts.head(5).items():
                        percentage = (count / total_env_records * 100)
                        st.write(f"**{env}**: {count} records ({percentage:.1f}%)")
                else:
                    st.info("No environment data available")
            
            # Recent activity
            st.subheader("🕐 Recent Records (Last 20)")
            df_recent = df_player.head(20).copy()
            
            if not df_recent.empty:
                # Format the data for better display
                df_recent['RecordDate'] = pd.to_datetime(df_recent['RecordDate']).dt.strftime('%Y-%m-%d %H:%M')
                df_recent['Track'] = df_recent['Challenge'].str[:40] + '...' if df_recent['Challenge'].str.len().max() > 40 else df_recent['Challenge']
                
                # Select and rename columns for display
                display_df = df_recent[['RecordDate', 'Track', 'Rank', 'Record', 'Envir']].copy()
                display_df.columns = ['Date', 'Track', 'Rank', 'Time', 'Environment']
                
                st.dataframe(display_df, use_container_width=True, hide_index=True)
            else:
                st.info("No recent records found")
            
            # Best achievements section
            st.subheader("🏆 Best Achievements")
            
            # Get world records
            world_record_tracks = df_player[df_player['Rank'] == '1']['Challenge'].tolist()
            
            if world_record_tracks:
                st.success(f"🥇 **World Records on {len(world_record_tracks)} tracks:**")
                # Show first 5 world record tracks
                for track in world_record_tracks[:5]:
                    st.write(f"• {track}")
                if len(world_record_tracks) > 5:
                    st.write(f"• ... and {len(world_record_tracks) - 5} more!")
            else:
                st.info("No world records yet - keep pushing!")
            
            # Nickname history
            st.subheader("📝 Nickname History")
            nickname_history = df_player[['NickName', 'RecordDate']].drop_duplicates('NickName').sort_values('RecordDate', ascending=False)
            
            if len(nickname_history) > 1:
                st.write("**Previous nicknames:**")
                for _, row in nickname_history.iterrows():
                    date = pd.to_datetime(row['RecordDate']).strftime('%Y-%m-%d')
                    st.write(f"• **{row['NickName']}** (last used: {date})")
            else:
                st.write(f"Always used the same nickname: **{player_name}**")
        
        else:
            # No player selected - show helpful message
            st.markdown("""
            <div class="info-box">
                <h3>🎮 Welcome to Player Analytics!</h3>
                <p><strong>Please select a player from the dropdown above</strong> to view their detailed statistics and performance data.</p>
                <p>The selected player will persist when you change time periods, so you can easily explore their performance across different date ranges.</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Show available players count
            st.info(f"📊 **{len(unique_players)} players** available in the database with recorded statistics.")
        
        conn.close()
        
    except Exception as e:
        st.error(f"Error loading player analytics: {e}")
        st.info("Please check the database connection and try again.")

if __name__ == "__main__":
    main() 