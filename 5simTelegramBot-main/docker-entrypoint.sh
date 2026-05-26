#!/bin/sh
# ── docker-entrypoint.sh — Graceful Startup & Shutdown ──────
# Handles: migrations, health checks, signal trapping

set -e

echo "=== SMS Bot Platform Entrypoint ==="
echo "Mode: ${APP_ENV:-production}"

# ── Run migrations ─────────────────────────────────────────
echo "Running database migrations..."
python -c "
from db.migrations import MigrationManager
mm = MigrationManager()
if mm.migrate():
    print('Migration complete')
else:
    print('WARNING: Migration failed — continuing anyway')
"

# ── Trap signals for graceful shutdown ─────────────────────
trap 'echo "Received SIGTERM — shutting down gracefully..."; kill -TERM $PID; wait $PID; exit 0' TERM INT

# ── Execute the main process ───────────────────────────────
echo "Starting application: $@"
exec "$@" &
PID=$!

# ── Wait for process ───────────────────────────────────────
wait $PID
EXIT_CODE=$?
echo "Application exited with code $EXIT_CODE"
exit $EXIT_CODE