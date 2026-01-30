# Code Review: Task 12

**Date**: 2026-01-29
**Reviewer**: code-review agent
**Status**: CHANGES REQUESTED

## Files Reviewed

| File | Lines Changed | Status |
|------|---------------|--------|
| `Dockerfile` | +43 | Issues Found |
| `docker-compose.yml` | +34 | Issues Found |

## Summary

The Docker configuration implements the core requirements well: multi-stage build, non-root user, health checks, and proper service orchestration. However, there are several security and operational issues that should be addressed before deployment.

---

## Issues Found

### Must-Fix Issues

These must be addressed before approval.

#### Issue 1: Missing .dockerignore File
**File**: `.dockerignore` (missing)
**Line(s)**: N/A
**Severity**: Must-Fix

**Problem**:
Without a .dockerignore file, the Docker build context will include unnecessary files like .venv, .git, .pytest_cache, .mypy_cache, .ruff_cache, and potentially sensitive files. This increases build context size, slows down builds, and risks copying secrets into the image.

**Current Code**:
File does not exist.

**Recommendation**:
Create a .dockerignore file with:
```
.venv/
.git/
.pytest_cache/
.mypy_cache/
.ruff_cache/
__pycache__/
*.pyc
*.pyo
*.pyd
.env
.env.*
!.env.example
*.log
firebase-debug.log
docs/
tests/
.gitignore
.claude/
uv.lock
```

---

#### Issue 2: Exposed Redis Port in Production
**File**: `docker-compose.yml`
**Line(s)**: 22-23
**Severity**: Must-Fix

**Problem**:
Redis port 6379 is exposed to the host, which is a security risk in production. Redis should only be accessible within the Docker network for this use case, as the MCP server is the only service that needs to access it.

**Current Code**:
```yaml
# Line 22-23
ports:
  - "6379:6379"
```

**Recommendation**:
Remove the ports mapping entirely, or make it optional via a profile/comment:
```yaml
# Uncomment only for local debugging
# ports:
#   - "6379:6379"
```

The texas-grocery-mcp service can still access Redis via the service name `redis:6379` on the internal Docker network.

---

#### Issue 3: Health Check Command Not Suitable for MCP Server
**File**: `Dockerfile`
**Line(s)**: 34-35
**Severity**: Must-Fix

**Problem**:
The health check only verifies that the Python package can be imported, which doesn't actually test if the MCP server is running and responsive. An MCP server is a long-running process that communicates via stdio, so importing the module proves nothing about the server's health.

**Current Code**:
```dockerfile
# Line 34-35
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import texas_grocery_mcp; print('ok')" || exit 1
```

**Recommendation**:
Since this is an MCP server that uses stdio (not HTTP), a better health check would verify the process is running or check Redis connectivity:
```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD pgrep -f texas-grocery-mcp || exit 1
```

Or check Redis connectivity since it's a critical dependency:
```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import redis; r = redis.from_url('redis://redis:6379'); r.ping()" || exit 1
```

Note: The second option requires redis to be available in the final image (which it is, via dependencies).

---

#### Issue 4: Volume Mount with Read-Only May Break Session Management
**File**: `docker-compose.yml`
**Line(s)**: 9
**Severity**: Important

**Problem**:
The auth state directory is mounted as read-only (`:ro`), but based on the system design, the MCP server needs to write session state back to this directory. If the server needs to refresh tokens or update session data, it will fail with permission errors.

**Current Code**:
```yaml
# Line 9
- ~/.texas-grocery-mcp:/home/appuser/.texas-grocery-mcp:ro
```

**Recommendation**:
Either make it read-write:
```yaml
- ~/.texas-grocery-mcp:/home/appuser/.texas-grocery-mcp
```

Or clarify in documentation/comments if the intention is that session state should only be stored in Redis (not filesystem), and the mounted directory is truly read-only for initial auth tokens.

---

### Nice-to-Have Improvements

These are suggestions, not blockers.

#### Suggestion 1: Add Version Pinning for Base Images
**File**: `Dockerfile`
**Line(s)**: 2, 17
**Category**: Security / Reproducibility

**Current**:
```dockerfile
FROM python:3.11-slim as builder
...
FROM python:3.11-slim
```

