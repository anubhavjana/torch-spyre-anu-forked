# Local Development Setup

This guide shows how to run the Spyre Dashboard locally with the secure backend architecture.

## Prerequisites

- Docker and Docker Compose installed
- Access to a ClickHouse instance
- ClickHouse credentials (username and password/token)

## Quick Start

### 1. Configure Environment Variables

Copy the example environment file and fill in your ClickHouse credentials:

```bash
cd tests/dashboard
cp .env.example .env
```

Edit `.env` with your actual values:

```bash
SPYRE_CH_URL=https://your-clickhouse-host.com:8443
SPYRE_CH_DB=spyre
SPYRE_CH_USER=default
SPYRE_CH_TOKEN=your-actual-password-here
```

**⚠️ IMPORTANT**: Never commit the `.env` file to git! It contains sensitive credentials.

### 2. Update dashboard.html

Add the API URL meta tag to `dashboard.html` (if not already present):

```html
<head>
  <!-- ... other meta tags ... -->
  <meta name="spyre-api-url" content="/api">
  <meta name="spyre-ch-db" content="spyre">
  <meta name="spyre-ch-workflow" content="">
  <meta name="spyre-ch-limit" content="30">
</head>
```

### 3. Start the Services

```bash
docker-compose up --build
```

docker compose version

This will start:

- **Backend API** on `http://localhost:5000`
- **Frontend (nginx)** on `http://localhost:8080`

### 4. Access the Dashboard

Open your browser and navigate to:

```
http://localhost:8080/dashboard.html
```

## Architecture

```
Browser (localhost:8080)
    ↓ /api/* requests
Nginx (port 8080)
    ↓ proxy to backend:5000
Backend API (port 5000)
    ↓ authenticated queries
ClickHouse Database
```

## Verify Setup

### Check Backend Health

```bash
curl http://localhost:5000/api/health
```

Expected response:

```json
{"status": "ok", "service": "spyre-dashboard-backend"}
```

### Check Backend Config

```bash
curl http://localhost:5000/api/config
```

Expected response:

```json
{"db": "spyre", "configured": true}
```

### Test Query Endpoint

```bash
curl -X POST http://localhost:5000/api/query \
  -H "Content-Type: text/plain" \
  -d "SELECT 1"
```

## Alternative: Run Without Docker

### Backend Only

1. Install Python dependencies:

```bash
cd tests/dashboard
pip install -r requirements-backend.txt
```

2. Set environment variables:

```bash
export SPYRE_CH_URL="https://your-clickhouse-host.com:8443"
export SPYRE_CH_DB="spyre"
export SPYRE_CH_USER="default"
export SPYRE_CH_TOKEN="your-password"
```

3. Run the backend:

```bash
python backend-api.py
```

Backend will be available at `http://localhost:5000`

### Frontend Only

1. Update `dashboard.html` to point to your backend:

```html
<meta name="spyre-api-url" content="http://localhost:5000/api">
```

2. Serve with any web server:

```bash
# Using Python
python -m http.server 8080

# Using Node.js
npx http-server -p 8080

# Or just open dashboard.html in your browser
```

## Troubleshooting

### Backend can't connect to ClickHouse

**Error**: `ClickHouse error: Connection refused`

**Solution**:

- Verify `SPYRE_CH_URL` is correct
- Check if ClickHouse is accessible from your machine
- Test connection: `curl -v https://your-clickhouse-host.com:8443`

### Frontend shows "Not configured"

**Error**: Dashboard shows "Not configured — backend API unavailable"

**Solution**:

- Verify backend is running: `curl http://localhost:5000/api/health`
- Check nginx logs: `docker-compose logs frontend`
- Ensure meta tag is present: `<meta name="spyre-api-url" content="/api">`

### CORS errors in browser console

**Error**: `Access to fetch at 'http://localhost:5000/api/...' has been blocked by CORS`

**Solution**:

- Use nginx proxy (recommended): Access via `http://localhost:8080`
- Or update backend CORS settings in `backend-api.py`

### Authentication errors

**Error**: `ClickHouse error 401: Authentication failed`

**Solution**:

- Verify credentials in `.env` file
- Check if token/password is correct
- Ensure user has SELECT permissions on the database

## Development Tips

### Watch Backend Logs

```bash
docker-compose logs -f backend
```

### Rebuild After Code Changes

```bash
docker-compose up --build
```

### Stop Services

```bash
docker-compose down
```

### Clean Up Everything

```bash
docker-compose down -v
rm .env
```

## Security Notes

✅ **DO**:

- Keep `.env` file private (it's in `.gitignore`)
- Use HTTPS in production
- Rotate credentials regularly
- Use read-only database users

❌ **DON'T**:

- Commit `.env` to git
- Share credentials in chat/email
- Use production credentials for local development
- Expose backend port (5000) publicly

## Next Steps

- See [SECURITY.md](./SECURITY.md) for architecture details
- Deploy to Kubernetes: See Helm chart in `tests/helm-charts/`
- Customize queries: Edit `backend-api.py`
- Add authentication: Implement auth middleware in backend
