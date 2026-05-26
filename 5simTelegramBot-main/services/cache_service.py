"""
services/cache_service.py — In-Memory Caching Layer
─────────────────────────────────────────────────
Simple TTL-based cache for:
- SMS prices (short-lived, 30 seconds)
- Country/operator lists (medium, 5 minutes)
- Settings (long, 10 minutes)
- Currency rates (from CurrencyService)

Thread-safe via lock.
Prepares for Redis migration later.
"""

import logging
import threading
import time
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CacheService:
    """
    Thread-safe in-memory cache with TTL support.
    Drop-in replacement for future Redis migration.
    """

    _instance: 'CacheService | None' = None
    _lock = threading.Lock()

    def __init__(self):
        self._store: dict[str, tuple[any, float]] = {}  # key -> (value, expiry_timestamp)
        self._hits = 0
        self._misses = 0

    @classmethod
    def get_instance(cls) -> 'CacheService':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def get(self, key: str, default: any = None) -> any:
        """Get a value from cache. Returns default if expired/missing."""
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            return default

        value, expiry = entry
        if expiry > 0 and time.time() > expiry:
            del self._store[key]
            self._misses += 1
            return default

        self._hits += 1
        return value

    def set(self, key: str, value: any, ttl_seconds: int = 300) -> None:
        """Set a value with TTL in seconds. 0 = never expire."""
        expiry = time.time() + ttl_seconds if ttl_seconds > 0 else 0
        self._store[key] = (value, expiry)

    def delete(self, key: str) -> None:
        """Remove a key from cache."""
        self._store.pop(key, None)

    def clear(self, prefix: str = '') -> None:
        """Clear cache. If prefix given, only clears matching keys."""
        if not prefix:
            self._store.clear()
        else:
            keys = [k for k in self._store if k.startswith(prefix)]
            for k in keys:
                del self._store[k]

    def get_or_set(self, key: str, factory: callable, ttl_seconds: int = 300) -> any:
        """Get from cache, or compute and cache if missing."""
        value = self.get(key)
        if value is not None:
            return value
        value = factory()
        if value is not None:
            self.set(key, value, ttl_seconds)
        return value

    def get_stats(self) -> dict:
        """Return cache statistics."""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        return {
            'size': len(self._store),
            'hits': self._hits,
            'misses': self._misses,
            'hit_rate': f'{hit_rate:.1f}%',
            'keys': list(self._store.keys())[:20],
        }


# ── Cache key constants ────────────────────────────────────────
class CacheKeys:
    """Standardized cache key patterns."""
    PRICES = 'prices:{}:{}'          # prices:service:country
    COUNTRIES = 'countries:{}'       # countries:service
    SERVICES = 'services:all'
    SETTINGS = 'settings:{}'         # settings:key
    USER_LANG = 'user:{}:lang'       # user:user_id:lang
    CURRENCY_RATE = 'currency:usd_rate'

    # TTL constants
    TTL_PRICES = 30       # Prices change frequently
    TTL_COUNTRIES = 300   # Country lists rarely change
    TTL_SETTINGS = 600    # Settings change via admin
    TTL_USER = 3600       # User data
    TTL_CURRENCY = 300    # Exchange rates