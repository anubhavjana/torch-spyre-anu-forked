# Spyre Dashboard

A secure web dashboard for visualizing Spyre test results from ClickHouse database.

## Directory Structure

```
tests/dashboard/
├── frontend/              # Frontend files (HTML, JavaScript)
│   ├── dashboard.html     # Main dashboard UI
│   └── spyre-clickhouse.js # ClickHouse integration
├── backend/               # Backend API service
│   ├── backend-api.py     # Flask API server
│   ├── requirements-backend.txt # Python dependencies
│   ├── Dockerfile.backend # Container image
│   ├── start-backend.sh   # Startup script
│   └── .env              # Environment variables (DO NOT COMMIT)
├── nginx-local.conf       # Nginx proxy configuration
├── .gitignore            # Git ignore rules
├── LOCAL_SETUP.md        # Local development guide
```

## Quick Start

### Local Development

1. **Set up environment variables:**
   ```bash
   cd tests/dashboard/backend
   # Edit .env with your ClickHouse credentials
   ```

2. **Start the backend:**
   ```bash
   cd tests/dashboard/backend
   ./start-backend.sh
   ```

3. **Open the dashboard:**
   ```bash
   # Open frontend/dashboard.html in your browser
   open ../frontend/dashboard.html
   ```


## Architecture
check the readme.md file in backend folder

```
Browser → Frontend (HTML/JS) → Backend API (Flask) → ClickHouse
         ↓                      ↓                      ↓
         UI             Handles auth & SQL          Database