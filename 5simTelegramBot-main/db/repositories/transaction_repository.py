"""
db/repositories/transaction_repository.py — Transaction Repository (PostgreSQL)
"""

import logging

from db.context import db_context
from db.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class TransactionRepository(BaseRepository):
    db_name = 'default'

    def create(self, user_id: int, amount: int, type_trans: str,
               description: str = '', ref_id: str | None = None) -> int | None:
        try:
            with db_context(self.db_name, transactional=True) as db:
                db.execute(
                    'INSERT INTO transactions (user_id, amount, type, description, ref_id) VALUES (%s, %s, %s, %s, %s)',
                    (user_id, amount, type_trans, description, ref_id))
            return 1
        except Exception as e:
            logger.error(f"Error recording transaction: {e}")
            return None

    def find_by_user(self, user_id: int, limit: int = 20):
        return self._execute_read(
            'SELECT id, amount, type, description, ref_id, timestamp FROM transactions WHERE user_id = %s ORDER BY timestamp DESC LIMIT %s',
            (user_id, limit))

    def find_recent(self, limit: int = 10):
        return self._execute_read(
            'SELECT id, user_id, amount, type, description, ref_id, timestamp FROM transactions ORDER BY timestamp DESC LIMIT %s',
            (limit,))

    def sum_by_type(self, user_id: int, type_trans: str) -> int:
        row = self._fetchone(
            'SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE user_id = %s AND type = %s',
            (user_id, type_trans))
        return row[0] if row else 0

    def get_last_transaction_time(self, user_id: int) -> str | None:
        row = self._fetchone(
            'SELECT timestamp FROM transactions WHERE user_id = %s ORDER BY timestamp DESC LIMIT 1',
            (user_id,))
        return str(row[0]) if row else None
