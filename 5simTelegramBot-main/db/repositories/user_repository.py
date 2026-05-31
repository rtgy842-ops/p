"""
db/repositories/user_repository.py — User Repository (PostgreSQL)
─────────────────────────────────────────────────
"""

import logging
from db.repositories.base import BaseRepository
from db.context import db_context

logger = logging.getLogger(__name__)


class UserRepository(BaseRepository):
    db_name = 'default'

    def find_by_id(self, user_id: int):
        return self._fetchone(
            'SELECT user_id, username, first_name, last_name, balance, is_blocked, language, join_date FROM users WHERE user_id = %s',
            (user_id,))

    def get_balance(self, user_id: int) -> int:
        row = self._fetchone('SELECT balance FROM users WHERE user_id = %s', (user_id,))
        return row[0] if row else 0

    def get_language(self, user_id: int) -> str:
        row = self._fetchone('SELECT language FROM users WHERE user_id = %s', (user_id,))
        return row[0] if row else 'fa'

    def exists(self, user_id: int) -> bool:
        row = self._fetchone('SELECT 1 FROM users WHERE user_id = %s', (user_id,))
        return row is not None

    def count_all(self) -> int:
        row = self._fetchone('SELECT COUNT(*) FROM users')
        return row[0] if row else 0

    def list_recent(self, limit: int = 10):
        return self._execute_read('SELECT user_id, balance, join_date FROM users ORDER BY user_id DESC LIMIT %s', (limit,))

    def get_all_ids(self):
        return self._execute_read('SELECT user_id FROM users')

    def create_if_not_exists(self, user_id: int, language: str = 'fa') -> bool:
        try:
            with db_context(self.db_name, transactional=True) as db:
                db.execute('INSERT INTO users (user_id, balance, language) VALUES (%s, 0, %s) ON CONFLICT (user_id) DO NOTHING', (user_id, language))
            return True
        except Exception as e:
            logger.error(f"Error creating user {user_id}: {e}")
            return False

    def set_language(self, user_id: int, language: str) -> bool:
        try:
            with db_context(self.db_name, transactional=True) as db:
                db.execute(
                    'INSERT INTO users (user_id, balance, language) VALUES (%s, 0, %s) ON CONFLICT (user_id) DO NOTHING', (user_id, language))
                db.execute('UPDATE users SET language = %s WHERE user_id = %s', (language, user_id))
            return True
        except Exception as e:
            logger.error(f"Error setting language: {e}")
            return False

    def add_balance(self, user_id: int, amount: int) -> int | None:
        try:
            with db_context(self.db_name, transactional=True) as db:
                # SELECT ... FOR UPDATE to prevent race conditions
                row = db.fetchone('SELECT balance FROM users WHERE user_id = %s FOR UPDATE', (user_id,))
                if row is None:
                    db.execute('INSERT INTO users (user_id, balance) VALUES (%s, %s) ON CONFLICT DO NOTHING', (user_id, max(amount, 0)))
                    return max(amount, 0)
                new_balance = row[0] + amount
                if new_balance < 0:
                    return None
                db.execute('UPDATE users SET balance = %s WHERE user_id = %s', (new_balance, user_id))
                return new_balance
        except Exception as e:
            logger.error(f"Error add_balance: {e}")
            return None

    def deduct_balance(self, user_id: int, amount: int) -> int | None:
        if amount <= 0:
            return None
        try:
            with db_context(self.db_name, transactional=True) as db:
                # SELECT ... FOR UPDATE to prevent race conditions
                row = db.fetchone('SELECT balance FROM users WHERE user_id = %s FOR UPDATE', (user_id,))
                if row is None or row[0] < amount:
                    return None
                new_balance = row[0] - amount
                db.execute('UPDATE users SET balance = %s WHERE user_id = %s', (new_balance, user_id))
                return new_balance
        except Exception as e:
            logger.error(f"Error deduct_balance: {e}")
            return None

    def refund_balance(self, user_id: int, amount: int) -> int | None:
        if amount <= 0:
            return None
        try:
            with db_context(self.db_name, transactional=True) as db:
                # SELECT ... FOR UPDATE to prevent race conditions
                row = db.fetchone('SELECT balance FROM users WHERE user_id = %s FOR UPDATE', (user_id,))
                if row is None:
                    db.execute('INSERT INTO users (user_id, balance) VALUES (%s, %s) ON CONFLICT DO NOTHING', (user_id, amount))
                    return amount
                new_balance = row[0] + amount
                db.execute('UPDATE users SET balance = %s WHERE user_id = %s', (new_balance, user_id))
                return new_balance
        except Exception as e:
            logger.error(f"Error refund_balance: {e}")
            return None

    def set_blocked(self, user_id: int, blocked: bool) -> bool:
        try:
            with db_context(self.db_name, transactional=True) as db:
                db.execute('UPDATE users SET is_blocked = %s WHERE user_id = %s', (1 if blocked else 0, user_id))
            return True
        except Exception as e:
            return False

    def save_phone(self, user_id: int, phone: str) -> bool:
        try:
            with db_context(self.db_name, transactional=True) as db:
                db.execute('UPDATE users SET phone = %s WHERE user_id = %s', (phone, user_id))
            return True
        except Exception as e:
            return False