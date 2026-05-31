"""
db/repositories/order_repository.py — Order Repository (PostgreSQL)
"""

import logging

from db.context import db_context
from db.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class OrderRepository(BaseRepository):
    db_name = 'default'

    def find_by_id(self, order_id: int):
        return self._fetchone(
            'SELECT id, user_id, activation_id, service, country, operator, phone, price, status, created_at FROM orders WHERE id = %s',
            (order_id,))

    def find_by_activation_id(self, activation_id: int):
        return self._fetchone(
            'SELECT id, user_id, activation_id, service, country, operator, phone, price, status, created_at FROM orders WHERE activation_id = %s',
            (activation_id,))

    def find_by_user(self, user_id: int, limit: int = 50):
        return self._execute_read(
            'SELECT id, activation_id, service, country, operator, phone, price, status, created_at FROM orders WHERE user_id = %s ORDER BY created_at DESC LIMIT %s',
            (user_id, limit))

    def get_activation_codes(self, order_id: int):
        return self._execute_read(
            'SELECT code, created_at FROM activation_codes WHERE order_id = %s ORDER BY created_at DESC',
            (order_id,))

    def create(self, order_data: dict) -> int | None:
        try:
            with db_context(self.db_name, transactional=True) as db:
                db.execute(
                    'INSERT INTO orders (user_id, activation_id, service, country, operator, phone, price, status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
                    (order_data['user_id'], order_data['activation_id'], order_data['service'],
                     order_data['country'], order_data['operator'], order_data['phone'],
                     order_data['price'], order_data['status']))
                row = db.fetchone('SELECT lastval()')
                return row[0] if row else 0
        except Exception as e:
            logger.error(f"Error creating order: {e}")
            return None

    def update_status(self, order_id: int, status: str) -> bool:
        try:
            with db_context(self.db_name, transactional=True) as db:
                db.execute('UPDATE orders SET status = %s WHERE id = %s', (status, order_id))
            return True
        except Exception:
            return False

    def cancel_by_activation_id(self, activation_id: int) -> bool:
        try:
            with db_context(self.db_name, transactional=True) as db:
                row = db.fetchone('SELECT id, status FROM orders WHERE activation_id = %s', (activation_id,))
                if row is None or row[1].upper() == 'CANCELED':
                    return False
                db.execute("UPDATE orders SET status = 'CANCELED' WHERE activation_id = %s", (activation_id,))
                return True
        except Exception:
            return False

    def save_activation_code(self, order_id: int, code: str) -> bool:
        try:
            with db_context(self.db_name, transactional=True) as db:
                db.execute('INSERT INTO activation_codes (order_id, code) VALUES (%s, %s)', (order_id, code))
            return True
        except Exception:
            return False

    def sum_revenue(self, days: int = 0) -> int:
        if days == 0:
            row = self._fetchone("SELECT COALESCE(SUM(price), 0) FROM orders WHERE created_at::date = CURRENT_DATE")
        else:
            row = self._fetchone(f"SELECT COALESCE(SUM(price), 0) FROM orders WHERE created_at::date >= CURRENT_DATE - INTERVAL '{days} days'")
        return row[0] if row else 0
