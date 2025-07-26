# 🏁 TrackMania Team Statistics - Streamlit App

A comprehensive web application for tracking and analyzing TrackMania team performance, built with Streamlit.

## Features

- 🏆 **Gaming Leaderboard**: Dynamic leaderboards with gaming-style visuals
- 📈 **Weekly Statistics**: Comprehensive weekly team performance reports
- 🔄 **Database Management**: Easy data fetching and updates from Dedimania
- 📊 **Player Analytics**: Individual player performance analysis
- 🎮 **Interactive Dashboard**: Real-time team overview and metrics

## Quick Start

### Local Development

1. **Clone and setup**:
   ```bash
   git clone <your-repo>
   cd tm_recs
   pip install -r requirements.txt
   ```

2. **Run the app**:
   ```bash
   streamlit run streamlit_app.py
   ```

3. **Access the app**:
   Open http://localhost:8501 in your browser

### First Time Setup

1. **Update Database**: Go to "Database Management" and click "Fetch Latest Data"
2. **Generate Leaderboard**: Visit "Gaming Leaderboard" and generate your first leaderboard
3. **Create Weekly Report**: Go to "Weekly Stats" and generate your first report

## Deployment Options

### 1. Streamlit Community Cloud (Recommended - FREE)

1. **Push to GitHub**:
   ```bash
   git add .
   git commit -m "Add Streamlit app"
   git push origin main
   ```

2. **Deploy**:
   - Go to https://share.streamlit.io
   - Connect your GitHub account
   - Select your repository
   - Set main file as `streamlit_app.py`
   - Deploy automatically

3. **Your app will be live at**: `https://share.streamlit.io/[username]/[repo-name]/main/streamlit_app.py`

### 2. Railway (Free Tier)

1. **Add Procfile**:
   ```
   web: streamlit run streamlit_app.py --server.port=$PORT --server.address=0.0.0.0
   ```

2. **Deploy**:
   - Connect to Railway.app
   - Link your GitHub repo
   - Deploy automatically

### 3. Render (Free Tier)

1. **Add start command**: `streamlit run streamlit_app.py --server.port=$PORT --server.address=0.0.0.0`
2. **Deploy via Render dashboard**

## Application Structure

```
tm_recs/
├── streamlit_app.py          # Main Streamlit application
├── requirements.txt          # Python dependencies
├── .streamlit/
│   └── config.toml          # Streamlit configuration
├── backend/
│   ├── Final_Weekly_stats/   # Weekly stats and leaderboard generators
│   └── database/             # Database management scripts
├── dedimania_history_master.db  # SQLite database
└── summaries/               # Generated reports and images
```

## Pages Overview

### 🏠 Dashboard
- Team overview with key metrics
- Recent activity feed
- Quick statistics

### 🏆 Gaming Leaderboard
- Generate dynamic gaming-style leaderboards
- View current rankings
- Export capabilities

### 📈 Weekly Stats
- Generate comprehensive weekly reports
- Create visual report images
- View historical reports

### 🔄 Database Management
- Fetch latest data from Dedimania
- Database statistics and health
- Player activity tracking

### 📊 Player Analytics
- Individual player performance
- Record history and trends
- Rank distribution analysis

## Configuration

### Database
The app uses SQLite database (`dedimania_history_master.db`) which should be:
- Placed in the root directory
- Updated regularly via the Database Management page
- Backed up before major updates

### Player List
Players are configured in the backend scripts. To add/remove players:
1. Edit `backend/Final_Weekly_stats/gaming_leaderboard.py`
2. Edit `backend/Final_Weekly_stats/weekly_team_stats.py`
3. Update the `player_logins` list in both files

## Troubleshooting

### Common Issues

1. **Import Errors**:
   - Ensure all backend files are in correct directory structure
   - Check Python path configuration in `streamlit_app.py`

2. **Database Not Found**:
   - Use Database Management page to fetch initial data
   - Ensure database file is in root directory

3. **Image Generation Fails**:
   - Check write permissions for `summaries/` directory
   - Ensure all matplotlib/PIL dependencies are installed

4. **Deployment Issues**:
   - Check requirements.txt has all necessary dependencies
   - Ensure database file is included (or set up data fetching)
   - Verify environment variables if using external databases

### Performance Tips

- Database updates can take several minutes
- Generate reports during off-peak hours
- Consider caching for frequently accessed data
- Use Streamlit's built-in caching decorators for expensive operations

## Environment Variables

For production deployment, consider using:
- `DATABASE_URL`: External database connection string
- `DEDIMANIA_API_KEY`: API key if required
- `DEBUG`: Set to False for production

## Support

For issues and questions:
- Check the application logs in Streamlit Cloud
- Review database integrity via Database Management page
- Ensure all team player logins are correctly configured

## License

[Your License Here] 