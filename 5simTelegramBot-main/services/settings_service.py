"""
services/settings_service.py — Unified Settings Access Layer
─────────────────────────────────────────────────
Single entry point for ALL application settings.
Reads from admin.db with in-memory caching.
Replaces scattered sqlite3.connect('admin.db') calls across the codebase.

Usage:
    from services.settings_service import SettingsService
    settings = SettingsService()
    usd_rate = settings.get('usd_rate')
    profit = settings.get('profit_percentage')
"""

import sqlite3
import logging
from config import DB_CONFIG

logger = logging.getLogger(__name__)

# ── Default values ─────────────────────────────────────────────
DEFAULT_SETTINGS: dict[str, str] = {
    'usd_rate': '0',
    'profit_percentage': '30',
    'channel_lock': 'false',
}


class SettingsService:
    """Thread-safe settings access with in-memory caching."""

    def __init__(self):
        self._cache: dict[str, str] = {}
        self._ensure_table()

    def _ensure_table(self) -> None:
        """Create the settings table if it doesn't exist."""
        try:
            conn = sqlite3.connect(DB_CONFIG['admin_db'])
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            ''')
            # Ensure default keys exist
            for key, default_value in DEFAULT_SETTINGS.items():
                cursor.execute(
                    'INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)',
                    (key, default_value)
                )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error ensuring settings table: {e}")

    def get(self, key: str, default: str | None = None) -> str | None:
        """
        Get a setting value. Checks cache first, then database.
        Falls back to DEFAULT_SETTINGS, then the provided default.
        """
        # Check cache
        if key in self._cache:
            return self._cache[key]

        try:
            conn = sqlite3.connect(DB_CONFIG['admin_db'])
            cursor = conn.cursor()
            cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
            result = cursor.fetchone()
            conn.close()

            if result:
                self._cache[key] = result[0]
                return result[0]
        except Exception as e:
            logger.error(f"Error reading setting '{key}': {e}")

        # Fall back to DEFAULT_SETTINGS, then caller's default
        fallback = DEFAULT_SETTINGS.get(key, default)
        if fallback is not None:
            self._cache[key] = fallback
        return fallback

    def get_float(self, key: str, default: float = 0.0) -> float:
        """Get a setting as float."""
        value = self.get(key)
        try:
            return float(value) if value is not None else default
        except (ValueError, TypeError):
            return default

    def get_int(self, key: str, default: int = 0) -> int:
        """Get a setting as int."""
        value = self.get(key)
        try:
            return int(value) if value is not None else default
        except (ValueError, TypeError):
            return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get a setting as bool."""
        value = self.get(key)
        if value is None:
            return default
        return value.lower() in ('true', '1', 'yes', 'on')

    def set(self, key: str, value: str) -> bool:
        """Set a setting value. Updates cache and database."""
        try:
            conn = sqlite3.connect(DB_CONFIG['admin_db'])
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)
            ''', (key, str(value)))
            conn.commit()
            conn.close()
            self._cache[key] = str(value)
            return True
        except Exception as e:
            logger.error(f"Error setting '{key}' = '{value}': {e}")
            return False

    def invalidate_cache(self, key: str | None = None) -> None:
        """Clear cached value(s). If key is None, clears all."""
        if key is None:
            self._cache.clear()
        elif key in self._cache:
            del self._cache[key]
