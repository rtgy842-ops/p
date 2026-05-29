"""
db/migrations.py — Versioned Migrations (PostgreSQL)
─────────────────────────────────────────────────
All CREATE IF NOT EXISTS — idempotent, safe to re-run.
"""

import logging
from datetime import datetime
from db.connection import ConnectionManager
from db.schema import ALL_TABLES, DEFAULT_SETTINGS, INDEXES

logger = logging.getLogger(__name__)

MIGRATIONS = [
    (0, 'Create all tables (schema v1)', list(ALL_TABLES.values()), ''),
    (1, 'Insert default settings', [
        f"INSERT INTO settings (key, value) VALUES ('{k}', '{v}') ON CONFLICT (key) DO NOTHING"
        for k, v in DEFAULT_SETTINGS
    ], ''),
    (2, 'Create performance indexes', INDEXES, ''),
]


class MigrationManager:
    def __init__(self):
        self._cm = ConnectionManager.get_instance()

    def get_current_version(self) -> int:
        try:
            cursor = self._cm.execute('default',
                "SELECT MAX(version) FROM _migrations WHERE success = 1")
            row = cursor.fetchone()
            self._cm.put_connection(cursor.connection)
            return row[0] if row and row[0] is not None else -1
        except Exception:
            return -1

    def migrate(self, target_version: int | None = None) -> bool:
        current = self.get_current_version()
        target = target_version if target_version is not None else len(MIGRATIONS) - 1
        if current >= target:
            logger.info(f"DB at version {current}")
            return True

        pending = [m for m in MIGRATIONS if m[0] > current and m[0] <= target]
        logger.info(f"Migrating {current} → {target} ({len(pending)} steps)")

        for version, description, up_sql, _ in pending:
            try:
                logger.info(f"Migration {version}: {description}")
                statements = up_sql if isinstance(up_sql, list) else [up_sql]
                conn = self._cm.get_connection('default')
                cursor = conn.cursor()
                cursor.execute('BEGIN')
                for stmt in statements:
                    if stmt.strip():
                        cursor.execute(stmt)
                conn.commit()
                cursor.execute(
                    "INSERT INTO _migrations (version, description, success, applied_at) VALUES (%s, %s, %s, %s)",
                    (version, description, 1, datetime.now().isoformat()))
                cursor.close()
                conn.commit()
                self._cm.put_connection(conn)
                logger.info(f"Migration {version} complete")
            except Exception as e:
                logger.error(f"Migration {version} FAILED: {e}")
                try:
                    cursor.execute(
                        "INSERT INTO _migrations VALUES (%s, %s, %s, %s)",
                        (version, description, 0, datetime.now().isoformat()))
                except: pass
                return False

        logger.info(f"Migration complete. Version {self.get_current_version()}")
        return True
