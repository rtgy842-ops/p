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

import logging
import json
from datetime import datetime
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
    Records to admin.db for persistence.
    """

    def __init__(self):
        self._ensure_table()

    def _ensure_table(self) -> None:
        """Create the audit_log table if it doesn't exist."""
        try:
            with db_context('admin_db', transactional=True) as db:
                db.execute('''
                    CREATE TABLE IF NOT EXISTS audit_log (
                        id          INTEGER PRIMARY KEY AUTOINCREMENT,
                        admin_id    INTEGER NOT NULL,
                        action      TEXT NOT NULL,
                        target      TEXT DEFAULT '',
                        details     TEXT DEFAULT '',
                        ip_address  TEXT DEFAULT '',
                        created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                db.execute(
                    'CREATE INDEX IF NOT EXISTS idx_audit_admin ON audit_log(admin_id)'
                )
                db.execute(
                    'CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action)'
                )
                db.execute(
                    'CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at)'
                )
        except Exception as e:
            logger.error(f"Error creating audit table: {e}")

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
            with db_context('admin_db', transactional=True) as db:
                db.execute(
                    '''INSERT INTO audit_log
                       (admin_id, action, target, details, ip_address)
                       VALUES (?, ?, ?, ?, ?)''',
                    (admin_id, action, str(target), str(details)[:2000], ip_address)
                )
            return True
        except Exception as e:
            logger.error(f"Audit log error: {e}")
            return False

    def get_recent(self, limit: int = 50, admin_id: int | None = None):
        """Get recent audit entries, optionally filtered by admin."""
        from db.connection import ConnectionManager
        cm = ConnectionManager.get_instance()
        conn = cm.get_connection('admin_db')
        cursor = conn.cursor()

        if admin_id:
            cursor.execute(
                'SELECT * FROM audit_log WHERE admin_id = ? '
                'ORDER BY created_at DESC LIMIT ?',
                (admin_id, limit)
            )
        else:
            cursor.execute(
                'SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?',
                (limit,)
            )
        return cursor.fetchall()

    def get_by_action(self, action: str, limit: int = 50):
        """Get audit entries filtered by action type."""
        from db.connection import ConnectionManager
        cm = ConnectionManager.get_instance()
        conn = cm.get_connection('admin_db')
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM audit_log WHERE action = ? '
            'ORDER BY created_at DESC LIMIT ?',
            (action, limit)
        )
        return cursor.fetchall()


# ── Global instance ────────────────────────────────────────────
audit_service = AuditService()
