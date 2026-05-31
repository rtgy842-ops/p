"""
services/settings_service.py — Settings Service (Enterprise Refactored)
─────────────────────────────────────────────────
Centralized setting access with caching.
Uses SettingsRepository — no direct sqlite3 connections.
"""

import logging

from db.repositories.settings_repository import SettingsRepository
from services.cache_service import CacheKeys, CacheService

logger = logging.getLogger(__name__)


class SettingsService:
    """Centralized settings management with caching."""

    def __init__(self):
        self._repo = SettingsRepository()
        self._cache = CacheService.get_instance()

    def get(self, key: str, default: str | None = None) -> str | None:
        """Get a setting value with caching."""
        cache_key = f'settings:{key}'

        def _fetch():
            return self._repo.get(key)

        value = self._cache.get_or_set(cache_key, _fetch, CacheKeys.TTL_SETTINGS)
        return value if value is not None else default

    def set(self, key: str, value: str) -> bool:
        """Set a setting value and invalidate cache."""
        success = self._repo.set(key, value)
        if success:
            self._cache.delete(f'settings:{key}')
        return success

    def get_int(self, key: str, default: int = 0) -> int:
        """Get a setting as integer."""
        value = self.get(key)
        try:
            return int(value) if value else default
        except (ValueError, TypeError):
            return default

    def get_float(self, key: str, default: float = 0.0) -> float:
        """Get a setting as float."""
        value = self.get(key)
        try:
            return float(value) if value else default
        except (ValueError, TypeError):
            return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get a setting as boolean."""
        value = self.get(key)
        if value is None:
            return default
        return value.lower() in ('true', '1', 'on', 'yes')

    def get_usd_rate(self) -> float:
        """Get USD exchange rate."""
        return self.get_float('usd_rate', 0.0)

    def get_profit_percentage(self) -> float:
        """Get profit percentage."""
        return self.get_float('profit_percentage', 30.0)

    def get_all(self) -> dict[str, str]:
        """Get all settings."""
        return self._repo.get_all()
