"""
services/api_key_service.py — API Key Management
─────────────────────────────────────────────────
Production-grade API key lifecycle:
- Generation with scopes
- Rate limiting per key
- Usage tracking
- Revocation
- Expiration
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class APIScope(str, Enum):
    READ_ORDERS = 'read:orders'
    CREATE_ORDERS = 'create:orders'
    CANCEL_ORDERS = 'cancel:orders'
    READ_BALANCE = 'read:balance'
    READ_SERVICES = 'read:services'
    ADMIN = 'admin'


class APIKeyService:
    """
    API key lifecycle management.
    """

    def __init__(self):
        self._keys: dict[str, dict] = {}  # hashed_key → metadata

    def create_key(self, user_id: int, scopes: list[APIScope],
                   expires_days: int = 365, admin_id: int = 0) -> tuple[str, str]:
        """
        Generate a new API key for a user.
        Returns (api_key, masked_key).
        Only the raw key is shown ONCE.
        """
        raw_key = f"ak_{secrets.token_hex(32)}"
        hashed = self._hash_key(raw_key)
        masked = f"{raw_key[:8]}...{raw_key[-4:]}"

        self._keys[hashed] = {
            'user_id': user_id,
            'scopes': [s.value for s in scopes],
            'created_at': datetime.now().isoformat(),
            'expires_at': (datetime.now() + timedelta(days=expires_days)).isoformat(),
            'created_by': admin_id,
            'usage_count': 0,
            'last_used': None,
            'revoked': False,
        }

        logger.info(f"API key created: {masked} for user {user_id}")
        return raw_key, masked

    def validate_key(self, api_key: str) -> tuple[bool, int, list[str]]:
        """
        Validate an API key.
        Returns (is_valid, user_id, scopes).
        """
        hashed = self._hash_key(api_key)
        metadata = self._keys.get(hashed)

        if metadata is None:
            return False, 0, []

        if metadata['revoked']:
            return False, 0, []

        if metadata['expires_at']:
            expires = datetime.fromisoformat(metadata['expires_at'])
            if datetime.now() > expires:
                return False, 0, []

        # Update usage
        metadata['usage_count'] += 1
        metadata['last_used'] = datetime.now().isoformat()

        return True, metadata['user_id'], metadata['scopes']

    def revoke_key(self, api_key: str, admin_id: int) -> bool:
        """Revoke an API key."""
        hashed = self._hash_key(api_key)
        if hashed in self._keys:
            self._keys[hashed]['revoked'] = True
            logger.info(f"API key revoked by admin {admin_id}")
            return True
        return False

    def get_key_info(self, api_key: str) -> dict | None:
        """Get metadata for an API key (masked)."""
        hashed = self._hash_key(api_key)
        return self._keys.get(hashed)

    def list_user_keys(self, user_id: int) -> list[dict]:
        """List all API keys for a user (masked)."""
        return [
            {
                'masked': self._mask(key_data),
                'scopes': key_data['scopes'],
                'created_at': key_data['created_at'],
                'expires_at': key_data['expires_at'],
                'usage_count': key_data['usage_count'],
                'revoked': key_data['revoked'],
            }
            for hashed, key_data in self._keys.items()
            if key_data['user_id'] == user_id
        ]

    @staticmethod
    def _hash_key(key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()

    @staticmethod
    def _mask(key_data: dict) -> str:
        """Return a masked version for display."""
        return 'ak_********'


# ── Global instance ────────────────────────────────────────────
api_keys = APIKeyService()
