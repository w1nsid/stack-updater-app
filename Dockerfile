# Build stage
FROM ghcr.io/astral-sh/uv:python3.11-alpine AS builder

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./

RUN uv sync --frozen --no-dev --compile-bytecode

COPY app/ ./app/
COPY main.py ./

# Production stage
FROM ghcr.io/astral-sh/uv:python3.11-alpine

# Security: run as non-root user
RUN addgroup -g 1000 appgroup && \
    adduser -u 1000 -G appgroup -h /home/appuser -D appuser && \
    mkdir -p /app

WORKDIR /app

# Copy from builder
COPY --from=builder --chown=appuser:appgroup /app /app

# Create data directory for SQLite
RUN mkdir -p /app/data && chown appuser:appgroup /app/data

# Switch to non-root user
USER appuser

# Environment defaults for production
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATABASE_URL=sqlite:////app/data/app.db \
    LOG_FILE=/app/data/app.log \
    UV_NO_CACHE=1

EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:8080/api/stacks || exit 1

# Production server with optimized settings
CMD ["uv", "run", "uvicorn", "app.main:app", \
    "--host", "0.0.0.0", \
    "--port", "8080", \
    "--workers", "1", \
    "--proxy-headers", \
    "--forwarded-allow-ips", "*"]