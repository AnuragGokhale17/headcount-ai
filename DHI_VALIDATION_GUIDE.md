# DHI Migration - Build Validation & Testing Guide

## Overview
This guide provides step-by-step instructions to validate the DHI migration and ensure all functionality is preserved.

---

## Phase 1: Image Build Validation

### 1.1 Backend Dockerfile Build Test

**Command**:
```bash
cd D:\Work\Projects\headcount
docker build -t headcount-backend:dhi -f backend/Dockerfile .
```

**Expected Output**:
```
Step 1/X : FROM dhi.io/node:20-alpine-dev AS frontend-builder
Step 2/X : WORKDIR /build
...
Step N/X : CMD ["python", "app.py"]
Successfully tagged headcount-backend:dhi
```

**Validation Points**:
- [ ] Frontend React build completes without errors
- [ ] Python dependency installation succeeds (watch for pip timeout errors)
- [ ] opencv-python-headless forced reinstall completes
- [ ] Final layer tagging succeeds
- [ ] No permission errors in RUN commands

**Common Build Issues & Fixes**:

| Error | Cause | Fix |
|-------|-------|-----|
| `npm ERR! network timeout` | Frontend dependency download timeout | Retry build or check network connectivity |
| `ERROR: Could not find a version that satisfies...` | Python package version conflict | Check requirements.txt versions compatibility |
| `Permission denied` | Build container nonroot user cannot write | Rebuild with `--build-arg BUILDKIT_CONTEXT_KEEP_GIT_DIR=1` |
| `ModuleNotFoundError` | Missing Python dependency in site-packages copy | Verify COPY commands in Stage 2 and Stage 3 |

### 1.2 Inspect Built Image

**Command**:
```bash
docker image inspect headcount-backend:dhi
```

**Validate**:
- [ ] Image size is reasonable (should be smaller than original python:3.10)
- [ ] `RootFS.Layers` shows 3 distinct build stages
- [ ] No unnecessary bloat in final layers

**Command** (check image size):
```bash
docker images | grep headcount-backend
```

**Expected Output**:
```
REPOSITORY              TAG      IMAGE ID      CREATED         SIZE
headcount-backend       dhi      <hash>        X seconds ago   ~500-700MB
```

---

## Phase 2: Container Runtime Validation

### 2.1 Start Container in Isolation

**Command**:
```bash
docker run -it --rm \
  -p 5000:5000 \
  -v D:\Work\Projects\headcount\data:/app/data \
  -v D:\Work\Projects\headcount\zones.json:/app/zones.json \
  -e FLASK_APP=app.py \
  -e PYTHONUNBUFFERED=1 \
  headcount-backend:dhi
```

**Expected Behavior**:
- Container starts without permission errors
- Flask application initializes
- Application listens on port 5000
- No import errors or missing dependencies

**Watch for**:
- `PermissionError` → File ownership issue
- `ModuleNotFoundError` → Missing Python package
- `Connection refused` → Port binding issue (should not occur with port 5000)

### 2.2 Test Flask Health Endpoint

**In another terminal**:
```bash
curl -v http://localhost:5000/health
```

**Expected Response**:
- HTTP 200 or 404 (depending on whether /health endpoint exists)
- Connection established successfully

**If Connection Refused**:
- Verify Flask app started in container
- Check logs with: `docker logs <container_id>`
- Verify port 5000 is exposed in Dockerfile (line: `EXPOSE 5000`)

---

## Phase 3: Docker Compose Integration Testing

### 3.1 Update docker-compose.yml

**Before running**:
1. Verify `backend/Dockerfile` is in place (DHI version)
2. Update `docker-compose.yml` services section:
   - Change `redis: image: redis:7-alpine` → `dhi.io/redis:7-alpine`
   - Change `amc-proxy: image: nginx:alpine` → `dhi.io/nginx:alpine`
3. Verify `amc_calibration/proxy.conf` uses ports 8000 and 5001

### 3.2 Compose Build Test

**Command**:
```bash
cd D:\Work\Projects\headcount
docker-compose build --no-cache
```

**Expected**:
- Backend service builds successfully using DHI images
- No errors or warnings about missing images

### 3.3 Compose Service Start

**Command**:
```bash
docker-compose up -d
```

**Verification** (wait 5-10 seconds):
```bash
docker-compose ps
```

**Expected Output**:
```
NAME                      STATUS              PORTS
headcount_backend         Up X seconds        0.0.0.0:5000->5000/tcp
headcount_redis           Up X seconds        0.0.0.0:6379->6379/tcp
headcount_amc_proxy       Up X seconds        0.0.0.0:8000->8000/tcp, 0.0.0.0:5001->5001/tcp
...
```

### 3.4 Service Logs Inspection

**Check Backend Logs**:
```bash
docker-compose logs backend
```

**Expected**:
- Flask application starts successfully
- No AttributeError or PermissionError messages
- Environment variables loaded correctly

**Check Redis Logs**:
```bash
docker-compose logs redis
```

**Expected**:
- Redis server ready to accept connections
- No permission or binding errors

**Check Nginx Logs** (if applicable):
```bash
docker-compose logs amc-proxy
```

**Expected**:
- Nginx master process started
- Listening on ports 8000 and 5001
- No "Permission denied" errors

---

## Phase 4: Functionality Testing

### 4.1 Backend API Connectivity

**Test Flask endpoint**:
```bash
curl -X GET http://localhost:5000/
```

**Expected**: 
- HTTP response (200, 404, or application-specific status)
- Connection succeeds

### 4.2 Redis Connectivity

