"""
services/user_service.py — User Service
─────────────────────────────────────────────────
User management operations.
Zero Telegram dependencies — pure business logic.
"""

import logging

from data.dto import UserDTO
from db.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)


class UserService:
    """User management — registration, language, blocking."""

    def __init__(self):
        self._user_repo = UserRepository()

    def get_or_create(self, user_id: int, language: str = 'fa') -> UserDTO:
        """
        Get user by ID, creating if they don't exist.
        This is the primary entry point for Telegram handlers.
        """
        user = self.get_user(user_id)
        if user is None:
            self._user_repo.create_if_not_exists(user_id, language)
            user = UserDTO(user_id=user_id, language=language)
            logger.info(f"New user created: {user_id}")
        return user

    def get_user(self, user_id: int) -> UserDTO | None:
        """Get user by ID."""
        row = self._user_repo.find_by_id(user_id)
        return UserDTO.from_row(row)

    def get_language(self, user_id: int) -> str:
        """Get user's language preference."""
        return self._user_repo.get_language(user_id)

    def set_language(self, user_id: int, language: str) -> bool:
        """Set user's language preference."""
        return self._user_repo.set_language(user_id, language)

    def get_balance(self, user_id: int) -> int:
        """Get user balance."""
        return self._user_repo.get_balance(user_id)

    def is_blocked(self, user_id: int) -> bool:
        """Check if user is blocked."""
        user = self.get_user(user_id)
        return user.is_blocked if user else False

    def set_blocked(self, user_id: int, blocked: bool) -> bool:
        """Block or unblock a user."""
        return self._user_repo.set_blocked(user_id, blocked)

    def save_phone(self, user_id: int, phone: str) -> bool:
        """Save user's phone number."""
        return self._user_repo.save_phone(user_id, phone)

    def get_stats(self) -> dict:
        """Get user statistics for admin panel."""
        return {
            'total_users': self._user_repo.count_all(),
        }

    def list_recent(self, limit: int = 10) -> list[UserDTO]:
        """List recently joined users."""
        rows = self._user_repo.list_recent(limit)
        return [UserDTO.from_row(r) for r in rows]

    def search(self, term: str) -> list[UserDTO]:
        """Search users by partial ID."""
        rows = self._user_repo.find_by_id_like(term)
        return [UserDTO.from_row(r) for r in rows]

    def get_all_ids(self) -> list[int]:
        """Get all user IDs for broadcast."""
        rows = self._user_repo.get_all_ids()
        # psycopg2 returns tuples by default; handle both tuple and dict cases
        result: list[int] = []
        for r in rows:
            if isinstance(r, dict):
                result.append(r.get('user_id', 0))
            else:
                result.append(r[0])
        return result
