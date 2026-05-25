# DHI Migration - Implementation Checklist

## Pre-Deployment Phase

### Documentation Review
- [ ] Read DHI_MIGRATION_SUMMARY.md (executive overview)
- [ ] Read DHI_MIGRATION_GUIDE.md (detailed changes and rationale)
- [ ] Review docker-compose.dhi-services.yml (service configurations)
- [ ] Review DHI_VALIDATION_GUIDE.md (testing procedures)

### Configuration Preparation
- [ ] Review `amc_calibration/proxy.conf`:
  - [ ] Verify nginx listens on port 8000 (not 80)
  - [ ] Verify nginx listens on port 5001
  - [ ] Confirm NO privileged ports (<1024) in config
- [ ] Check host volume permissions:
  - [ ] `./data` directory is readable
  - [ ] `./zones.json` file is readable
- [ ] Backup current `docker-compose.yml`:
  ```bash
  cp docker-compose.yml docker-compose.yml.backup
  ```

### Backend Dockerfile Verification
- [ ] Confirm `backend/Dockerfile` uses DHI images:
  - [ ] `dhi.io/node:20-alpine-dev` (frontend builder)
  - [ ] `dhi.io/python:3.10-alpine-dev` (dependency builder)
  - [ ] `dhi.io/python:3.10-alpine` (runtime)
- [ ] File location: `D:\Work\Projects\headcount\backend\Dockerfile`
- [ ] No syntax errors in Dockerfile

---

## Build Phase

### Initial Image Build
- [ ] Navigate to project root:
  ```bash
  cd D:\Work\Projects\headcount
  ```
- [ ] Build image:
  ```bash
  docker build -t headcount-backend:dhi -f backend/Dockerfile .
  ```
- [ ] Monitor build output for:
  - [ ] Frontend npm install completes
  - [ ] Python pip dependency installation succeeds
  - [ ] opencv-python-headless forced reinstall completes
  - [ ] No error: "Permission denied"
  - [ ] No error: "ModuleNotFoundError"
  - [ ] Final image successfully tagged

### Build Troubleshooting
If build fails, check:
- [ ] Network connectivity for npm and pip downloads
- [ ] Python package version compatibility in `requirements.txt`
- [ ] File paths in COPY commands match actual directory structure
- [ ] Docker daemon has sufficient disk space

---

## Docker Compose Configuration Phase

### Update docker-compose.yml

**Make these changes**:

1. **Redis Service**:
   ```yaml
   redis:
     image: dhi.io/redis:7-alpine  # CHANGE from: redis:7-alpine
     # ... rest unchanged
   ```

2. **Nginx Service (amc-proxy)**:
   ```yaml
   amc-proxy:
     image: dhi.io/nginx:alpine  # CHANGE from: nginx:alpine
     user: "101:101"  # ADD this line
     # ... rest unchanged
   ```

3. **Backend Service**:
   - No changes needed (already uses updated Dockerfile)

### Validation Checklist
- [ ] Syntax is valid YAML (no indentation errors)
- [ ] All services properly defined
- [ ] Port mappings unchanged
- [ ] Volume mounts preserved
- [ ] Environment variables preserved
- [ ] No duplicate service definitions

---

## Pre-Deployment Testing Phase

### Image Inspection
- [ ] Check image size:
  ```bash
  docker images headcount-backend:dhi
  ```
  - Expected: Reasonable size (typically 500-700 MB)

- [ ] Inspect image layers:
  ```bash
  docker image inspect headcount-backend:dhi
  ```
  - [ ] Verify 3 distinct build stages present

### Isolated Container Test
- [ ] Start backend container standalone:
  ```bash
  docker run -it --rm \
    -p 5000:5000 \
    -v D:\Work\Projects\headcount\data:/app/data \
    -v D:\Work\Projects\headcount\zones.json:/app/zones.json \
    -e FLASK_APP=app.py \
    -e PYTHONUNBUFFERED=1 \
    headcount-backend:dhi
  ```

- [ ] Verify:
  - [ ] Container starts without errors
  - [ ] Flask application initializes
  - [ ] No permission errors
  - [ ] Listens on port 5000

- [ ] Test connectivity (in separate terminal):
  ```bash
  curl http://localhost:5000/
  ```
  - [ ] Connection succeeds (HTTP response received)

- [ ] Stop container: `Ctrl+C`

### Compose Build Test
- [ ] Run compose build:
  ```bash
  docker-compose build --no-cache
  ```
  - [ ] All services build successfully
  - [ ] No missing image errors
  - [ ] No dependency conflicts

---

## Deployment Phase

### Pre-Deployment Backup
- [ ] Backup docker-compose.yml:
  ```bash
  cp docker-compose.yml docker-compose.yml.backup
  ```
- [ ] Document current image versions running:
  ```bash
  docker-compose images > images-before.txt
  ```

### Stop Existing Services (if running)
- [ ] Gracefully stop services:
  ```bash
  docker-compose down
  ```
- [ ] Verify no containers running:
  ```bash
  docker-compose ps
  ```

### Deploy New Stack
- [ ] Start services with DHI images:
  ```bash
  docker-compose up -d
  ```
- [ ] Wait 5-10 seconds for services to initialize
- [ ] Check services status:
  ```bash
  docker-compose ps
  ```
  - [ ] All services show "Up" status
  - [ ] No services in "Exit" or "Error" state

### Log Inspection
- [ ] Check backend logs:
  ```bash
  docker-compose logs backend
  ```
  - [ ] No error messages
  - [ ] Flask app started successfully

- [ ] Check redis logs:
  ```bash
  docker-compose logs redis
  ```
  - [ ] Redis ready to accept connections

