"""
admin_config.py — Admin Configuration (Enterprise Refactored)
─────────────────────────────────────────────────
Now delegates all DB operations to the SettingsRepository.
No direct sqlite3 connections. All operations are transaction-safe.
Backward-compatible API for bot.py callers.
"""

import logging
from db.repositories.settings_repository import SettingsRepository

logger = logging.getLogger(__name__)


class AdminConfig:
    """Admin configuration manager using enterprise repository layer."""

    def __init__(self):
        self._repo = SettingsRepository()
        # Ensure defaults exist (via setup_databases or migration)
        self._ensure_defaults()

    def _ensure_defaults(self):
        """Ensure default settings exist."""
        defaults = {
            'profit_percentage': '30',
            'usd_rate': '0',
            'channel_lock': 'false',
        }
        for key, value in defaults.items():
            if not self._repo.exists(key):
                self._repo.set(key, value)
                logger.info(f"Default setting inserted: {key}={value}")

    def get_profit_percentage(self):
        val = self._repo.get('profit_percentage')
        return float(val) if val else 30.0

    def set_profit_percentage(self, percentage):
        self._repo.set('profit_percentage', str(percentage))

    def get_usd_rate(self):
        val = self._repo.get('usd_rate')
        return float(val) if val else 0.0

    def set_usd_rate(self, rate):
        self._repo.set('usd_rate', str(rate))

    def get_transactions(self, limit=10):
        """Get recent transactions via repository."""
        from db.repositories.transaction_repository import TransactionRepository
        repo = TransactionRepository()
        return repo.find_recent(limit)

    def get_required_channels(self):
        """Get all required channels from admin.db."""
        try:
            channels = self._repo.get_required_channels()
            channels_list = []
            for row in channels:
                channels_list.append((
                    row['username'],
                    row['display_name'],
                    row['invite_link'],
                ))
            logger.info(f"Returning {len(channels_list)} channels")
            return channels_list
        except Exception as e:
            logger.error(f"Error in get_required_channels: {e}")
            return []

    def add_required_channel(self, username, display_name, invite_link):
        """Add a required channel via repository."""
        try:
            return self._repo.add_channel(username, display_name, invite_link)
        except Exception as e:
            logger.error(f"Error in add_required_channel: {e}")
            return False

    def remove_required_channel(self, username):
        """Remove a required channel via repository."""
        try:
            return self._repo.remove_channel(username)
        except Exception as e:
            logger.error(f"Error in remove_required_channel: {e}")
            return False

    def get_lock_status(self):
        """Check if channel lock is enabled."""
        try:
            val = self._repo.get('channel_lock')
            return val == 'true' if val else False
        except Exception as e:
            logger.error(f"Error in get_lock_status: {e}")
            return False

    def set_lock_status(self, status):
        """Enable/disable channel lock."""
        try:
            return self._repo.set('channel_lock', str(status).lower())
        except Exception as e:
            logger.error(f"Error in set_lock_status: {e}")
            return False

    # ── Legacy backward-compat (deprecated, kept for bot.py migration) ──
    def setup_database(self):
        """No-op: database setup is handled by migrations now."""
        pass

    def add_transaction(self, user_id, amount, type_trans, description):
        """Add transaction via repository."""
        from db.repositories.transaction_repository import TransactionRepository
        repo = TransactionRepository()
        repo.create(user_id, amount, type_trans, description)
