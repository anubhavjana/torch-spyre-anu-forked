# Backend API - Deployment Options

This document explains all the ways to run the Spyre Dashboard backend API.

## Option 1: Direct Python Execution (Simplest)

**Best for:** Quick local testing, development

```bash
cd tests/dashboard/backend

# 1. Install dependencies
pip install -r requirements-backend.txt

# 2. Set environment variables
export CLICKHOUSE_HOST="your-clickhouse-host"
export CLICKHOUSE_USER="your-username"
export CLICKHOUSE_PASSWORD="your-password"
export CLICKHOUSE_DATABASE="spyre"

# 3. Run the server
python backend-api.py
```

Or use the provided script:
```bash
cd tests/dashboard/backend
./start-backend.sh  # Loads .env file automatically
```

**Pros:**
- ✅ Fastest to start
- ✅ Easy debugging
- ✅ No Docker required

**Cons:**
- ❌ Requires Python 3.8+ installed
- ❌ Manual dependency management
- ❌ Environment variables must be set manually

---

## Option 2: Using .env File (Recommended for Local Dev)

**Best for:** Local development with persistent configuration

```bash
cd tests/dashboard/backend

# 1. Create .env file
cat > .env << EOF
CLICKHOUSE_HOST=your-clickhouse-host
CLICKHOUSE_USER=your-username
CLICKHOUSE_PASSWORD=your-password
CLICKHOUSE_DATABASE=spyre
EOF

# 2. Install dependencies
pip install -r requirements-backend.txt

# 3. Run with the startup script
./start-backend.sh
```

The `start-backend.sh` script automatically:
- Loads variables from `.env`
- Starts Flask on port 5000
- Enables debug mode

**Pros:**
- ✅ Credentials stored securely in `.env` (gitignored)
- ✅ Easy to switch between environments
- ✅ Simple startup with `./start-backend.sh`

**Cons:**
- ❌ Still requires Python installed
- ❌ `.env` file must be protected

---

## Option 3: Docker Container (Portable)

**Best for:** Consistent environment, CI/CD, sharing with team

```bash
cd tests/dashboard/backend

# 1. Build the Docker image
docker build -f Dockerfile.backend -t spyre-dashboard-backend .

# 2. Run the container
docker run -d \
  -p 5000:5000 \
  -e CLICKHOUSE_HOST="your-host" \
  -e CLICKHOUSE_USER="your-user" \
  -e CLICKHOUSE_PASSWORD="your-password" \
  -e CLICKHOUSE_DATABASE="spyre" \
  --name spyre-backend \
  spyre-dashboard-backend

# 3. Check logs
docker logs -f spyre-backend

# 4. Stop the container
docker stop spyre-backend
docker rm spyre-backend
```

Or use environment file:
```bash
docker run -d \
  -p 5000:5000 \
  --env-file .env \
  --name spyre-backend \
  spyre-dashboard-backend
```

**Pros:**
- ✅ Consistent environment across machines
- ✅ No Python installation needed
- ✅ Easy to deploy anywhere
- ✅ Isolated from host system

**Cons:**
- ❌ Requires Docker installed
- ❌ Slightly slower startup

---

## Option 4: Docker Compose (Full Stack)

**Best for:** Running frontend + backend + nginx together

```bash
cd tests/dashboard

# 1. Ensure .env exists in backend/
ls backend/.env

# 2. Start all services
docker-compose up -d

# 3. Access dashboard
open http://localhost:8080

# 4. View logs
docker-compose logs -f

# 5. Stop all services
docker-compose down
```

This starts:
- Backend API (port 5000)
- Nginx proxy (port 8080)
- Serves frontend files

**Pros:**
- ✅ Complete local environment
- ✅ Nginx handles routing
- ✅ Mimics production setup
- ✅ One command to start everything

**Cons:**
- ❌ Requires Docker Compose
- ❌ More complex setup

---

## Option 5: Kubernetes/Helm (Production)

**Best for:** Production deployment, scalability, high availability

```bash
# 1. Create Kubernetes Secret for credentials
kubectl create secret generic spyre-clickhouse-creds \
  --from-literal=host=your-host \
  --from-literal=user=your-user \
  --from-literal=password=your-password \
  --from-literal=database=spyre \
  -n your-namespace

# 2. Deploy with Helm
cd tests/helm-charts
helm install spyre-dashboard . \
  --namespace your-namespace \
  --set backend.enabled=true

# 3. Check status
kubectl get pods -n your-namespace
kubectl logs -f deployment/spyre-dashboard-backend -n your-namespace

# 4. Access via route/ingress
kubectl get route spyre-dashboard -n your-namespace
```

**Pros:**
- ✅ Production-ready
- ✅ Auto-scaling
- ✅ High availability
- ✅ Secrets management
- ✅ Load balancing

**Cons:**
- ❌ Requires Kubernetes cluster
- ❌ More complex configuration
- ❌ Requires Helm knowledge

---

## Comparison Table

| Method | Setup Time | Portability | Production Ready | Requires |
|--------|-----------|-------------|------------------|----------|
| Direct Python | 1 min | ❌ Low | ❌ No | Python 3.8+ |
| .env File | 2 min | ❌ Low | ❌ No | Python 3.8+ |
| Docker | 5 min | ✅ High | ⚠️ Maybe | Docker |
| Docker Compose | 5 min | ✅ High | ⚠️ Maybe | Docker Compose |
| Kubernetes | 15 min | ✅ Very High | ✅ Yes | K8s cluster |

---

## Quick Start Recommendation

**For Local Development:**
```bash
cd tests/dashboard/backend
./start-backend.sh
```

**For Testing/Sharing:**
```bash
cd tests/dashboard
docker-compose up
```

**For Production:**
```bash
cd tests/helm-charts
helm install spyre-dashboard .
```

---

## Troubleshooting

### Port 5000 already in use
```bash
# Find and kill the process
lsof -ti:5000 | xargs kill -9

# Or use a different port
export FLASK_RUN_PORT=5001
python backend-api.py
```

### Connection refused to ClickHouse
- Check `CLICKHOUSE_HOST` is correct
- Verify network connectivity: `ping your-clickhouse-host`
- Check firewall rules
- Verify ClickHouse is running

### Module not found errors
```bash
pip install -r requirements-backend.txt
```

### Permission denied on start-backend.sh
```bash
chmod +x start-backend.sh