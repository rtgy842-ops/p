#!/bin/sh
# ── docker-entrypoint.sh — Wait then exec, no DB touching ──
set -e
echo "=== NumGenius Entrypoint ==="
echo "Waiting for PostgreSQL..."
for i in $(seq 1 30); do
  python3 -c "
import psycopg2, os
try:
    dsn=os.getenv('DATABASE_URL','postgresql://smsbot:MyS3cur3Pssw0r@postgres:5432/smsbot')
    c=psycopg2.connect(dsn); c.close()
except: exit(1)
" 2>/dev/null && echo "PostgreSQL ready!" && break
  [ $i -eq 30 ] && echo "WARNING: PostgreSQL not ready"
  sleep 2
done

echo "Waiting for Redis..."
for i in $(seq 1 15); do
  python3 -c "
import redis, os
try:
    r=redis.from_url(os.getenv('CELERY_BROKER_URL','redis://redis:6379/0'))
    r.ping()
except: exit(1)
" 2>/dev/null && echo "Redis ready!" && break
  sleep 2
done

echo "Starting: $@"
exec "$@"