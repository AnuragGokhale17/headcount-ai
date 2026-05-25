# Docker Hardened Images (DHI) Migration Guide

## Executive Summary

This document outlines the migration of the Headcount project from standard Docker images to Docker Hardened Images (DHI). The migration maintains all existing functionality while improving security posture through reduced attack surface, non-root default execution, and minimal image composition.

---

## Part 1: Backend Dockerfile Migration

### Overview of Changes

The backend Dockerfile has been restructured from a 2-stage build to a 3-stage build to optimize DHI usage:

1. **Stage 1**: Node.js development environment for frontend React build
2. **Stage 2**: Python development environment for dependency installation and compilation
3. **Stage 3**: Python runtime environment for application execution

### Before vs After

#### BEFORE (Original)
```dockerfile
#syntax=docker/dockerfile:1

# Stage 1: Build the React frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /build
COPY frontend/package*.json ./
RUN npm config set strict-ssl false && npm install
COPY frontend/ .
RUN npm run build

# Stage 2: Python backend
FROM python:3.10
WORKDIR /app

# Install Python requirements (long timeout for large packages)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --default-timeout=1000 --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt

# Overwrite full opencv-python with headless variant (no libGL needed)
RUN pip install --no-cache-dir --force-reinstall --no-deps --trusted-host pypi.org --trusted-host files.pythonhosted.org opencv-python-headless

# Copy all source code
COPY . .

# Copy built frontend into Flask static folder
COPY --from=frontend-builder /build/dist /app/frontend/dist

# Start Flask
EXPOSE 5000
ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1
CMD ["python", "app.py"]
```

#### AFTER (DHI Migration)
```dockerfile
#syntax=docker/dockerfile:1

# === Stage 1: Build the React frontend ===
FROM dhi.io/node:20-alpine-dev AS frontend-builder
WORKDIR /build
COPY frontend/package*.json ./
RUN npm config set strict-ssl false && npm install
COPY frontend/ .
RUN npm run build

# === Stage 2: Build Python dependencies ===
FROM dhi.io/python:3.10-alpine-dev AS python-builder
WORKDIR /app

# Install Python requirements (long timeout for large packages)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --default-timeout=1000 --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt

# Overwrite full opencv-python with headless variant (no libGL needed)
RUN pip install --no-cache-dir --force-reinstall --no-deps --trusted-host pypi.org --trusted-host files.pythonhosted.org opencv-python-headless

# === Stage 3: Python backend runtime ===
FROM dhi.io/python:3.10-alpine

WORKDIR /app

# Copy Python dependencies from builder stage
COPY --from=python-builder --chown=root:root /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=python-builder --chown=root:root /usr/local/bin /usr/local/bin

# Copy all source code
COPY --chown=root:root . .

# Copy built frontend into Flask static folder
COPY --from=frontend-builder /build/dist /app/frontend/dist

# Ensure proper permissions for the nonroot user
RUN chmod -R u+r /app && \
    chmod u+x /app/app.py

# Start Flask
EXPOSE 5000
ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1
CMD ["python", "app.py"]
```

### Migration Rationale

| Item | Original | DHI Migration | Reason |
|------|----------|---------------|--------|
| **Frontend Build Image** | `node:20-alpine` | `dhi.io/node:20-alpine-dev` | DHI dev tag includes npm and build tools; Alpine variant maintains minimal footprint |
| **Backend Build Image** | `python:3.10` (bloated runtime) | `dhi.io/python:3.10-alpine-dev` | Separated build from runtime; dev tag includes pip and compilation tools |
| **Backend Runtime Image** | `python:3.10` (unnecessary tools) | `dhi.io/python:3.10-alpine` | Minimal runtime image reduces attack surface; Alpine reduces size; nonroot user by default |
| **Dependency Handling** | Installed in single stage | Multi-stage with explicit COPY | Follows DHI best practice; only necessary artifacts in runtime stage |
| **Permissions** | Root user (inherited) | Explicit chown directives | DHI runtime runs as nonroot; ensures file accessibility |
| **Port Usage** | Port 5000 (above 1024) | Port 5000 (unchanged) | Already compliant; nonroot users can bind ports ≥1024 |
| **TLS Certificates** | Implicit | No changes needed | DHI includes standard TLS certificates by default |

### Key Improvements

**Security**:
- Runtime image runs as nonroot user by default, reducing privilege escalation risk
- Minimal Alpine base reduces CVE surface area compared to standard Python images
- Build-time dependencies not included in runtime image

**Performance**:
- Smaller final image size due to Alpine and dependency separation
- Faster image pulls and deployments

**Reliability**:
- Explicit permission handling prevents runtime permission errors
- Clear separation of concerns between build and runtime stages

---

## Part 2: Docker Compose Service Migrations

### Service 1: Redis Migration

#### Current Configuration
```yaml
redis:
  image: redis:7-alpine
  container_name: headcount_redis
  ports:
    - "6379:6379"
  restart: unless-stopped
```

#### DHI Recommendation
```yaml
redis:
  image: dhi.io/redis:7-alpine
  container_name: headcount_redis
  ports:
    - "6379:6379"
  restart: unless-stopped
```

**Migration Notes**:
- Direct DHI equivalent available: `dhi.io/redis:7-alpine`
- No configuration changes required; API remains identical
- Security benefits: nonroot user execution, minimal attack surface
- Reliability: DHI Redis includes security patches and is maintained by Docker

---

### Service 2: Nginx Migration

#### Current Configuration
```yaml
amc-proxy:
  image: nginx:alpine
  container_name: headcount_amc_proxy
  ports:
    - "8000:8000"
    - "5001:5001"
  volumes:
    - ./amc_calibration/proxy.conf:/etc/nginx/nginx.conf:ro
  depends_on:
    - amc-backend
    - amc-ui
  restart: unless-stopped
```

