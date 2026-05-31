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
    (0, 'Create all core tables (schema v1)', list(ALL_TABLES.values()), ''),
    (1, 'Insert default settings', [
        f"INSERT INTO settings (key, value) VALUES ('{k}', '{v}') ON CONFLICT (key) DO NOTHING"
        for k, v in DEFAULT_SETTINGS
    ], ''),
    (2, 'Create performance indexes', INDEXES, ''),
    (3, 'Seed default currency (USD)', [
        "INSERT INTO currencies (code, name, symbol, rate_to_usd, is_active, is_default) VALUES ('USD', 'US Dollar', '$', 1.0, 1, 1) ON CONFLICT (code) DO NOTHING",
    ], ''),
    (4, 'Seed default provider record', [
        "INSERT INTO providers (name, display_name, is_active, priority) VALUES ('herosms', 'HeroSMS', 1, 1) ON CONFLICT (name) DO NOTHING",
    ], ''),
    (5, 'Seed catalog services', [
        "INSERT INTO catalog_services (service_code, service_name, category, is_active, display_order) VALUES ('telegram', 'Telegram', 'messaging', 1, 1) ON CONFLICT (service_code) DO NOTHING",
        "INSERT INTO catalog_services (service_code, service_name, category, is_active, display_order) VALUES ('whatsapp', 'WhatsApp', 'messaging', 1, 2) ON CONFLICT (service_code) DO NOTHING",
        "INSERT INTO catalog_services (service_code, service_name, category, is_active, display_order) VALUES ('instagram', 'Instagram', 'social', 1, 3) ON CONFLICT (service_code) DO NOTHING",
        "INSERT INTO catalog_services (service_code, service_name, category, is_active, display_order) VALUES ('google', 'Google', 'other', 1, 4) ON CONFLICT (service_code) DO NOTHING",
    ], ''),
    (6, 'Seed catalog countries', [
        "INSERT INTO catalog_countries (country_code, country_name, is_active, display_order) VALUES ('cyprus', 'Cyprus', 1, 1) ON CONFLICT (country_code) DO NOTHING",
        "INSERT INTO catalog_countries (country_code, country_name, is_active, display_order) VALUES ('poland', 'Poland', 1, 2) ON CONFLICT (country_code) DO NOTHING",
        "INSERT INTO catalog_countries (country_code, country_name, is_active, display_order) VALUES ('philippines', 'Philippines', 1, 3) ON CONFLICT (country_code) DO NOTHING",
        "INSERT INTO catalog_countries (country_code, country_name, is_active, display_order) VALUES ('netherlands', 'Netherlands', 1, 4) ON CONFLICT (country_code) DO NOTHING",
        "INSERT INTO catalog_countries (country_code, country_name, is_active, display_order) VALUES ('estonia', 'Estonia', 1, 5) ON CONFLICT (country_code) DO NOTHING",
        "INSERT INTO catalog_countries (country_code, country_name, is_active, display_order) VALUES ('vietnam', 'Vietnam', 1, 6) ON CONFLICT (country_code) DO NOTHING",
        "INSERT INTO catalog_countries (country_code, country_name, is_active, display_order) VALUES ('georgia', 'Georgia', 1, 7) ON CONFLICT (country_code) DO NOTHING",
        "INSERT INTO catalog_countries (country_code, country_name, is_active, display_order) VALUES ('cameroon', 'Cameroon', 1, 8) ON CONFLICT (country_code) DO NOTHING",
        "INSERT INTO catalog_countries (country_code, country_name, is_active, display_order) VALUES ('laos', 'Laos', 1, 9) ON CONFLICT (country_code) DO NOTHING",
        "INSERT INTO catalog_countries (country_code, country_name, is_active, display_order) VALUES ('benin', 'Benin', 1, 10) ON CONFLICT (country_code) DO NOTHING",
        "INSERT INTO catalog_countries (country_code, country_name, is_active, display_order) VALUES ('canada', 'Canada', 1, 11) ON CONFLICT (country_code) DO NOTHING",
        "INSERT INTO catalog_countries (country_code, country_name, is_active, display_order) VALUES ('indonesia', 'Indonesia', 1, 12) ON CONFLICT (country_code) DO NOTHING",
        "INSERT INTO catalog_countries (country_code, country_name, is_active, display_order) VALUES ('ethiopia', 'Ethiopia', 1, 13) ON CONFLICT (country_code) DO NOTHING",
        "INSERT INTO catalog_countries (country_code, country_name, is_active, display_order) VALUES ('russia', 'Russia', 1, 14) ON CONFLICT (country_code) DO NOTHING",
        "INSERT INTO catalog_countries (country_code, country_name, is_active, display_order) VALUES ('paraguay', 'Paraguay', 1, 15) ON CONFLICT (country_code) DO NOTHING",
        "INSERT INTO catalog_countries (country_code, country_name, is_active, display_order) VALUES ('maldives', 'Maldives', 1, 16) ON CONFLICT (country_code) DO NOTHING",
        "INSERT INTO catalog_countries (country_code, country_name, is_active, display_order) VALUES ('suriname', 'Suriname', 1, 17) ON CONFLICT (country_code) DO NOTHING",
        "INSERT INTO catalog_countries (country_code, country_name, is_active, display_order) VALUES ('slovenia', 'Slovenia', 1, 18) ON CONFLICT (country_code) DO NOTHING",
        "INSERT INTO catalog_countries (country_code, country_name, is_active, display_order) VALUES ('cambodia', 'Cambodia', 1, 19) ON CONFLICT (country_code) DO NOTHING",
        "INSERT INTO catalog_countries (country_code, country_name, is_active, display_order) VALUES ('dominican_republic', 'Dominican Republic', 1, 20) ON CONFLICT (country_code) DO NOTHING",
    ], ''),
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
                except Exception:
                    pass
                return False

        logger.info(f"Migration complete. Version {self.get_current_version()}")
        return True
