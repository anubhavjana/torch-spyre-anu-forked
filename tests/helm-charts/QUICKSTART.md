# Quick Start: Deploy Spyre Dashboard with Kubernetes

This guide shows how to deploy the complete Spyre Dashboard (frontend + backend + nginx) using your existing Helm chart.

## Prerequisites

- Kubernetes cluster access
- `kubectl` configured
- `helm` installed
- ClickHouse database accessible from cluster

## Step 1: Create Kubernetes Secret for ClickHouse Credentials

```bash
# Create namespace (if needed)
kubectl create namespace spyre-dashboard

# Create secret with ClickHouse credentials
kubectl create secret generic spyre-clickhouse-creds \
  --from-literal=host='your-clickhouse-host.example.com' \
  --from-literal=user='spyre_reader' \
  --from-literal=password='your-secure-password' \
  --from-literal=token='your-clickhouse-token' \
  --from-literal=database='spyre' \
  --namespace spyre-dashboard
```

## Step 2: Review/Update values.yaml

```bash
cd tests/helm-charts
cat values.yaml
```

Key settings to verify:
```yaml
# Backend API configuration
backend:
  enabled: true
  replicas: 2
  image:
    repository: your-registry/spyre-dashboard-backend
    tag: latest

# ClickHouse connection
clickhouse:
  url: "https://your-clickhouse-host.example.com:8443"
  db: "spyre"
  secretName: "spyre-clickhouse-creds"
```

## Step 3: Build and Push Backend Docker Image (First Time Only)

```bash
# Build the backend image
cd tests/dashboard/backend
docker build -f Dockerfile.backend -t your-registry/spyre-dashboard-backend:latest .

# Push to your container registry
docker push your-registry/spyre-dashboard-backend:latest
```

## Step 4: Deploy with Helm

```bash
cd tests/helm-charts

# Install the chart
helm install spyre-dashboard . \
  --namespace spyre-dashboard \
  --create-namespace

# Or upgrade if already installed
helm upgrade spyre-dashboard . \
  --namespace spyre-dashboard
```

## Step 5: Verify Deployment

```bash
# Check all pods are running
kubectl get pods -n spyre-dashboard

# Expected output:
# NAME                                        READY   STATUS    RESTARTS   AGE
# spyre-dashboard-backend-xxxxx-xxxxx         1/1     Running   0          1m
# spyre-dashboard-backend-xxxxx-yyyyy         1/1     Running   0          1m
# spyre-dashboard-xxxxx-xxxxx                 1/1     Running   0          1m

# Check backend logs
kubectl logs -f deployment/spyre-dashboard-backend -n spyre-dashboard

# Check services
kubectl get svc -n spyre-dashboard
```

## Step 6: Access the Dashboard

### Option A: Via Route (OpenShift)
```bash
# Get the route URL
kubectl get route spyre-dashboard -n spyre-dashboard

# Open in browser
open https://$(kubectl get route spyre-dashboard -n spyre-dashboard -o jsonpath='{.spec.host}')
```

### Option B: Via Port Forward (Development)
```bash
# Forward port 8080 to the service
kubectl port-forward svc/spyre-dashboard 8080:80 -n spyre-dashboard

# Open in browser
open http://localhost:8080
```

### Option C: Via Ingress (if configured)
```bash
# Get ingress URL
kubectl get ingress -n spyre-dashboard
```

## Architecture Deployed

```
┌─────────────────────────────────────────────────────────┐
│ Kubernetes Cluster                                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐      ┌──────────────┐               │
│  │   Route/     │      │   Service    │               │
│  │   Ingress    │─────▶│   (nginx)    │               │
│  └──────────────┘      └──────┬───────┘               │
│                               │                         │
│                    ┌──────────┴──────────┐             │
│                    ▼                     ▼             │
│         ┌──────────────────┐  ┌──────────────────┐    │
│         │  Frontend Pod    │  │  Backend Pod     │    │
│         │  (nginx + HTML)  │  │  (Flask API)     │    │
│         │                  │  │                  │    │
│         │  dashboard.html  │  │  backend-api.py  │    │
│         │  spyre-api-      │  │                  │    │
│         │    client.js     │  │  Reads from:     │    │
│         │                  │  │  - Secret        │    │
│         └──────────────────┘  └────────┬─────────┘    │
│                                        │               │
└────────────────────────────────────────┼───────────────┘
                                         │
                                         ▼
                              ┌──────────────────┐
                              │   ClickHouse     │
                              │   Database       │
                              └──────────────────┘
```

