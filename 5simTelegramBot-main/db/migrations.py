"""
db/migrations.py — Versioned Migration System
─────────────────────────────────────────────────
Simple, safe, logged migration system for SQLite.
Each migration has a version number, forward (up) and reverse (down) SQL.

Rules:
- Version numbers are sequential integers starting at 1
- Each migration is applied exactly once
- Applied migrations are tracked in a _migrations table
- Reversible: each migration has a 'down' SQL
- Safe: no migration is applied twice
- Logged: every migration is logged with timestamp

Usage:
    from db.migrations import MigrationManager
    mm = MigrationManager()
    mm.migrate()  # applies all pending migrations
    mm.rollback(1)  # rolls back to version 0
"""

import sqlite3
import logging
from datetime import datetime
from config import DB_CONFIG

logger = logging.getLogger(__name__)

# ── Migration definitions ──────────────────────────────────────
# Format: (version, description, up_sql, down_sql)

MIGRATIONS: list[tuple[int, str, str | list[str], str | list[str]]] = [
    # Version 0: Baseline — ensure _migrations table exists
    (
        0,
        'Create migrations tracking table',
        '''
        CREATE TABLE IF NOT EXISTS _migrations (
            version     INTEGER PRIMARY KEY,
            description TEXT NOT NULL,
            applied_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            success     INTEGER DEFAULT 1
        )
        ''',
        'DROP TABLE IF EXISTS _migrations'
    ),
    # Version 1: Add indexes for performance
    (
        1,
        'Add performance indexes to transactions and orders',
        [
            'CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id)',
            'CREATE INDEX IF NOT EXISTS idx_transactions_timestamp ON transactions(timestamp)',
            'CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id)',
            'CREATE INDEX IF NOT EXISTS idx_orders_order_id ON orders(order_id)',
        ],
        [
            'DROP INDEX IF EXISTS idx_transactions_user_id',
            'DROP INDEX IF EXISTS idx_transactions_timestamp',
            'DROP INDEX IF EXISTS idx_orders_user_id',
            'DROP INDEX IF EXISTS idx_orders_order_id',
        ]
    ),
    # Version 2: Add language column to users (if missing)
    (
        2,
        'Ensure language column exists on users table',
        "ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'fa'",
        # SQLite doesn't support DROP COLUMN easily; this is a no-op reverse
        "SELECT 1"
    ),
    # Version 3: Add phone column to users
    (
        3,
        'Ensure phone column exists on users table',
        'ALTER TABLE users ADD COLUMN phone TEXT',
        'SELECT 1'
    ),
]


class MigrationManager:
    """Manages database schema migrations."""

    def __init__(self):
        self._cm = None  # Lazy init

    @property
    def conn(self):
        if self._cm is None:
            from db.connection import ConnectionManager
            self._cm = ConnectionManager.get_instance()
        return self._cm.get_connection('users_db')

    def get_current_version(self) -> int:
        """Get the current migration version from the database."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='_migrations'"
            )
            if not cursor.fetchone():
                return -1  # No migrations table yet

            cursor.execute(
                'SELECT MAX(version) FROM _migrations WHERE success = 1'
            )
            result = cursor.fetchone()
            return result[0] if result and result[0] is not None else -1
        except Exception as e:
            logger.error(f"Error getting migration version: {e}")
            return -1

    def migrate(self, target_version: int | None = None) -> bool:
        """
        Apply all pending migrations up to target_version.
        If target_version is None, applies all.
        """
        current = self.get_current_version()
        target = target_version if target_version is not None else len(MIGRATIONS) - 1

        if current >= target:
            logger.info(f"Database already at version {current} (target: {target})")
            return True

        pending = [m for m in MIGRATIONS if m[0] > current and m[0] <= target]
        logger.info(
            f"Migrating from version {current} to {target} "
            f"({len(pending)} migrations pending)"
        )

        for version, description, up_sql, _down_sql in pending:
            try:
                logger.info(f"Applying migration {version}: {description}")
                self._execute_sql(up_sql)
                self._record_migration(version, description, True)
                logger.info(f"Migration {version} applied successfully")
            except Exception as e:
                logger.error(f"Migration {version} FAILED: {e}")
                try:
                    self._record_migration(version, description, False)
                except Exception:
                    pass
                return False

        final = self.get_current_version()
        logger.info(f"Migration complete. Database at version {final}")
        return True

    def rollback(self, target_version: int) -> bool:
        """
        Rollback migrations down to target_version.
        Applies 'down' SQL in reverse order.
        """
        current = self.get_current_version()
        if current <= target_version:
            logger.info(f"No rollback needed. Current: {current}, Target: {target_version}")
            return True

        reverts = [m for m in reversed(MIGRATIONS) if m[0] > target_version and m[0] <= current]
        logger.info(
            f"Rolling back from version {current} to {target_version} "
            f"({len(reverts)} migrations to revert)"
        )

        for version, description, _up_sql, down_sql in reverts:
            try:
                logger.info(f"Reverting migration {version}: {description}")
                self._execute_sql(down_sql)
                with self.conn:
                    cursor = self.conn.cursor()
                    cursor.execute(
                        'DELETE FROM _migrations WHERE version = ?', (version,)
                    )
                    self.conn.commit()
                logger.info(f"Migration {version} reverted successfully")
            except Exception as e:
                logger.error(f"Rollback {version} FAILED: {e}")
                return False

        final = self.get_current_version()
        logger.info(f"Rollback complete. Database at version {final}")
        return True

    def status(self) -> list[dict]:
        """Return migration status for all versions."""
        current = self.get_current_version()
        result = []
        for version, description, _up, _down in MIGRATIONS:
            result.append({
                'version': version,
                'description': description,
                'applied': version <= current,
            })
        return result

    def _execute_sql(self, sql: str | list[str]) -> None:
        """Execute SQL (string or list of strings) within a transaction."""
        statements = [sql] if isinstance(sql, str) else sql
        cursor = self.conn.cursor()
        try:
            cursor.execute('BEGIN')
            for stmt in statements:
                if stmt.strip() and stmt.strip().upper() != 'SELECT 1':
                    cursor.execute(stmt)
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def _record_migration(self, version: int, description: str, success: bool) -> None:
        """Record a migration in the _migrations table."""
        cursor = self.conn.cursor()
        cursor.execute(
            '''INSERT OR REPLACE INTO _migrations
               (version, description, success, applied_at)
               VALUES (?, ?, ?, ?)''',
            (version, description, 1 if success else 0, datetime.now().isoformat())
        )
        self.conn.commit()
