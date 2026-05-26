"""
db/repositories/transaction_repository.py — Transaction Repository
─────────────────────────────────────────────────
Handles ALL financial transaction records.
Every write is TRANSACTION-SAFE.

Transaction types:
- 'deposit'   — money added (payment, admin credit)
- 'purchase'  — money spent (buying a number)
- 'refund'    — money returned (order cancellation)
- 'admin_add' — admin manually added balance
- 'admin_deduct' — admin manually reduced balance
"""

import logging
import sqlite3
from db.repositories.base import BaseRepository
from db.context import db_context

logger = logging.getLogger(__name__)


class TransactionRepository(BaseRepository):
    """Repository for transactions table (users.db)."""

    db_name = 'users_db'

    def create(self, user_id: int, amount: int, type_trans: str,
               description: str = '', ref_id: str | None = None) -> int | None:
        """
        Record a new transaction. Returns transaction ID or None.
        TRANSACTION-SAFE.
        """
        try:
            with db_context(self.db_name, transactional=True) as db:
                db.execute(
                    '''INSERT INTO transactions
                       (user_id, amount, type, description, ref_id)
                       VALUES (?, ?, ?, ?, ?)''',
                    (user_id, amount, type_trans, description, ref_id)
                )
                return db.lastrowid
        except sqlite3.Error as e:
            logger.error(f"Error recording transaction: {e}")
            return None

    def find_by_user(self, user_id: int, limit: int = 20):
        """Get recent transactions for a user."""
        return self._execute_read(
            'SELECT id, amount, type, description, ref_id, timestamp '
            'FROM transactions WHERE user_id = ? '
            'ORDER BY timestamp DESC LIMIT ?',
            (user_id, limit)
        )

    def find_recent(self, limit: int = 10):
        """Get most recent transactions across all users."""
        return self._execute_read(
            'SELECT id, user_id, amount, type, description, ref_id, timestamp '
            'FROM transactions ORDER BY timestamp DESC LIMIT ?',
            (limit,)
        )

    def sum_by_type(self, user_id: int, type_trans: str) -> int:
        """Sum all transactions of a given type for a user."""
        row = self._fetchone(
            'SELECT COALESCE(SUM(amount), 0) as total FROM transactions '
            'WHERE user_id = ? AND type = ?',
            (user_id, type_trans)
        )
        return row['total'] if row else 0

    def get_last_transaction_time(self, user_id: int) -> str | None:
        """Get timestamp of user's last transaction."""
        row = self._fetchone(
            'SELECT timestamp FROM transactions WHERE user_id = ? '
            'ORDER BY timestamp DESC LIMIT 1',
            (user_id,)
        )
        return row['timestamp'] if row else None