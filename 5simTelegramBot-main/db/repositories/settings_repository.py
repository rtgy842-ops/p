"""
db/repositories/settings_repository.py — Settings Repository
─────────────────────────────────────────────────
Handles key-value settings stored in admin.db.
Used by SettingsService for cached access.
"""

import logging
import sqlite3
from db.repositories.base import BaseRepository
from db.context import db_context

logger = logging.getLogger(__name__)


class SettingsRepository(BaseRepository):
    """Repository for settings table (admin.db)."""

    db_name = 'admin_db'

    def get(self, key: str) -> str | None:
        """Get a setting value by key."""
        row = self._fetchone(
            'SELECT value FROM settings WHERE key = ?', (key,)
        )
        return row['value'] if row else None

    def get_all(self) -> dict[str, str]:
        """Get all settings as a dictionary."""
        rows = self._execute_read('SELECT key, value FROM settings')
        return {row['key']: row['value'] for row in rows}

    def set(self, key: str, value: str) -> bool:
        """Insert or update a setting. Transaction-safe."""
        try:
            with db_context(self.db_name, transactional=True) as db:
                db.execute(
                    '''INSERT OR REPLACE INTO settings (key, value, updated_at)
                       VALUES (?, ?, CURRENT_TIMESTAMP)''',
                    (key, str(value))
                )
            return True
        except sqlite3.Error as e:
            logger.error(f"Error setting '{key}': {e}")
            return False

    def set_many(self, settings: dict[str, str]) -> bool:
        """Batch insert/update settings. Transaction-safe."""
        try:
            with db_context(self.db_name, transactional=True) as db:
                for key, value in settings.items():
                    db.execute(
                        '''INSERT OR REPLACE INTO settings (key, value, updated_at)
                           VALUES (?, ?, CURRENT_TIMESTAMP)''',
                        (key, str(value))
                    )
            return True
        except sqlite3.Error as e:
            logger.error(f"Error in batch settings update: {e}")
            return False

    def exists(self, key: str) -> bool:
        """Check if a setting key exists."""
        row = self._fetchone(
            'SELECT 1 FROM settings WHERE key = ?', (key,)
        )
        return row is not None

    # ── Card Info (stored in admin.db too) ─────────────────────

    def get_card_info(self):
        """Get current bank card information."""
        return self._fetchone(
            'SELECT card_number, card_holder FROM card_info '
            'ORDER BY id DESC LIMIT 1'
        )

    def set_card_info(self, card_number: str, card_holder: str) -> bool:
        """Set bank card information. Transaction-safe."""
        try:
            with db_context(self.db_name, transactional=True) as db:
                db.execute('DELETE FROM card_info')
                db.execute(
                    'INSERT INTO card_info (card_number, card_holder) VALUES (?, ?)',
                    (card_number, card_holder)
                )
            return True
        except sqlite3.Error as e:
            logger.error(f"Error setting card info: {e}")
            return False

    # ── Required Channels ──────────────────────────────────────

    def get_required_channels(self):
        """Get all required channels for membership check."""
        return self._execute_read(
            'SELECT username, display_name, invite_link FROM required_channels'
        )

    def add_channel(self, username: str, display_name: str, invite_link: str) -> bool:
        """Add a required channel."""
        try:
            with db_context(self.db_name, transactional=True) as db:
                db.execute(
                    '''INSERT OR REPLACE INTO required_channels
                       (username, display_name, invite_link)
                       VALUES (?, ?, ?)''',
                    (username.replace('@', ''), display_name, invite_link)
                )
            return True
        except sqlite3.Error as e:
            logger.error(f"Error adding channel @{username}: {e}")
            return False

    def remove_channel(self, username: str) -> bool:
        """Remove a required channel."""
        try:
            with db_context(self.db_name, transactional=True) as db:
                db.execute(
                    'DELETE FROM required_channels WHERE username = ?',
                    (username.replace('@', ''),)
                )
            return True
        except sqlite3.Error as e:
            logger.error(f"Error removing channel @{username}: {e}")
            return False

    # ── Operator Settings ──────────────────────────────────────

    def get_operator(self, service: str, country: str):
        """Get operator for a service+country pair."""
        return self._fetchone(
            'SELECT operator, country_name FROM operator_settings '
            'WHERE service = ? AND country = ?',
            (service, country)
        )

    def set_operator(self, service: str, country: str,
                     operator: str, country_name: str) -> bool:
        """Set operator for a service+country pair."""
        try:
            with db_context(self.db_name, transactional=True) as db:
                db.execute(
                    '''INSERT OR REPLACE INTO operator_settings
                       (service, country, operator, country_name)
                       VALUES (?, ?, ?, ?)''',
                    (service, country, operator, country_name)
                )
            return True
        except sqlite3.Error as e:
            logger.error(f"Error setting operator: {e}")
            return False

    def get_all_operators(self):
        """Get all operator settings."""
        return self._execute_read(
            'SELECT service, country, operator, country_name FROM operator_settings'
        )