**Suggested**:
Pin to specific digest or more specific version:
```dockerfile
FROM python:3.11.8-slim as builder
...
FROM python:3.11.8-slim
```

**Rationale**:
Using exact versions ensures reproducible builds and prevents unexpected breakage from upstream changes. The `3.11-slim` tag is a moving target.

---

#### Suggestion 2: Add Build Metadata Labels
**File**: `Dockerfile`
**Line(s)**: 17-19
**Category**: Best Practice

**Current**:
No labels present in the production image.

**Suggested**:
Add standard OCI labels:
```dockerfile
LABEL org.opencontainers.image.title="Texas Grocery MCP"
LABEL org.opencontainers.image.description="MCP server for HEB grocery store integration"
LABEL org.opencontainers.image.version="0.1.0"
LABEL org.opencontainers.image.source="https://github.com/yourusername/texas-grocery-mcp"
```

**Rationale**:
Makes it easier to identify and manage images in registries.

---

#### Suggestion 3: Add Restart Policy
**File**: `docker-compose.yml`
**Line(s)**: 5-18
**Category**: Reliability

**Current**:
No restart policy defined.

**Suggested**:
```yaml
texas-grocery-mcp:
  build: .
  restart: unless-stopped
  # ... rest of config
```

**Rationale**:
If the MCP server crashes or the system reboots, the container should automatically restart. `unless-stopped` is safer than `always` for development.

---

#### Suggestion 4: Optimize Layer Caching
**File**: `Dockerfile`
**Line(s)**: 10-11
**Category**: Performance

**Current**:
```dockerfile
COPY pyproject.toml README.md ./
COPY src/ ./src/
```

**Suggested**:
Copy pyproject.toml first, install dependencies in a separate layer, then copy source:
```dockerfile
COPY pyproject.toml README.md ./
# If dependencies are defined in pyproject.toml, install them first
COPY src/ ./src/
```

**Rationale**:
Currently this is already fairly optimized since hatch handles the build. However, if you wanted to separate dependency installation from source copying, you could improve cache hits when only source code changes.

Actually, on review, the current approach is fine for a wheel-based build. This is a low-priority suggestion.

---

#### Suggestion 5: Document Environment Variables
**File**: `docker-compose.yml`
**Line(s)**: 10-13
**Category**: Documentation

**Current**:
Environment variables are listed but not documented.

**Suggested**:
Add comments explaining each variable:
```yaml
environment:
  # Redis connection URL (required)
  - REDIS_URL=redis://redis:6379
  # Logging level: DEBUG, INFO, WARNING, ERROR
  - LOG_LEVEL=${LOG_LEVEL:-INFO}
  # Optional: Default HEB store ID for operations
  - HEB_DEFAULT_STORE=${HEB_DEFAULT_STORE:-}
```

**Rationale**:
Makes it easier for others to understand and configure the service.

---

#### Suggestion 6: Add Resource Limits
**File**: `docker-compose.yml`
**Line(s)**: 5-18
**Category**: Reliability

**Current**:
No resource limits defined.

**Suggested**:
```yaml
texas-grocery-mcp:
  build: .
  deploy:
    resources:
      limits:
        cpus: '1'
        memory: 512M
      reservations:
        cpus: '0.5'
        memory: 256M
```

**Rationale**:
Prevents the service from consuming excessive resources and helps with capacity planning. Adjust limits based on actual usage patterns.

---

## What's Good

- Multi-stage build properly separates build-time and runtime dependencies
- Non-root user (appuser) is correctly implemented
- Health checks are present for both services
- Service dependencies are properly configured with health check conditions
- Redis data persistence is configured via named volume
- Environment variables follow 12-factor app principles
- Proper use of ENTRYPOINT for the main process
- stdin_open and tty flags correctly set for stdio-based MCP server
- Redis uses lightweight alpine image

## Checklist Summary

| Category | Status |
|----------|--------|
| Code Quality | PASS |
| Patterns & Conventions | PASS |
| Potential Issues | ISSUES |
| Performance | PASS |
| Documentation | MINOR ISSUES |
| Basic Security | ISSUES |

