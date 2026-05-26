"""
db/repositories/order_repository.py — Order Repository
─────────────────────────────────────────────────
Handles ALL order lifecycle operations:
- Create, track, update status, cancel, refund.

All write operations are TRANSACTION-SAFE.
Order creation + balance deduction = atomic.
"""

import logging
import sqlite3
from db.repositories.base import BaseRepository
from db.context import db_context

logger = logging.getLogger(__name__)


class OrderRepository(BaseRepository):
    """Repository for orders table (bot.db)."""

    db_name = 'bot_db'

    # ── Read Operations ────────────────────────────────────────

    def find_by_id(self, order_id: int):
        """Find order by local ID."""
        return self._fetchone(
            'SELECT id, user_id, activation_id, service, country, operator, '
            'phone, price, status, created_at FROM orders WHERE id = ?',
            (order_id,)
        )

    def find_by_activation_id(self, activation_id: int):
        """Find order by activation_id from 5sim."""
        return self._fetchone(
            'SELECT id, user_id, activation_id, service, country, operator, '
            'phone, price, status, created_at FROM orders WHERE activation_id = ?',
            (activation_id,)
        )

    def find_by_user(self, user_id: int, limit: int = 50):
        """Get all orders for a user."""
        return self._execute_read(
            'SELECT id, activation_id, service, country, operator, '
            'phone, price, status, created_at '
            'FROM orders WHERE user_id = ? '
            'ORDER BY created_at DESC LIMIT ?',
            (user_id, limit)
        )

    def get_activation_codes(self, order_id: int):
        """Get activation codes for an order."""
        return self._execute_read(
            'SELECT code, created_at FROM activation_codes '
            'WHERE order_id = ? ORDER BY created_at DESC',
            (order_id,)
        )

    # ── Write Operations (ALL TRANSACTIONAL) ──────────────────

    def create(self, order_data: dict) -> int | None:
        """
        Create a new order. Returns local order_id or None.
        
        TRANSACTION-SAFE: Atomic INSERT + return ID.
        """
        try:
            with db_context(self.db_name, transactional=True) as db:
                db.execute(
                    '''INSERT INTO orders
                       (user_id, activation_id, service, country,
                        operator, phone, price, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        order_data['user_id'],
                        order_data['activation_id'],
                        order_data['service'],
                        order_data['country'],
                        order_data['operator'],
                        order_data['phone'],
                        order_data['price'],
                        order_data['status'],
                    )
                )
                return db.lastrowid
        except sqlite3.Error as e:
            logger.error(f"Error creating order: {e}")
            return None

    def update_status(self, order_id: int, status: str) -> bool:
        """Update order status. Transaction-safe."""
        try:
            with db_context(self.db_name, transactional=True) as db:
                db.execute(
                    'UPDATE orders SET status = ? WHERE id = ?',
                    (status, order_id)
                )
            return True
        except sqlite3.Error as e:
            logger.error(f"Error updating order {order_id} status: {e}")
            return False

    def cancel_by_activation_id(self, activation_id: int) -> bool:
        """
        Mark an order as CANCELED by activation_id.
        Checks that it's not already canceled.
        Returns True if canceled, False if already canceled or not found.
        """
        try:
            with db_context(self.db_name, transactional=True) as db:
                row = db.fetchone(
                    'SELECT id, status FROM orders WHERE activation_id = ?',
                    (activation_id,)
                )
                if row is None:
                    return False
                if row['status'].upper() == 'CANCELED':
                    return False  # Already canceled

                db.execute(
                    "UPDATE orders SET status = 'CANCELED' WHERE activation_id = ?",
                    (activation_id,)
                )
                return True
        except sqlite3.Error as e:
            logger.error(f"Error canceling order {activation_id}: {e}")
            return False

    def save_activation_code(self, order_id: int, code: str) -> bool:
        """Save a received activation code."""
        try:
            with db_context(self.db_name, transactional=True) as db:
                db.execute(
                    'INSERT INTO activation_codes (order_id, code) VALUES (?, ?)',
                    (order_id, code)
                )
            return True
        except sqlite3.Error as e:
            logger.error(f"Error saving activation code for order {order_id}: {e}")
            return False

    # ── Revenue queries ────────────────────────────────────────

    def sum_revenue(self, days: int = 0) -> int:
        """Sum prices for recent orders. days=0 means today."""
        if days == 0:
            row = self._fetchone(
                "SELECT COALESCE(SUM(price), 0) as total FROM orders "
                "WHERE date(created_at) = date('now')"
            )
        else:
            row = self._fetchone(
                "SELECT COALESCE(SUM(price), 0) as total FROM orders "
                "WHERE date(created_at) >= date('now', ?)",
                (f'-{days} days',)
            )
        return row['total'] if row else 0

    def count_active(self) -> int:
        """Count active orders."""
        row = self._fetchone("SELECT COUNT(*) as cnt FROM orders WHERE status = 'PENDING'")
        return row['cnt'] if row else 0