"""
services/audit_service.py — DB-backed Audit Trail
─────────────────────────────────────────────────
Records ALL sensitive admin actions with:
- Who did it
- What changed
- When it happened
- IP address (when available)
- Before/after values (for data changes)

This is the compliance-grade audit system.
"""

import json
import logging

from db.connection import ConnectionManager
from db.context import db_context

logger = logging.getLogger(__name__)


class AuditAction(str):
    """Standardized audit action types."""
    # Balance
    BALANCE_ADD = 'balance:add'
    BALANCE_DEDUCT = 'balance:deduct'
    BALANCE_REFUND = 'balance:refund'

    # User
    USER_BAN = 'user:ban'
    USER_UNBAN = 'user:unban'
    USER_ROLE_CHANGE = 'user:role_change'

    # Payment
    PAYMENT_APPROVE = 'payment:approve'
    PAYMENT_REJECT = 'payment:reject'

    # Settings
    SETTING_CHANGE = 'setting:change'
    USD_RATE_CHANGE = 'usd_rate:change'
    PROFIT_CHANGE = 'profit:change'

    # Channels
    CHANNEL_ADD = 'channel:add'
    CHANNEL_REMOVE = 'channel:remove'
    LOCK_TOGGLE = 'lock:toggle'

    # Operator
    OPERATOR_CHANGE = 'operator:change'

    # Card
    CARD_UPDATE = 'card:update'

    # API
    API_KEY_CREATE = 'api_key:create'
    API_KEY_REVOKE = 'api_key:revoke'


class AuditService:
    """
    Persistent audit log for all sensitive operations.
    Records to PostgreSQL main database (schema is in db/schema.py).
    """

    def __init__(self):
        pass  # Schema managed by db/schema.py + migrations

    def log(self, admin_id: int, action: str, target: str = '',
            details: dict | str = '', ip_address: str = '') -> bool:
        """
        Record an audit entry.

        Args:
            admin_id: The admin who performed the action
            action: One of AuditAction values
            target: The entity affected (user_id, payment_id, setting_key, etc.)
            details: Additional info (before/after values, reason, etc.)
            ip_address: IP of the admin (from request context)
        """
        if isinstance(details, dict):
            details = json.dumps(details, ensure_ascii=False)

        try:
            with db_context('default', transactional=True) as db:
                db.execute(
                    '''INSERT INTO audit_log
                       (admin_id, action, target, details, ip_address)
                       VALUES (%s, %s, %s, %s, %s)''',
                    (admin_id, action, str(target), str(details)[:2000], ip_address)
                )
            return True
        except Exception as e:
            logger.error(f"Audit log error: {e}")
            return False

    def get_recent(self, limit: int = 50, admin_id: int | None = None):
        """Get recent audit entries, optionally filtered by admin."""
        cm = ConnectionManager.get_instance()
        conn = cm.get_connection('default')
        cursor = conn.cursor()

        if admin_id:
            cursor.execute(
                'SELECT * FROM audit_log WHERE admin_id = %s '
                'ORDER BY created_at DESC LIMIT %s',
                (admin_id, limit)
            )
        else:
            cursor.execute(
                'SELECT * FROM audit_log ORDER BY created_at DESC LIMIT %s',
                (limit,)
            )
        result = cursor.fetchall()
        cm.put_connection(conn)
        return result

    def get_by_action(self, action: str, limit: int = 50):
        """Get audit entries filtered by action type."""
        cm = ConnectionManager.get_instance()
        conn = cm.get_connection('default')
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM audit_log WHERE action = %s '
            'ORDER BY created_at DESC LIMIT %s',
            (action, limit)
        )
        result = cursor.fetchall()
        cm.put_connection(conn)
        return result


# ── Global instance ────────────────────────────────────────────
audit_service = AuditService()
