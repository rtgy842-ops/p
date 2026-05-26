"""
db/repositories/user_repository.py — User Repository
─────────────────────────────────────────────────
Handles ALL user-related database operations.
Financial operations (balance changes) are ALWAYS transactional.

Prevents: race conditions, partial writes, lost updates.
"""

import logging
import sqlite3
from db.repositories.base import BaseRepository
from db.context import db_context

logger = logging.getLogger(__name__)


class UserRepository(BaseRepository):
    """Repository for users table operations."""

    db_name = 'users_db'

    # ── Read Operations ────────────────────────────────────────

    def find_by_id(self, user_id: int):
        """Find a user by their Telegram user_id."""
        return self._fetchone(
            'SELECT user_id, username, first_name, last_name, balance, '
            'is_blocked, language, join_date FROM users WHERE user_id = ?',
            (user_id,)
        )

    def get_balance(self, user_id: int) -> int:
        """Get user balance. Returns 0 if user not found."""
        row = self._fetchone(
            'SELECT balance FROM users WHERE user_id = ?', (user_id,)
        )
        return row['balance'] if row else 0

    def get_language(self, user_id: int) -> str:
        """Get user language preference."""
        row = self._fetchone(
            'SELECT language FROM users WHERE user_id = ?', (user_id,)
        )
        return row['language'] if row else 'fa'

    def exists(self, user_id: int) -> bool:
        """Check if a user exists."""
        row = self._fetchone(
            'SELECT 1 FROM users WHERE user_id = ?', (user_id,)
        )
        return row is not None

    def count_all(self) -> int:
        """Return total number of users."""
        row = self._fetchone('SELECT COUNT(*) as cnt FROM users')
        return row['cnt'] if row else 0

    def list_recent(self, limit: int = 10):
        """List recently joined users."""
        return self._execute_read(
            'SELECT user_id, balance, join_date FROM users '
            'ORDER BY user_id DESC LIMIT ?', (limit,)
        )

    def find_by_id_like(self, search_term: str):
        """Search users by partial ID match."""
        return self._execute_read(
            'SELECT user_id, balance FROM users WHERE CAST(user_id AS TEXT) LIKE ?',
            (f'%{search_term}%',)
        )

    def get_all_ids(self):
        """Get all user IDs (for broadcast)."""
        return self._execute_read('SELECT user_id FROM users')

    # ── Write Operations (ALL TRANSACTIONAL) ──────────────────

    def create_if_not_exists(self, user_id: int, language: str = 'fa') -> bool:
        """
        Create a user if they don't exist.
        Transaction-safe — no race condition possible.
        """
        try:
            with db_context(self.db_name, transactional=True) as db:
                db.execute(
                    'INSERT OR IGNORE INTO users (user_id, balance, language) '
                    'VALUES (?, 0, ?)',
                    (user_id, language)
                )
            return True
        except sqlite3.Error as e:
            logger.error(f"Error creating user {user_id}: {e}")
            return False

    def set_language(self, user_id: int, language: str) -> bool:
        """Update user language preference. Transaction-safe."""
        try:
            with db_context(self.db_name, transactional=True) as db:
                db.execute(
                    'INSERT OR IGNORE INTO users (user_id, balance, language) '
                    'VALUES (?, 0, ?)',
                    (user_id, language)
                )
                db.execute(
                    'UPDATE users SET language = ? WHERE user_id = ?',
                    (language, user_id)
                )
            return True
        except sqlite3.Error as e:
            logger.error(f"Error setting language for {user_id}: {e}")
            return False

    # ═══════════════════════════════════════════════════════════
    # FINANCIAL OPERATIONS — CRITICAL SECTION
    # Every balance change uses BEGIN/COMMIT/ROLLBACK.
    # Locking strategy: row-level via UPDATE WHERE.
    # ═══════════════════════════════════════════════════════════

    def add_balance(self, user_id: int, amount: int) -> int | None:
        """
        Add or subtract balance. Returns new balance or None on failure.
        
        TRANSACTION-SAFE: Uses BEGIN/COMMIT/ROLLBACK.
        Prevents race conditions and lost updates.
        Negative amount = deduction.
        """
        try:
            with db_context(self.db_name, transactional=True) as db:
                # Check if user exists
                row = db.fetchone(
                    'SELECT balance FROM users WHERE user_id = ?',
                    (user_id,)
                )

                if row is None:
                    # Create new user with the amount as initial balance
                    db.execute(
                        'INSERT INTO users (user_id, balance) VALUES (?, ?)',
                        (user_id, max(amount, 0))
                    )
                    return max(amount, 0)
                else:
                    current_balance = row['balance']
                    new_balance = current_balance + amount

                    # Prevent negative balance if subtracting
                    if new_balance < 0:
                        logger.warning(
                            f"Insufficient balance for user {user_id}: "
                            f"current={current_balance}, attempted_change={amount}"
                        )
                        return None

                    db.execute(
                        'UPDATE users SET balance = ? WHERE user_id = ?',
                        (new_balance, user_id)
                    )
                    return new_balance

        except sqlite3.Error as e:
            logger.error(f"Error updating balance for user {user_id}: {e}")
            return None

    def deduct_balance(self, user_id: int, amount: int) -> int | None:
        """
        Deduct balance for a purchase. Atomic operation.
        
        Checks balance BEFORE deduction to prevent overspending.
        Returns new balance or None if insufficient funds.
        """
        if amount <= 0:
            logger.warning(f"Invalid deduction amount: {amount}")
            return None

        try:
            with db_context(self.db_name, transactional=True) as db:
                row = db.fetchone(
                    'SELECT balance FROM users WHERE user_id = ?',
                    (user_id,)
                )

                if row is None or row['balance'] < amount:
                    logger.warning(
                        f"Deduction failed: user={user_id}, "
                        f"balance={row['balance'] if row else 0}, needed={amount}"
                    )
                    return None

                new_balance = row['balance'] - amount
                db.execute(
                    'UPDATE users SET balance = ? WHERE user_id = ?',
                    (new_balance, user_id)
                )
                return new_balance

        except sqlite3.Error as e:
            logger.error(f"Error deducting balance for user {user_id}: {e}")
            return None

    def refund_balance(self, user_id: int, amount: int) -> int | None:
        """
        Refund money to user (e.g., order cancellation).
        Transaction-safe credit operation.
        """
        if amount <= 0:
            return None

        try:
            with db_context(self.db_name, transactional=True) as db:
                row = db.fetchone(
                    'SELECT balance FROM users WHERE user_id = ?',
                    (user_id,)
                )

                if row is None:
                    # User doesn't exist — create with refund amount
                    db.execute(
                        'INSERT INTO users (user_id, balance) VALUES (?, ?)',
                        (user_id, amount)
                    )
                    return amount

                new_balance = row['balance'] + amount
                db.execute(
                    'UPDATE users SET balance = ? WHERE user_id = ?',
                    (new_balance, user_id)
                )
                return new_balance

        except sqlite3.Error as e:
            logger.error(f"Error refunding balance for user {user_id}: {e}")
            return None

    # ── Admin Operations ───────────────────────────────────────

    def set_blocked(self, user_id: int, blocked: bool) -> bool:
        """Block or unblock a user."""
        try:
            with db_context(self.db_name, transactional=True) as db:
                db.execute(
                    'UPDATE users SET is_blocked = ? WHERE user_id = ?',
                    (1 if blocked else 0, user_id)
                )
            return True
        except sqlite3.Error as e:
            logger.error(f"Error blocking user {user_id}: {e}")
            return False

    def save_phone(self, user_id: int, phone: str) -> bool:
        """Save user's phone number."""
        try:
            with db_context(self.db_name, transactional=True) as db:
                db.execute(
                    'UPDATE users SET phone = ? WHERE user_id = ?',
                    (phone, user_id)
                )
            return True
        except sqlite3.Error as e:
            logger.error(f"Error saving phone for {user_id}: {e}")
            return False