- [ ] Check nginx logs (if applicable):
  ```bash
  docker-compose logs amc-proxy
  ```
  - [ ] Nginx master process started
  - [ ] Listening on ports 8000 and 5001

---

## Post-Deployment Validation Phase

### Critical Functional Tests
- [ ] **Backend Connectivity**:
  ```bash
  curl -v http://localhost:5000/
  ```
  - [ ] HTTP response received (no connection refused)

- [ ] **Redis Connectivity**:
  ```bash
  docker-compose exec backend redis-cli -h redis ping
  ```
  - [ ] Response: "PONG"

- [ ] **Frontend Assets**:
  ```bash
  docker-compose exec backend ls -la /app/frontend/dist/
  ```
  - [ ] index.html present
  - [ ] JavaScript and CSS files present

- [ ] **Volume Accessibility**:
  ```bash
  docker-compose exec backend ls -la /app/data/
  ```
  - [ ] Directory listing succeeds
  - [ ] No permission errors

- [ ] **Configuration File Access**:
  ```bash
  docker-compose exec backend cat /app/zones.json
  ```
  - [ ] File contents displayed
  - [ ] No permission errors

### Non-Root User Verification
- [ ] Backend container user:
  ```bash
  docker-compose exec backend whoami
  ```
  - [ ] Output is NOT "root"

- [ ] Redis container user:
  ```bash
  docker-compose exec redis whoami
  ```
  - [ ] Output is NOT "root"

- [ ] Nginx container user (if running):
  ```bash
  docker-compose exec amc-proxy whoami
  ```
  - [ ] Output is NOT "root"

### Service Restart Recovery
- [ ] Restart backend service:
  ```bash
  docker-compose restart backend
  ```
  - [ ] Service recovers without errors

- [ ] Restart all services:
  ```bash
  docker-compose restart
  ```
  - [ ] All services restart successfully
  - [ ] All services return to "Up" state

---

## Extended Testing Phase

### Load and Stress Testing (Optional but Recommended)
- [ ] Monitor resource usage:
  ```bash
  docker stats --no-stream
  ```
  - [ ] Memory usage reasonable
  - [ ] CPU usage normal

- [ ] Test service failover:
  - [ ] Stop Redis: `docker-compose stop redis`
  - [ ] Observe backend behavior (should handle gracefully)
  - [ ] Start Redis: `docker-compose start redis`
  - [ ] Backend reconnects automatically

### Multi-Service Testing
- [ ] Verify service-to-service communication:
  - [ ] Backend reaches Redis via hostname
  - [ ] Backend accesses frontend assets
  - [ ] Nginx routes to expected backends

---

## Security Verification Phase

### Non-Root Execution Verification
- [ ] Check all containers:
  ```bash
  docker-compose ps --format "table {{.Names}}\t{{.Status}}"
  ```
  - [ ] All containers running

- [ ] Verify each runs as non-root:
  ```bash
  for service in backend redis amc-proxy; do
    echo "=== $service ==="
    docker-compose exec $service whoami
  done
  ```
  - [ ] None output "root"

### File Permission Verification
- [ ] Backend app permissions:
  ```bash
  docker-compose exec backend stat /app
  ```
  - [ ] Accessible to non-root user

- [ ] Data directory permissions:
  ```bash
  docker-compose exec backend stat /app/data
  ```
  - [ ] Readable by non-root user

---

## Rollback Procedure (If Needed)

### Quick Rollback
If critical issues occur:

1. Stop current services:
   ```bash
   docker-compose down
   ```

2. Restore backup config:
   ```bash
   cp docker-compose.yml.backup docker-compose.yml
   ```

3. Revert backend/Dockerfile to original (or use git):
   ```bash
   git checkout backend/Dockerfile
   ```

4. Restart with original images:
   ```bash
   docker-compose up -d
   ```

### Validation After Rollback
- [ ] Services start successfully
- [ ] Backends respond normally
- [ ] No data loss detected

---

## Post-Migration Documentation

### Record Migration Details
- [ ] Migration Date: _______________
- [ ] Migration Time: _______________
- [ ] Performed By: _______________

### Performance Comparison (Optional)
- [ ] Image Size Before: ________________
- [ ] Image Size After: ________________
- [ ] Memory Usage Before: ______________
- [ ] Memory Usage After: ______________

### Issues Encountered
- [ ] Issue 1: ________________ → Resolution: ________________
- [ ] Issue 2: ________________ → Resolution: ________________
- [ ] Issue 3: ________________ → Resolution: ________________

### Approved By
- [ ] Technical Lead: ________________ Date: _______________
- [ ] Deployment Manager: ________________ Date: _______________

---

## Final Sign-Off

### Migration Success Criteria
- [x] Backend Dockerfile migrated to DHI
- [x] docker-compose services updated (recommendations provided)
- [x] All documentation provided
- [x] No functional regression
- [ ] All containers running as non-root
- [ ] All validation tests passing
- [ ] No permission-related errors
- [ ] Service connectivity verified

### Final Checklist
- [ ] This checklist completed
- [ ] All validation tests passed
- [ ] Team trained on new configuration
- [ ] Backup of original config maintained
- [ ] Documentation reviewed and understood

---

**Migration Status**: READY FOR DEPLOYMENT

**Deployment Authorized By**: _____________________________

**Deployment Date**: _____________________________

**Deployment Completed By**: _____________________________

**Migration Validation Completed**: ☐ YES ☐ NO

**Date Validation Completed**: _____________________________

**Validated By**: _____________________________

---

**End of Implementation Checklist**
