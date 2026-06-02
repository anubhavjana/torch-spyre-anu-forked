# Backend API - Deployment Options

This document explains all the ways to run the Spyre Dashboard backend API.


## Option 1: Using .env File (Recommended for Local Dev)

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


---


## Option 2: Kubernetes/Helm (Production)

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


---