## What Gets Deployed

1. **Frontend Pod** (nginx + static files)
   - Serves `dashboard.html` and `spyre-api-client.js`
   - Proxies `/api/*` requests to backend

2. **Backend Pods** (2 replicas for HA)
   - Flask API server
   - Handles ClickHouse authentication
   - Executes SQL queries
   - Returns JSON to frontend

3. **Services**
   - ClusterIP service for backend (internal only)
   - LoadBalancer/NodePort service for frontend (external access)

4. **ConfigMaps**
   - nginx configuration
   - Dashboard HTML injection script

5. **Secrets**
   - ClickHouse credentials (you created this)

## Troubleshooting

### Backend pods not starting
```bash
# Check pod status
kubectl describe pod -l app.kubernetes.io/component=backend -n spyre-dashboard

# Check logs
kubectl logs -l app.kubernetes.io/component=backend -n spyre-dashboard

# Common issues:
# - Image pull error: Check image repository and credentials
# - Secret not found: Verify secret name in values.yaml
# - CrashLoopBackOff: Check ClickHouse connectivity
```

### Can't access dashboard
```bash
# Check service
kubectl get svc spyre-dashboard -n spyre-dashboard

# Check route/ingress
kubectl get route,ingress -n spyre-dashboard

# Test backend directly
kubectl port-forward svc/spyre-dashboard-backend 5000:5000 -n spyre-dashboard
curl http://localhost:5000/api/health
```

### Backend can't connect to ClickHouse
```bash
# Check secret
kubectl get secret spyre-clickhouse-creds -n spyre-dashboard -o yaml

# Test connectivity from pod
kubectl exec -it deployment/spyre-dashboard-backend -n spyre-dashboard -- \
  curl -v https://your-clickhouse-host:8443

# Check environment variables
kubectl exec -it deployment/spyre-dashboard-backend -n spyre-dashboard -- env | grep CLICKHOUSE
```

## Updating the Deployment

### Update backend code
```bash
# 1. Build new image
cd tests/dashboard/backend
docker build -f Dockerfile.backend -t your-registry/spyre-dashboard-backend:v2 .
docker push your-registry/spyre-dashboard-backend:v2

# 2. Update values.yaml
# Change: backend.image.tag: "v2"

# 3. Upgrade Helm release
cd tests/helm-charts
helm upgrade spyre-dashboard . -n spyre-dashboard
```

### Update frontend
```bash
# Frontend is in git repo, so just update values.yaml:
# Change: git.revision to new commit SHA

helm upgrade spyre-dashboard . -n spyre-dashboard
```

### Update ClickHouse credentials
```bash
# Delete old secret
kubectl delete secret spyre-clickhouse-creds -n spyre-dashboard

# Create new secret
kubectl create secret generic spyre-clickhouse-creds \
  --from-literal=host='new-host' \
  --from-literal=password='new-password' \
  --namespace spyre-dashboard

# Restart backend pods
kubectl rollout restart deployment/spyre-dashboard-backend -n spyre-dashboard
```

## Cleanup

```bash
# Uninstall the Helm release
helm uninstall spyre-dashboard -n spyre-dashboard

# Delete the namespace (optional)
kubectl delete namespace spyre-dashboard
```

## Next Steps

- Set up monitoring (Prometheus/Grafana)
- Configure auto-scaling (HPA)
- Set up backup for ClickHouse
- Configure SSL/TLS certificates
- Set up CI/CD pipeline for automated deployments