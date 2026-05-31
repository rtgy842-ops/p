"""
services/provider_registry.py — Multi-Provider Plugin Registry
─────────────────────────────────────────────────
Centralized registry for all SMS/number providers.
Each provider is a self-contained plugin implementing BaseSMSProvider.
The registry manages provider lifecycle, health, and configuration.

Architecture:
    ProviderRegistry (singleton)
    ├── providers: dict[str, BaseSMSProvider]  (name → instance)
    ├── health_status: dict[str, dict]
    └── active_providers → filtered list
"""

import logging
import time

from db.context import db_context
from services.sms_service import BaseSMSProvider

logger = logging.getLogger(__name__)


class ProviderInfo:
    """Metadata about a registered provider."""
    __slots__ = ('name', 'display_name', 'is_active', 'priority',
                 'last_sync_at', 'health_status', 'country_count',
                 'service_count', 'error_count')

    def __init__(self, name: str, display_name: str, is_active: bool = True,
                 priority: int = 0):
        self.name = name
        self.display_name = display_name
        self.is_active = is_active
        self.priority = priority
        self.last_sync_at: float | None = None
        self.health_status: str = 'unknown'
        self.country_count: int = 0
        self.service_count: int = 0
        self.error_count: int = 0


class ProviderRegistry:
    """
    Singleton registry for all SMS providers.
    Manages registration, activation, health, and provides
    the active provider list to the Smart Routing Engine.
    """

    _instance: 'ProviderRegistry | None' = None

    def __init__(self):
        self._providers: dict[str, BaseSMSProvider] = {}
        self._info: dict[str, ProviderInfo] = {}
        self._last_sync_all: float = 0.0

    @classmethod
    def get_instance(cls) -> 'ProviderRegistry':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Registration ─────────────────────────────────────────

    def register(self, provider: BaseSMSProvider, display_name: str = '',
                 priority: int = 0, is_active: bool = True) -> None:
        """Register a provider plugin."""
        name = provider.provider_name
        self._providers[name] = provider
        self._info[name] = ProviderInfo(
            name=name,
            display_name=display_name or name,
            is_active=is_active,
            priority=priority,
        )
        # Persist to DB
        try:
            with db_context('default', transactional=True) as db:
                db.execute(
                    """INSERT INTO providers (name, display_name, is_active, priority)
                       VALUES (%s, %s, %s, %s)
                       ON CONFLICT (name) DO UPDATE SET
                       display_name = %s, priority = %s, updated_at = CURRENT_TIMESTAMP""",
                    (name, display_name or name, 1 if is_active else 0, priority,
                     display_name or name, priority)
                )
        except Exception as e:
            logger.warning(f"Failed to persist provider {name}: {e}")

        logger.info(f"Provider registered: {name} (active={is_active}, priority={priority})")

    def unregister(self, name: str) -> bool:
        """Remove a provider from the registry."""
        if name in self._providers:
            del self._providers[name]
            self._info.pop(name, None)
            return True
        return False

    def get(self, name: str) -> BaseSMSProvider | None:
        """Get a provider instance by name."""
        return self._providers.get(name)

    def get_info(self, name: str) -> ProviderInfo | None:
        """Get provider metadata."""
        return self._info.get(name)

    # ── Active Provider Access ───────────────────────────────

    @property
    def active_providers(self) -> list[BaseSMSProvider]:
        """Return all ACTIVE providers sorted by priority (highest first)."""
        active = [
            (self._providers[name], self._info[name])
            for name in self._providers
            if self._info.get(name) and self._info[name].is_active
        ]
        active.sort(key=lambda x: x[1].priority, reverse=True)
        return [p for p, _ in active]

    @property
    def all_providers(self) -> list[BaseSMSProvider]:
        """Return ALL registered providers."""
        return list(self._providers.values())

    @property
    def active_count(self) -> int:
        return len(self.active_providers)

    def get_active_names(self) -> list[str]:
        return [p.provider_name for p in self.active_providers]

    # ── Health ───────────────────────────────────────────────

    def update_health(self, name: str, status: str, error: str | None = None) -> None:
        """Update a provider's health status."""
        info = self._info.get(name)
        if info:
            info.health_status = status
            if error:
                info.error_count += 1
            else:
                info.error_count = 0
            info.last_sync_at = time.time()

    def get_health(self, name: str) -> dict:
        """Get health status for a provider."""
        info = self._info.get(name)
        if not info:
            return {'name': name, 'status': 'not_registered'}
        return {
            'name': name,
            'display_name': info.display_name,
            'status': info.health_status,
            'is_active': info.is_active,
            'priority': info.priority,
            'errors': info.error_count,
            'last_sync': info.last_sync_at,
            'countries': info.country_count,
            'services': info.service_count,
        }

    def get_all_health(self) -> list[dict]:
        """Get health status for all providers."""
        return [self.get_health(name) for name in self._providers]

    def health_check_all(self) -> dict[str, bool]:
        """Run health check (getBalance) on all active providers."""
        results = {}
        for provider in self.active_providers:
            name = provider.provider_name
            try:
                resp = provider.get_balance()
                healthy = resp.success and 'ACCESS_BALANCE' in (resp.raw_response or '')
                self.update_health(name, 'healthy' if healthy else 'unhealthy',
                                   None if healthy else 'Balance check failed')
                results[name] = healthy
            except Exception as e:
                self.update_health(name, 'error', str(e))
                results[name] = False
        return results

    # ── Activation ───────────────────────────────────────────

    def set_active(self, name: str, active: bool) -> bool:
        """Enable or disable a provider."""
        info = self._info.get(name)
        if not info:
            return False
        info.is_active = active
        try:
            with db_context('default', transactional=True) as db:
                db.execute(
                    "UPDATE providers SET is_active = %s, updated_at = CURRENT_TIMESTAMP WHERE name = %s",
                    (1 if active else 0, name)
                )
        except Exception:
            pass
        return True

    def set_priority(self, name: str, priority: int) -> bool:
        """Change provider priority."""
        info = self._info.get(name)
        if not info:
            return False
        info.priority = priority
        try:
            with db_context('default', transactional=True) as db:
                db.execute(
                    "UPDATE providers SET priority = %s WHERE name = %s",
                    (priority, name)
                )
        except Exception:
            pass
        return True

    # ── Load from DB ─────────────────────────────────────────

    def load_from_db(self) -> int:
        """Load provider configuration from database. Returns count loaded."""
        try:
            with db_context('default', transactional=False) as db:
                rows = db.fetchall(
                    "SELECT name, display_name, is_active, priority FROM providers"
                )
                count = 0
                for row in rows:
                    name = row[0] if not isinstance(row, dict) else row.get('name')
                    display = row[1] if not isinstance(row, dict) else row.get('display_name', '')
                    active = row[2] if not isinstance(row, dict) else row.get('is_active', 1)
                    prio = row[3] if not isinstance(row, dict) else row.get('priority', 0)

                    if name not in self._info:
                        self._info[name] = ProviderInfo(
                            name=name, display_name=display or name,
                            is_active=bool(active), priority=prio or 0
                        )
                    else:
                        info = self._info[name]
                        info.is_active = bool(active)
                        info.priority = prio or 0
                    count += 1
                return count
        except Exception as e:
            logger.warning(f"Failed to load providers from DB: {e}")
            return 0

    # ── Stats ────────────────────────────────────────────────

    def get_stats(self) -> dict:
        return {
            'total_providers': len(self._providers),
            'active_providers': self.active_count,
            'active_names': self.get_active_names(),
            'health': self.get_all_health(),
        }


# ── Global instance ────────────────────────────────────────────
provider_registry = ProviderRegistry()