#### DHI Recommendation
```yaml
amc-proxy:
  image: dhi.io/nginx:alpine
  container_name: headcount_amc_proxy
  ports:
    - "8000:8000"
    - "5001:5001"
  volumes:
    - ./amc_calibration/proxy.conf:/etc/nginx/nginx.conf:ro
  depends_on:
    - amc-backend
    - amc-ui
  restart: unless-stopped
  user: "101:101"  # Ensure nginx runs as nonroot (uid:gid 101:101)
```

**Migration Notes**:
- Direct DHI equivalent: `dhi.io/nginx:alpine`
- Port configuration requires attention: Nginx typically runs as root to bind privileged ports. DHI enforces nonroot execution.
- Solution: Configure Nginx to listen on ports ≥1024 internally and use port mapping, OR use `user: "101:101"` directive and ensure Nginx config reflects this
- Recommended: Update `proxy.conf` to use ports 8000 and 5001 in listen directives (already exposed, so internal binding should work)
- Security benefit: Eliminates root privilege requirement for reverse proxy

---

### Service 3: Backend Service (Updated)

The backend service now uses the DHI-migrated Dockerfile. No docker-compose changes needed:

```yaml
backend:
  build:
    context: .
    dockerfile: backend/Dockerfile
  container_name: headcount_backend
  depends_on:
    - redis
    - deepstream
  environment:
    - REDIS_HOST=redis
    - DS_API_BASE=deepstream:8010
    - FLASK_ENV=production
  ports:
    - "5000:5000"
  volumes:
    - .:/app
    - ./data:/app/data
    - ./zones.json:/app/zones.json
  restart: unless-stopped
```

---

## Updated docker-compose.yml (Partial - Services Migrated)

```yaml
version: '3.8'

services:
  redis:
    image: dhi.io/redis:7-alpine
    container_name: headcount_redis
    ports:
      - "6379:6379"
    restart: unless-stopped

  amc-proxy:
    image: dhi.io/nginx:alpine
    container_name: headcount_amc_proxy
    ports:
      - "8000:8000"
      - "5001:5001"
    volumes:
      - ./amc_calibration/proxy.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - amc-backend
      - amc-ui
    restart: unless-stopped
    user: "101:101"

  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
    container_name: headcount_backend
    depends_on:
      - redis
      - deepstream
    environment:
      - REDIS_HOST=redis
      - DS_API_BASE=deepstream:8010
      - FLASK_ENV=production
    ports:
      - "5000:5000"
    volumes:
      - .:/app
      - ./data:/app/data
      - ./zones.json:/app/zones.json
    restart: unless-stopped

  # ... Other services remain unchanged (deepstream, amc-backend, amc-ui, mediamtx)
```

---

## Validation and Testing

### Pre-Migration Checklist
- [ ] Review file permissions in volumes
- [ ] Verify Nginx configuration listens on non-privileged ports
- [ ] Test Redis connectivity from backend service
- [ ] Validate Flask application startup

### Post-Migration Validation

#### Test Backend Build
```bash
docker build -t headcount-backend:dhi -f backend/Dockerfile .
```

#### Test Services
```bash
docker-compose up -d
docker-compose logs -f backend
docker-compose logs -f redis
docker-compose logs -f amc-proxy
```

#### Functional Verification
1. Backend Flask API responds on port 5000
2. Redis connectivity maintained (REDIS_HOST=redis)
3. Frontend React build artifacts served correctly
4. Nginx reverse proxy routes requests properly

### Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| Permission denied errors | Nonroot user cannot access mounted volumes | Ensure host volumes have appropriate permissions; use `chown` in Dockerfile |
| Flask app fails to start | Import errors or missing dependencies | Verify all pip packages copied from builder stage |
| Nginx fails to bind ports | Nonroot user attempting privileged port binding | Ensure Nginx config uses ports ≥1024; verify docker-compose port mapping is correct |
| Redis connection refused | Network isolation or connection string | Verify service name in REDIS_HOST environment variable; check docker network |

---

## Security and Reliability Benefits

### Security Enhancements
1. **Non-root Execution**: All containers run as unprivileged users by default, limiting blast radius of container breakouts
2. **Reduced CVE Surface**: Minimal Alpine-based images contain fewer packages and libraries, reducing exploitable vulnerabilities
3. **Supply Chain Security**: DHI images are maintained by Docker and regularly patched
4. **Explicit File Permissions**: Clear ownership prevents privilege escalation through file access

### Reliability Improvements
1. **Consistent Build Behavior**: Multi-stage builds separate build tools from runtime, preventing subtle dependency issues
2. **Faster Deployments**: Smaller image sizes mean faster pulls and starts
3. **Clear Separation of Concerns**: Build-time dependencies isolated from runtime, reducing unexpected failures
4. **Better Resource Utilization**: Alpine-based images reduce memory and disk footprint

---

## Rollback Plan

If issues arise after migration:

1. Revert backend/Dockerfile to use original node:20-alpine and python:3.10 images
2. Update docker-compose.yml to use redis:7-alpine and nginx:alpine
3. Rebuild and redeploy: `docker-compose down && docker-compose up -d`

Original images will continue to work; DHI migration is not destructive.

---

## References

- [Docker Hardened Images Documentation](https://docs.docker.com/desktop/hardened-desktop/hardened-images/)
- [Alpine Linux vs Standard Base Images](https://alpinelinux.org/)
- [Multi-stage Docker Builds](https://docs.docker.com/build/building/multi-stage/)
