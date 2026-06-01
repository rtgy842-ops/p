#!/bin/sh
# ── docker-entrypoint.sh — Wait for deps, run alembic, then exec ──
set -e
echo "=== NumGenius Entrypoint ==="

echo "Waiting for PostgreSQL..."
for i in $(seq 1 30); do
  python3 -c "
import psycopg2, os, sys
dsn = os.getenv('DATABASE_URL', '')
if not dsn:
    sys.exit(1)
try:
    c = psycopg2.connect(dsn)
    c.close()
except Exception:
    sys.exit(1)
" 2>/dev/null && echo "PostgreSQL ready!" && break
  [ "$i" -eq 30 ] && echo "WARNING: PostgreSQL not ready after 30 attempts"
  sleep 2
done

echo "Waiting for Redis..."
for i in $(seq 1 15); do
  python3 -c "
import redis, os, sys
url = os.getenv('CELERY_BROKER_URL', '')
if not url:
    sys.exit(1)
try:
    r = redis.from_url(url)
    r.ping()
except Exception:
    sys.exit(1)
" 2>/dev/null && echo "Redis ready!" && break
  sleep 2
done

# Run Alembic migrations — ONLY from customer_bot (prevents race condition from 4 simultaneous containers)
if [ -n "$BOT_TOKEN" ] && [ -z "$SKIP_ALEMBIC" ]; then
  echo "Running alembic upgrade head (customer_bot only)..."
  for i in $(seq 1 5); do
    python3 -m alembic upgrade head 2>/dev/null && echo "Alembic OK" && break
    echo "Alembic attempt $i failed, retrying in 2s..."
    sleep 2
  done
fi

echo "Starting: $@"
exec "$@"