"""
operator_config.py — Operator Configuration (Enterprise Refactored)
─────────────────────────────────────────────────
Now delegates ALL operations to SettingsRepository.
No direct sqlite3 connections.
"""

import logging

from data.service_countries import get_all_service_countries
from db.repositories.settings_repository import SettingsRepository

logger = logging.getLogger(__name__)


class OperatorConfig:
    """Operator configuration manager using enterprise repository layer."""

    def __init__(self):
        self._repo = SettingsRepository()
        self._ensure_defaults()

    def _ensure_defaults(self):
        """Seed default operator settings from the Single Source of Truth."""
        try:
            default_settings = get_all_service_countries()
            for service, country, operator, country_name in default_settings:
                if not self._repo.get_operator(service, country):
                    self._repo.set_operator(service, country, operator, country_name)
            logger.info("Operator settings seeded from SSOT")
        except Exception as e:
            logger.error(f"Error seeding operator defaults: {e}")

    def get_operator_info(self, service, country):
        """Get operator and country name for a service+country pair."""
        try:
            result = self._repo.get_operator(service, country)
            if result:
                return (result['operator'], result['country_name'])
            return (None, None)
        except Exception as e:
            logger.error(f"Error in get_operator_info: {e}")
            return (None, None)

    def set_operator(self, service, country, operator, country_name):
        """Set operator for a service+country pair."""
        try:
            return self._repo.set_operator(service, country, operator, country_name)
        except Exception as e:
            logger.error(f"Error in set_operator: {e}")
            return False

    def get_all_settings(self):
        """Get all operator settings."""
        try:
            return self._repo.get_all_operators()
        except Exception as e:
            logger.error(f"Error in get_all_settings: {e}")
            return []

    # ── Legacy backward-compat ──
    def setup_database(self):
        """No-op: handled by SettingsRepository."""
        self._ensure_defaults()
