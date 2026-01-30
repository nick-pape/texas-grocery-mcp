# Dockerfile
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN pip install --no-cache-dir hatch

# Copy project files
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Build wheel
RUN hatch build -t wheel

# Production image
FROM python:3.11-slim

WORKDIR /app

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser

# Copy wheel from builder
COPY --from=builder /app/dist/*.whl ./

# Install the package
RUN pip install --no-cache-dir *.whl && rm *.whl

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import texas_grocery_mcp; print('ok')" || exit 1

# Default environment
ENV LOG_LEVEL=INFO
ENV ENVIRONMENT=production

# Run the MCP server
ENTRYPOINT ["texas-grocery-mcp"]
