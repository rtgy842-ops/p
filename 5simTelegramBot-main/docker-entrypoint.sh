#!/bin/sh
# ── docker-entrypoint.sh — PostgreSQL Startup ─────────────
set -e
echo "=== SMS Bot Platform Entrypoint (PostgreSQL) ==="
echo "Mode: ${APP_ENV:-production}"

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL..."
for i in $(seq 1 30); do
  if python -c "
import psycopg2
try:
    conn = psycopg2.connect('${DATABASE_URL:-postgresql://smsbot:smsbot_secret@postgres:5432/smsbot}')
    conn.close()
    print('OK')
except: pass
" 2>/dev/null; then
    echo "PostgreSQL is ready!"
    break
  fi
  echo "  Waiting... ($i/30)"
  sleep 2
done

# Run migrations
echo "Running database migrations..."
python -c "
from db.connection import ConnectionManager
from db.schema import ALL_TABLES, DEFAULT_SETTINGS, INDEXES
from db.migrations import MigrationManager

cm = ConnectionManager.get_instance()
conn = cm.get_connection('default')
cursor = conn.cursor()

for table_name, ddl in ALL_TABLES.items():
    try:
        cursor.execute(ddl)
        print(f'Table ensured: {table_name}')
    except Exception as e:
        print(f'Table {table_name}: {e}')
conn.commit()
cm.put_connection(conn)

mm = MigrationManager()
if mm.migrate():
    print('Migration complete')
else:
    print('WARNING: Migration had issues')
"

# Start the main process
echo "Starting application: $@"
exec "$@"