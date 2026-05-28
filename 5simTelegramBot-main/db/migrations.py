"""
db/migrations.py — Versioned Migration System (Enterprise)
─────────────────────────────────────────────────
Complete migration system covering ALL tables.
Each migration is versioned, logged, and reversible.

Tables covered:
- users (with balance, language, phone, is_blocked)
- transactions (financial audit trail)
- orders (number purchases)
- card_payments (card-to-card payments)
- settings (key-value config)
- card_info (bank card info for payments)
- required_channels (mandatory join channels)
- operator_settings (SMS operator config)
- activation_codes (received SMS codes)
- _migrations (self-tracking table)

Usage:
    from db.migrations import MigrationManager
    mm = MigrationManager()
    mm.migrate()  # applies all pending migrations
"""

import sqlite3
import logging
from datetime import datetime
from config import DB_CONFIG

logger = logging.getLogger(__name__)

# ── Migration definitions ──────────────────────────────────────
MIGRATIONS: list[tuple[int, str, str | list[str], str | list[str]]] = [
    # Version 0: Baseline — _migrations tracking table
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

    # ── users_db tables ────────────────────────────────────────
    (
        1,
        'Create users table with all columns',
        '''
        CREATE TABLE IF NOT EXISTS users (
            user_id       INTEGER PRIMARY KEY,
            username      TEXT,
            first_name    TEXT,
            last_name     TEXT,
            join_date     DATETIME DEFAULT CURRENT_TIMESTAMP,
            balance       INTEGER DEFAULT 0,
            is_blocked    INTEGER DEFAULT 0,
            language      TEXT DEFAULT 'fa',
            phone         TEXT
        )
        ''',
        'DROP TABLE IF EXISTS users'
    ),
    (
        2,
        'Create transactions table (financial audit)',
        '''
        CREATE TABLE IF NOT EXISTS transactions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            amount      INTEGER NOT NULL,
            type        TEXT NOT NULL,
            description TEXT DEFAULT '',
            ref_id      TEXT,
            timestamp   DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        ''',
        'DROP TABLE IF EXISTS transactions'
    ),
    (
        3,
        'Create orders table (purchase records)',
        '''
        CREATE TABLE IF NOT EXISTS orders (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            service         TEXT,
            country         TEXT,
            phone_number    TEXT,
            price           INTEGER,
            status          TEXT DEFAULT 'active',
            order_id        TEXT UNIQUE,
            order_date      DATETIME DEFAULT CURRENT_TIMESTAMP,
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        ''',
        'DROP TABLE IF EXISTS orders'
    ),
    (
        4,
        'Create card_payments table (card-to-card payments)',
        '''
        CREATE TABLE IF NOT EXISTS card_payments (
            payment_id      TEXT PRIMARY KEY,
            user_id         INTEGER NOT NULL,
            amount          INTEGER NOT NULL,
            status          TEXT DEFAULT 'pending',
            receipt         TEXT,
            admin_response  TEXT,
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        ''',
        'DROP TABLE IF EXISTS card_payments'
    ),

    # ── admin_db tables ────────────────────────────────────────
    (
        5,
        'Create admin_settings table',
        '''
        CREATE TABLE IF NOT EXISTS settings (
            key         TEXT PRIMARY KEY,
            value       TEXT,
            updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''',
        'DROP TABLE IF EXISTS settings'
    ),
    (
        6,
        'Create admin_card_info table',
        '''
        CREATE TABLE IF NOT EXISTS card_info (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            card_number  TEXT,
            card_holder  TEXT,
            updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''',
        'DROP TABLE IF EXISTS card_info'
    ),
    (
        7,
        'Create required_channels table',
        '''
        CREATE TABLE IF NOT EXISTS required_channels (
            username      TEXT PRIMARY KEY,
            display_name  TEXT NOT NULL,
            invite_link   TEXT NOT NULL,
            added_date    DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''',
        'DROP TABLE IF EXISTS required_channels'
    ),
    (
        8,
        'Create operator_settings table',
        '''
        CREATE TABLE IF NOT EXISTS operator_settings (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            service       TEXT NOT NULL,
            country       TEXT NOT NULL,
            operator      TEXT NOT NULL,
            country_name  TEXT NOT NULL,
            UNIQUE(service, country)
        )
        ''',
        'DROP TABLE IF EXISTS operator_settings'
    ),

    # ── bot_db tables ──────────────────────────────────────────
    (
        9,
        'Create bot_orders table',
        '''
        CREATE TABLE IF NOT EXISTS orders (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            activation_id   INTEGER NOT NULL,
            service         TEXT NOT NULL,
            country         TEXT NOT NULL,
            operator        TEXT NOT NULL,
            phone           TEXT NOT NULL,
            price           INTEGER NOT NULL,
            status          TEXT NOT NULL DEFAULT 'PENDING',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''',
        'DROP TABLE IF EXISTS orders'
    ),
    (
        10,
        'Create activation_codes table',
        '''
        CREATE TABLE IF NOT EXISTS activation_codes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id    INTEGER NOT NULL,
            code        TEXT NOT NULL,
            status      TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (order_id) REFERENCES orders(id)
        )
        ''',
        'DROP TABLE IF EXISTS activation_codes'
    ),
    (
        11,
        'Create bot_settings table',
        '''
        CREATE TABLE IF NOT EXISTS settings (
            key    TEXT PRIMARY KEY,
            value  TEXT NOT NULL
        )
        ''',
        'DROP TABLE IF EXISTS settings'
    ),

    # ── Default settings seeding ───────────────────────────────
    (
        12,
        'Insert default settings (usd_rate, profit, channel_lock)',
        [
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('usd_rate', '0')",
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('profit_percentage', '30')",
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('channel_lock', 'false')",
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('usd_rate', '0')",
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('profit_percentage', '30')",
        ],
        "DELETE FROM settings WHERE key IN ('usd_rate', 'profit_percentage', 'channel_lock')"
    ),

    # ── Performance indexes ────────────────────────────────────
    (
        13,
        'Add performance indexes',
        [
            'CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id)',
            'CREATE INDEX IF NOT EXISTS idx_transactions_timestamp ON transactions(timestamp)',
            'CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id)',
            'CREATE INDEX IF NOT EXISTS idx_orders_order_id ON orders(order_id)',
            'CREATE INDEX IF NOT EXISTS idx_card_payments_user_id ON card_payments(user_id)',
            'CREATE INDEX IF NOT EXISTS idx_card_payments_status ON card_payments(status)',
        ],
        [
            'DROP INDEX IF EXISTS idx_transactions_user_id',
            'DROP INDEX IF EXISTS idx_transactions_timestamp',
            'DROP INDEX IF EXISTS idx_orders_user_id',
            'DROP INDEX IF EXISTS idx_orders_order_id',
            'DROP INDEX IF EXISTS idx_card_payments_user_id',
            'DROP INDEX IF EXISTS idx_card_payments_status',
        ]
    ),

    # ── Migration: add language column to existing users ───────
    (
        14,
        'Add language column to users (if upgrading from old schema)',
        "ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'fa'",
        "SELECT 1"
    ),
    (
        15,
        'Add phone column to users',
        'ALTER TABLE users ADD COLUMN phone TEXT',
        'SELECT 1'
    ),
    (
        16,
        'Add created_at column to orders',
        "ALTER TABLE orders ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP",
        'SELECT 1'
    ),
]


class MigrationManager:
    """Manages database schema migrations across all databases."""

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
        """Rollback migrations down to target_version."""
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
                stmt = stmt.strip()
                if stmt and stmt.upper() != 'SELECT 1':
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
