#!/bin/sh
# ── docker-entrypoint.sh — Wait for dependencies, then exec ──
set -e
echo "=== NumGenius Entrypoint ==="

# Wait for PostgreSQL
echo "Waiting for PostgreSQL..."
for i in $(seq 1 30); do
  if python -c "
import psycopg2
try:
    conn = psycopg2.connect('${DATABASE_URL:-postgresql://smsbot:MyS3cur3Pssw0r@postgres:5432/smsbot}')
    conn.close()
    print('OK')
except: pass
" 2>/dev/null; then
    echo "PostgreSQL ready!"
    break
  fi
  [ $i -eq 30 ] && echo "WARNING: PostgreSQL not ready after 30 attempts"
  sleep 2
done

# Wait for Redis
echo "Waiting for Redis..."
for i in $(seq 1 15); do
  if python -c "
import redis
try:
    r = redis.from_url('${CELERY_BROKER_URL:-redis://redis:6379/0}')
    r.ping()
    print('OK')
except: pass
" 2>/dev/null; then
    echo "Redis ready!"
    break
  fi
  sleep 2
done

# The application handles migrations itself
echo "Starting: $@"
exec "$@"