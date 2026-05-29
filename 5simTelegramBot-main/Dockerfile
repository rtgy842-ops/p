# ── Multi-stage production Dockerfile ───────────────────────
# Stage 1: Build
FROM python:3.11-slim-bookworm AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libc-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Production
FROM python:3.11-slim-bookworm AS production

# Create non-root user
RUN groupadd -r botuser && useradd -r -g botuser botuser

# Install runtime deps + PostgreSQL client libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates libpq-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /root/.local /home/botuser/.local

# Copy application code
COPY --chown=botuser:botuser . .

# Create writable directories
RUN mkdir -p /app/logs /app/data/backups && \
    chown -R botuser:botuser /app

# Ensure scripts are executable
RUN chmod +x docker-entrypoint.sh 2>/dev/null || true

# Use non-root user
USER botuser

# Add local bin to PATH
ENV PATH=/home/botuser/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV FLASK_APP=bot.py

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:5000/ping || exit 1

EXPOSE 5000

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["python", "bot.py"]