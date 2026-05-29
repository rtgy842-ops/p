#!/bin/sh
# ── docker-entrypoint.sh — Graceful Startup & Shutdown ──────
# Handles: migrations, health checks, signal trapping

set -e

echo "=== SMS Bot Platform Entrypoint ==="
echo "Mode: ${APP_ENV:-production}"

# ── Run migrations (all 3 databases) ─────────────────────
echo "Running database migrations..."
python -c "
from db.connection import ConnectionManager
from db.schema import ALL_SCHEMAS, DEFAULT_SETTINGS, INDEXES
from db.migrations import MigrationManager
import logging
logging.basicConfig(level=logging.INFO)

# Pre-create all tables across all databases BEFORE migrations
cm = ConnectionManager.get_instance()
for db_name, tables in ALL_SCHEMAS.items():
    conn = cm.get_connection(db_name)
    cursor = conn.cursor()
    for table_name, ddl in tables.items():
        try:
            cursor.execute(ddl)
            print(f'Table ensured: {db_name}.{table_name}')
        except Exception as e:
            print(f'Table {db_name}.{table_name} warning: {e}')
    conn.commit()
    print(f'Database initialized: {db_name}')

# Now run versioned migrations
mm = MigrationManager()
if mm.migrate():
    print('Migration complete')
else:
    print('WARNING: Migration had issues — continuing anyway')
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