**From Backend Container**:
```bash
docker-compose exec backend redis-cli -h redis ping
```

**Expected Output**:
```
PONG
```

**If Connection Refused**:
- Verify Redis service is running: `docker-compose ps redis`
- Check Redis logs: `docker-compose logs redis`
- Verify REDIS_HOST environment variable: `docker-compose exec backend printenv | grep REDIS`

### 4.3 Frontend Assets

**Verify React build was copied**:
```bash
docker-compose exec backend ls -la /app/frontend/dist/
```

**Expected**:
- `index.html` present
- `*.js` and `*.css` files present
- Directory is readable by container process

**Test asset serving**:
```bash
curl -v http://localhost:5000/static/ || curl -v http://localhost:5000/frontend/dist/
```

### 4.4 Volume Mounts

**Verify /app/data is accessible**:
```bash
docker-compose exec backend ls -la /app/data/
```

**Expected**:
- Directory listing succeeds
- Files are readable and writable

**Verify zones.json is accessible**:
```bash
docker-compose exec backend cat /app/zones.json
```

**Expected**:
- JSON content displayed without permission errors

---

## Phase 5: Non-Root User Verification

### 5.1 Confirm Container User

**Backend Container**:
```bash
docker-compose exec backend whoami
```

**Expected Output** (nonroot user):
```
python
```

**Redis Container**:
```bash
docker-compose exec redis whoami
```

**Expected Output**:
```
redis
```

**Nginx Container**:
```bash
docker-compose exec amc-proxy whoami
```

**Expected Output**:
```
nginx
```

### 5.2 Permission Verification

**Check /app ownership in backend**:
```bash
docker-compose exec backend stat /app/ | grep Uid
```

**Expected**: User can read (at minimum) /app and subdirectories

---

## Phase 6: Load Testing & Performance

### 6.1 Memory Usage

**Baseline Comparison**:
```bash
# DHI migrated
docker stats headcount_backend --no-stream

# Original (if running in parallel for comparison)
# ... record memory usage for later comparison
```

**Expected**: DHI images typically use 10-20% less memory than standard images

### 6.2 Response Time

**Simple Load Test**:
```bash
# Requires Apache Bench or similar tool
# ab -n 100 -c 10 http://localhost:5000/
```

**Expected**: Consistent response times, no degradation under load

---

## Phase 7: Failure Recovery Testing

### 7.1 Container Restart

**Stop and Restart**:
```bash
docker-compose restart backend
```

**Expected**:
- Container restarts within 5 seconds
- Application recovers to running state
- No data loss in persistent volumes

### 7.2 Service Dependency Recovery

**Stop Redis, then restart**:
```bash
docker-compose stop redis
# Wait 10 seconds
docker-compose start redis
```

**Expected**:
- Backend handles Redis disconnection gracefully
- Backend reconnects when Redis restarts

### 7.3 Compose Stack Restart

**Full stack restart**:
```bash
docker-compose down
docker-compose up -d
```

**Expected**:
- All services start successfully
- Services reach running state
- No orphaned containers or dangling volumes

---

## Phase 8: Image Size Comparison

### Before vs After Analysis

**Original Images Size Estimation**:
```bash
docker images | grep "node:20-alpine\|python:3.10"
```

**DHI Images Size** (after build):
```bash
docker images | grep headcount-backend
docker images | grep "dhi.io"
```

**Expected Savings**:
- Backend image: ~15-25% smaller with DHI Alpine
- Reduced pull time, faster deployment
- Lower storage requirements

**Calculate**:
```bash
# Get original size
docker images python:3.10 --format "{{.Size}}"

# Get DHI size (from headcount-backend final layer)
docker images headcount-backend:dhi --format "{{.Size}}"
```

---

## Validation Checklist

### Critical Path (Must Pass)
- [ ] Backend Dockerfile builds without errors
- [ ] Container starts and Flask app initializes
- [ ] Port 5000 responds to requests
- [ ] Redis connection works
- [ ] Frontend assets present and accessible
- [ ] Volumes mount and are accessible
- [ ] Container runs as non-root user

### Extended Path (Should Pass)
- [ ] docker-compose up succeeds for all services
- [ ] All services reach healthy state
- [ ] No permission errors in logs
- [ ] Health checks pass (if defined)
- [ ] Memory usage acceptable
- [ ] Service restarts work correctly

### Optional (Nice to Have)
- [ ] Image size reduced vs original
- [ ] Response times acceptable
- [ ] Load testing passes
- [ ] Multi-service failover scenarios work

---

## Troubleshooting Decision Tree

```
Build fails?
├─ npm error → Check network, retry build
├─ pip error → Check Python versions in requirements.txt
├─ Permission error → Verify Dockerfile layer permissions
└─ Unknown → docker build -v (verbose output)

Container won't start?
├─ ModuleNotFoundError → COPY from python-builder stage missing
├─ PermissionError → File ownership in volumes incorrect
├─ Connection refused → Port mapping or Flask app not running
└─ OOM → Image too large, check layer content

Service connectivity fails?
├─ Redis: Check REDIS_HOST env var, verify redis service running
├─ Nginx: Check proxy.conf uses ports 8000/5001
├─ Frontend: Verify /app/frontend/dist exists and readable
└─ Volumes: Check host permissions on mounted directories
```

---

## Sign-Off

Migration validation is complete when:
1. Backend builds successfully with DHI images
2. All containers run as non-root users
3. Functional tests pass (Redis, Flask, volumes, assets)
4. docker-compose orchestration works
5. No security warnings or permission errors

Record validation completion date: ________________
Validated by: ________________________________
