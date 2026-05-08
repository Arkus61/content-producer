# ── Stage 1: Build venv with dependencies ──
FROM python:3.11-slim AS builder

WORKDIR /build

# System deps for building wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Install deps to isolated venv
COPY requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# ── Stage 2: Runtime (slim, no build tools) ──
FROM python:3.11-slim AS runtime

WORKDIR /app

# Runtime system deps (ffmpeg for audio/video, libpq for psycopg)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libpq5 curl && \
    rm -rf /var/lib/apt/lists/*

# Copy venv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy source (exclude tests — smaller image)
COPY pyproject.toml .
COPY src/ src/

# Create data dirs with writable permissions
RUN mkdir -p data/memory data/reflections experts && \
    chmod 777 data/memory data/reflections experts

EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run with 2 workers for production (CPU-bound: 2 × CPU cores)
CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
