# Security Architecture - Spyre Dashboard

## Overview

The Spyre Dashboard implements a **secure three-tier architecture** to protect sensitive ClickHouse credentials:

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (Public)                                          │
│  - dashboard.html                                           │
│  - spyre-clickhouse.js                                      │
│  - NO credentials exposed                                   │
│  - Only knows: /api endpoint                                │
└────────────────┬────────────────────────────────────────────┘
                 │ HTTPS API calls only
                 ↓
┌─────────────────────────────────────────────────────────────┐
│  Backend API (Private)                                      │
│  - backend-api.py (Flask)                                   │
│  - Has ClickHouse credentials from K8s Secret               │
│  - Validates and proxies queries                            │
│  - Runs in separate pod with restricted access              │
└────────────────┬────────────────────────────────────────────┘
                 │ Authenticated ClickHouse queries
                 ↓
┌─────────────────────────────────────────────────────────────┐
│  ClickHouse Database (Private)                              │
│  - Only accessible by backend service                       │
│  - Credentials never leave the backend pod                  │
└─────────────────────────────────────────────────────────────┘
```

## Security Features

### 1. **No Client-Side Credentials**
- ❌ **Before**: Token exposed in `<meta name="spyre-ch-token">` tag
- ✅ **After**: Frontend only knows `/api` endpoint, no credentials

### 2. **Backend Authentication**
- All ClickHouse credentials stored in Kubernetes Secrets
- Secrets mounted only in backend pod (not frontend)
- Backend validates and proxies all database queries

### 3. **API Endpoints**
Frontend can only call these secure endpoints:

- `GET /api/health` - Health check
- `GET /api/config` - Safe configuration (no secrets)
- `POST /api/query` - Execute SQL (backend validates)
- `GET /api/commits` - Fetch commit list
- `GET /api/runs` - Fetch test runs
- `GET /api/test-cases/<run_id>` - Fetch test cases
- `GET /api/commit-tests/<commit_sha>` - Fetch commit tests

### 4. **Network Isolation**
```yaml
Frontend Pod (nginx) → Backend Service (ClusterIP) → ClickHouse
                       ↑
                       Only accessible within cluster
```

## Deployment

### 1. Create ClickHouse Secret
```bash
kubectl create secret generic spyre-clickhouse-token \
  --from-literal=token=<your-clickhouse-password> \
  -n <namespace>
```

### 2. Build Backend Image
```bash
cd tests/dashboard
docker build -f Dockerfile.backend -t your-registry/spyre-dashboard-backend:latest .
docker push your-registry/spyre-dashboard-backend:latest
```

### 3. Update values.yaml
```yaml
backend:
  image:
    repository: your-registry/spyre-dashboard-backend
    tag: latest
```

### 4. Deploy with Helm
```bash
helm install spyre-dashboard tests/helm-charts -n <namespace>
```

## Architecture Components

### Frontend (dashboard.html + spyre-clickhouse.js)
- **Purpose**: User interface for viewing test results
- **Access**: Public (via OpenShift Route)
- **Credentials**: None - only knows `/api` endpoint
- **Communication**: HTTPS to backend API only

### Backend API (backend-api.py)
- **Purpose**: Secure proxy for ClickHouse queries
- **Access**: Private (ClusterIP service)
- **Credentials**: Mounted from K8s Secret
- **Communication**: 
  - Receives: API calls from frontend
  - Sends: Authenticated queries to ClickHouse

### Nginx Proxy
- **Purpose**: Routes `/api/*` to backend service
- **Configuration**: `nginx-ch.conf` in ConfigMap
- **No credentials**: Just proxies requests

## Security Best Practices

### ✅ DO
- Store credentials in Kubernetes Secrets
- Use backend API for all database access
- Validate and sanitize SQL queries in backend
- Use HTTPS for all external communication
- Implement rate limiting on API endpoints
- Monitor backend logs for suspicious queries

### ❌ DON'T
- Expose credentials in HTML meta tags
- Allow direct ClickHouse access from frontend
- Store credentials in ConfigMaps
- Hardcode credentials in code
- Trust client-side input without validation

## Migration from Old Architecture

### Old (Insecure)
```javascript
// Frontend had direct access to credentials
const token = document.querySelector("meta[name='spyre-ch-token']").content;
fetch(clickhouseUrl, {
  headers: {
    'X-ClickHouse-Key': token  // ❌ Exposed to client
  }
});
```

### New (Secure)
```javascript
// Frontend only calls backend API
fetch('/api/query', {
  method: 'POST',
  body: sql  // ✅ Backend handles authentication
});
```

## Monitoring

### Backend Health Check
```bash
curl http://spyre-dashboard-backend:5000/api/health
```

### View Backend Logs
```bash
kubectl logs -l app.kubernetes.io/component=backend -n <namespace>
```

### Check Secret Mount
```bash
kubectl exec -it <backend-pod> -n <namespace> -- env | grep SPYRE_CH
```

## Troubleshooting

### Frontend can't connect to backend
- Check nginx configuration includes `/api/` proxy
- Verify backend service is running: `kubectl get svc`
- Check backend pod logs: `kubectl logs <backend-pod>`

### Backend can't connect to ClickHouse
- Verify secret exists: `kubectl get secret spyre-clickhouse-token`
- Check secret is mounted in backend pod
- Verify ClickHouse URL is correct in values.yaml
- Test connection from backend pod: `curl <clickhouse-url>`

### Credentials still exposed
- Verify you're using the updated configmap-passwd.yaml
- Check meta tags in browser: should only see `spyre-api-url`
- Redeploy if old meta tags still present

## References

- [OWASP API Security Top 10](https://owasp.org/www-project-api-security/)
- [Kubernetes Secrets Best Practices](https://kubernetes.io/docs/concepts/configuration/secret/)
- [Flask Security Considerations](https://flask.palletsprojects.com/en/latest/security/)