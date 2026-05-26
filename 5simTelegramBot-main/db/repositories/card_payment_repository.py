"""
db/repositories/card_payment_repository.py — Card Payment Repository
─────────────────────────────────────────────────
Handles card-to-card payment records.
All payment state changes are TRANSACTION-SAFE.
"""

import logging
import sqlite3
import time
from db.repositories.base import BaseRepository
from db.context import db_context

logger = logging.getLogger(__name__)


class CardPaymentRepository(BaseRepository):
    """Repository for card_payments table (users.db)."""

    db_name = 'users_db'

    def create(self, user_id: int, amount: int) -> str | None:
        """Create a new card payment request. Returns payment_id."""
        payment_id = f"CP{int(time.time())}{user_id}"
        try:
            with db_context(self.db_name, transactional=True) as db:
                db.execute(
                    'INSERT INTO card_payments (payment_id, user_id, amount) '
                    'VALUES (?, ?, ?)',
                    (payment_id, user_id, amount)
                )
                return payment_id
        except sqlite3.Error as e:
            logger.error(f"Error creating card payment: {e}")
            return None

    def find_by_id(self, payment_id: str):
        """Find a card payment by ID."""
        return self._fetchone(
            'SELECT payment_id, user_id, amount, status, receipt, '
            'admin_response, created_at FROM card_payments WHERE payment_id = ?',
            (payment_id,)
        )

    def update_receipt(self, payment_id: str, receipt_file_id: str) -> bool:
        """Save receipt photo file_id. Transaction-safe."""
        try:
            with db_context(self.db_name, transactional=True) as db:
                db.execute(
                    'UPDATE card_payments SET receipt = ? WHERE payment_id = ?',
                    (receipt_file_id, payment_id)
                )
            return True
        except sqlite3.Error as e:
            logger.error(f"Error updating receipt for {payment_id}: {e}")
            return False

    def approve(self, payment_id: str, admin_id: int) -> bool:
        """
        Approve a card payment. Must be 'pending' to approve.
        TRANSACTION-SAFE — prevents double-approval.
        """
        try:
            with db_context(self.db_name, transactional=True) as db:
                row = db.fetchone(
                    'SELECT status FROM card_payments WHERE payment_id = ?',
                    (payment_id,)
                )
                if row is None or row['status'] != 'pending':
                    logger.warning(f"Cannot approve payment {payment_id}: status={row['status'] if row else 'not_found'}")
                    return False

                db.execute(
                    '''UPDATE card_payments SET status = 'approved',
                       admin_response = ? WHERE payment_id = ?''',
                    (f"تایید شده توسط {admin_id}", payment_id)
                )
                return True
        except sqlite3.Error as e:
            logger.error(f"Error approving payment {payment_id}: {e}")
            return False

    def reject(self, payment_id: str, reason: str) -> bool:
        """
        Reject a card payment. Must be 'pending' to reject.
        TRANSACTION-SAFE.
        """
        try:
            with db_context(self.db_name, transactional=True) as db:
                row = db.fetchone(
                    'SELECT status FROM card_payments WHERE payment_id = ?',
                    (payment_id,)
                )
                if row is None or row['status'] != 'pending':
                    return False

                db.execute(
                    '''UPDATE card_payments SET status = 'rejected',
                       admin_response = ? WHERE payment_id = ?''',
                    (reason, payment_id)
                )
                return True
        except sqlite3.Error as e:
            logger.error(f"Error rejecting payment {payment_id}: {e}")
            return False

    def list_recent(self, limit: int = 5):
        """Get recent card payments."""
        return self._execute_read(
            'SELECT payment_id, user_id, amount, status, created_at '
            'FROM card_payments ORDER BY created_at DESC LIMIT ?',
            (limit,)
        )

    def list_paginated(self, offset: int, limit: int = 5):
        """Get paginated card payments."""
        return self._execute_read(
            'SELECT payment_id, user_id, amount, status, created_at '
            'FROM card_payments ORDER BY created_at DESC LIMIT ? OFFSET ?',
            (limit, offset)
        )