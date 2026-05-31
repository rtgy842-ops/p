"""
db/repositories/card_payment_repository.py — Card Payment Repository (PostgreSQL)
"""

import logging
import time

from db.context import db_context
from db.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class CardPaymentRepository(BaseRepository):
    db_name = 'default'

    def create(self, user_id: int, amount: int) -> str | None:
        payment_id = f"CP{int(time.time())}{user_id}"
        try:
            with db_context(self.db_name, transactional=True) as db:
                db.execute('INSERT INTO card_payments (payment_id, user_id, amount) VALUES (%s, %s, %s)',
                           (payment_id, user_id, amount))
                return payment_id
        except Exception as e:
            logger.error(f"Error creating card payment: {e}")
            return None

    def find_by_id(self, payment_id: str):
        return self._fetchone(
            'SELECT payment_id, user_id, amount, status, receipt, admin_response, created_at FROM card_payments WHERE payment_id = %s',
            (payment_id,))

    def update_receipt(self, payment_id: str, receipt_file_id: str) -> bool:
        try:
            with db_context(self.db_name, transactional=True) as db:
                db.execute('UPDATE card_payments SET receipt = %s WHERE payment_id = %s', (receipt_file_id, payment_id))
            return True
        except Exception:
            return False

    def approve(self, payment_id: str, admin_id: int) -> bool:
        try:
            with db_context(self.db_name, transactional=True) as db:
                row = db.fetchone('SELECT status FROM card_payments WHERE payment_id = %s', (payment_id,))
                if row is None or row[0] != 'pending':
                    return False
                db.execute("UPDATE card_payments SET status = 'approved', admin_response = %s WHERE payment_id = %s",
                           (f"Approved by {admin_id}", payment_id))
                return True
        except Exception:
            return False

    def reject(self, payment_id: str, reason: str) -> bool:
        try:
            with db_context(self.db_name, transactional=True) as db:
                row = db.fetchone('SELECT status FROM card_payments WHERE payment_id = %s', (payment_id,))
                if row is None or row[0] != 'pending':
                    return False
                db.execute("UPDATE card_payments SET status = 'rejected', admin_response = %s WHERE payment_id = %s",
                           (reason, payment_id))
                return True
        except Exception:
            return False

    def list_recent(self, limit: int = 5):
        return self._execute_read(
            'SELECT payment_id, user_id, amount, status, created_at FROM card_payments ORDER BY created_at DESC LIMIT %s',
            (limit,))

    def list_paginated(self, offset: int, limit: int = 5):
        return self._execute_read(
            'SELECT payment_id, user_id, amount, status, created_at FROM card_payments ORDER BY created_at DESC LIMIT %s OFFSET %s',
            (limit, offset))
