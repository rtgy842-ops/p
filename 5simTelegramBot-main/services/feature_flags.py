"""
services/feature_flags.py — Feature Flag System
─────────────────────────────────────────────────
Toggle features on/off without redeploying.
Supports gradual rollouts and A/B testing.

Usage:
    from services.feature_flags import flags
    
    if flags.is_enabled('new_payment_flow'):
        # use new flow
    else:
        # use old flow

Flags can be:
- Global (on/off for everyone)
- Percentage-based (e.g., 10% of users)
- User-specific (for testing)
"""

import hashlib
import logging

from db.repositories.settings_repository import SettingsRepository
from services.cache_service import CacheKeys, CacheService

logger = logging.getLogger(__name__)


class FeatureFlags:
    """
    Feature flag management with caching.
    Default all flags are OFF until explicitly enabled.
    """

    _FLAG_PREFIX = 'feature:'

    def __init__(self):
        self._settings = SettingsRepository()
        self._cache = CacheService.get_instance()

    def is_enabled(self, flag: str, user_id: int | None = None) -> bool:
        """
        Check if a feature flag is enabled.
        
        For percentage-based flags, uses user_id hash for consistent assignment.
        """
        cache_key = f'{self._FLAG_PREFIX}{flag}'

        def _fetch():
            value = self._settings.get(cache_key)
            return value

        value = self._cache.get_or_set(cache_key, _fetch, CacheKeys.TTL_SETTINGS)

        if value is None:
            return False

        # Simple boolean flag
        if value.lower() in ('true', '1', 'on'):
            return True

        if value.lower() in ('false', '0', 'off'):
            return False

        # Percentage-based flag (e.g., "20" = 20% of users)
        try:
            pct = int(value)
            if user_id is not None:
                # Deterministic assignment based on user_id hash
                bucket = int(hashlib.md5(str(user_id).encode()).hexdigest(), 16) % 100
                return bucket < pct
            return pct >= 100  # Without user_id, only 100% returns True
        except ValueError:
            return False

    def enable(self, flag: str) -> bool:
        """Enable a feature flag globally."""
        return self._settings.set(f'{self._FLAG_PREFIX}{flag}', 'true')

    def disable(self, flag: str) -> bool:
        """Disable a feature flag."""
        return self._settings.set(f'{self._FLAG_PREFIX}{flag}', 'false')

    def set_percentage(self, flag: str, percentage: int) -> bool:
        """Set a percentage-based rollout (0-100)."""
        if not 0 <= percentage <= 100:
            return False
        return self._settings.set(f'{self._FLAG_PREFIX}{flag}', str(percentage))

    def list_all(self) -> dict[str, str]:
        """List all feature flags and their values."""
        all_settings = self._settings.get_all()
        return {
            k.replace(self._FLAG_PREFIX, ''): v
            for k, v in all_settings.items()
            if k.startswith(self._FLAG_PREFIX)
        }

    def clear_cache(self) -> None:
        """Clear all feature flag caches."""
        self._cache.clear(self._FLAG_PREFIX)


# ── Migration Phase Feature Flags ──────────────────────────────
# ALL FLAGS NOW TRUE — Enterprise Architecture Fully Activated
# Legacy code paths are DEAD. All operations route through new services.
MIGRATION_FLAGS = {
    'use_new_wallet_service':    True,  # WalletService for balance ops
    'use_new_sms_service':       True,  # SMSService for all API calls
    'use_new_order_service':     True,  # OrderService with state machine
    'use_new_payment_service':   True,  # PaymentService gateways
    'use_new_admin_service':     True,  # AdminService for admin ops
}

def is_migration_enabled(flag_name: str) -> bool:
    """Check if a specific migration feature flag is enabled.
    
    Falls back gracefully: if the FeatureFlags system is unavailable (e.g.,
    before DB setup), returns the hardcoded default from MIGRATION_FLAGS.
    """
    try:
        enabled = flags.is_enabled(flag_name)
        if enabled:
            return True
        # If not explicitly set in DB, fall back to hardcoded default
        return MIGRATION_FLAGS.get(flag_name, False)
    except Exception:
        # Graceful degradation — if flags system isn't ready, use hardcoded defaults
        return MIGRATION_FLAGS.get(flag_name, False)


# ── Global instance ────────────────────────────────────────────
flags = FeatureFlags()
