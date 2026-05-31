"""
db/repositories/settings_repository.py — Settings Repository (PostgreSQL)
"""

import logging

from db.context import db_context
from db.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class SettingsRepository(BaseRepository):
    db_name = 'default'

    def get(self, key: str):
        row = self._fetchone('SELECT value FROM settings WHERE key = %s', (key,))
        return row[0] if row else None

    def get_all(self) -> dict:
        rows = self._execute_read('SELECT key, value FROM settings')
        return {row[0]: row[1] for row in rows}

    def set(self, key: str, value: str) -> bool:
        try:
            with db_context(self.db_name, transactional=True) as db:
                db.execute(
                    'INSERT INTO settings (key, value, updated_at) VALUES (%s, %s, CURRENT_TIMESTAMP) ON CONFLICT (key) DO UPDATE SET value = %s, updated_at = CURRENT_TIMESTAMP',
                    (key, str(value), str(value)))
            return True
        except Exception as e:
            logger.error(f"Error setting '{key}': {e}")
            return False

    def exists(self, key: str) -> bool:
        row = self._fetchone('SELECT 1 FROM settings WHERE key = %s', (key,))
        return row is not None

    def get_card_info(self):
        return self._fetchone('SELECT card_number, card_holder FROM card_info ORDER BY id DESC LIMIT 1')

    def set_card_info(self, card_number: str, card_holder: str) -> bool:
        try:
            with db_context(self.db_name, transactional=True) as db:
                db.execute('DELETE FROM card_info')
                db.execute('INSERT INTO card_info (card_number, card_holder) VALUES (%s, %s)', (card_number, card_holder))
            return True
        except Exception:
            return False

    def get_required_channels(self):
        return self._execute_read('SELECT username, display_name, invite_link FROM required_channels')

    def add_channel(self, username: str, display_name: str, invite_link: str) -> bool:
        try:
            with db_context(self.db_name, transactional=True) as db:
                db.execute(
                    'INSERT INTO required_channels (username, display_name, invite_link) VALUES (%s, %s, %s) ON CONFLICT (username) DO UPDATE SET display_name = %s, invite_link = %s',
                    (username.replace('@', ''), display_name, invite_link, display_name, invite_link))
            return True
        except Exception:
            return False

    def remove_channel(self, username: str) -> bool:
        try:
            with db_context(self.db_name, transactional=True) as db:
                db.execute('DELETE FROM required_channels WHERE username = %s', (username.replace('@', ''),))
            return True
        except Exception:
            return False

    def get_operator(self, service: str, country: str):
        return self._fetchone('SELECT operator, country_name FROM operator_settings WHERE service = %s AND country = %s', (service, country))

    def set_operator(self, service: str, country: str, operator: str, country_name: str) -> bool:
        try:
            with db_context(self.db_name, transactional=True) as db:
                db.execute(
                    'INSERT INTO operator_settings (service, country, operator, country_name) VALUES (%s, %s, %s, %s) ON CONFLICT (service, country) DO UPDATE SET operator = %s, country_name = %s',
                    (service, country, operator, country_name, operator, country_name))
            return True
        except Exception:
            return False

    def get_all_operators(self):
        return self._execute_read('SELECT service, country, operator, country_name FROM operator_settings')
