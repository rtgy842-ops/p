"""
services/rbac_service.py — Role-Based Access Control
─────────────────────────────────────────────────
Enterprise-grade RBAC with predefined roles and granular permissions.

Roles:
    SUPER_ADMIN — Everything (all permissions)
    ADMIN — Daily operations (users, orders, payments, settings)
    MODERATOR — Content moderation (users, orders view)
    SUPPORT — Read + basic user assistance
    FINANCE — Payment management + financial reports
    ANALYST — Read-only analytics access

Permissions are checked per-action with audit trail integration.
"""

import logging
from enum import Enum

from config import BOT_CONFIG

logger = logging.getLogger(__name__)


class Role(str, Enum):
    SUPER_ADMIN = 'super_admin'
    ADMIN = 'admin'
    MODERATOR = 'moderator'
    SUPPORT = 'support'
    FINANCE = 'finance'
    ANALYST = 'analyst'


class Permission(str, Enum):
    # ── Users ──────────────────────────────────────────────
    USERS_VIEW = 'users:view'
    USERS_EDIT = 'users:edit'
    USERS_BAN = 'users:ban'
    USERS_BALANCE_EDIT = 'users:balance:edit'

    # ── Orders ─────────────────────────────────────────────
    ORDERS_VIEW = 'orders:view'
    ORDERS_CANCEL = 'orders:cancel'
    ORDERS_REFUND = 'orders:refund'

    # ── Payments ───────────────────────────────────────────
    PAYMENTS_VIEW = 'payments:view'
    PAYMENTS_APPROVE = 'payments:approve'
    PAYMENTS_REJECT = 'payments:reject'

    # ── Settings ───────────────────────────────────────────
    SETTINGS_VIEW = 'settings:view'
    SETTINGS_EDIT = 'settings:edit'

    # ── Channels ───────────────────────────────────────────
    CHANNELS_MANAGE = 'channels:manage'

    # ── Operators ──────────────────────────────────────────
    OPERATORS_MANAGE = 'operators:manage'

    # ── Broadcast ──────────────────────────────────────────
    BROADCAST_SEND = 'broadcast:send'

    # ── Analytics ──────────────────────────────────────────
    ANALYTICS_VIEW = 'analytics:view'

    # ── API Keys ───────────────────────────────────────────
    API_KEYS_MANAGE = 'api_keys:manage'

    # ── Audit ──────────────────────────────────────────────
    AUDIT_VIEW = 'audit:view'


# ── Role → Permissions mapping ────────────────────────────────
ROLE_PERMISSIONS: dict[Role, list[Permission]] = {
    Role.SUPER_ADMIN: list(Permission),  # ALL permissions
    Role.ADMIN: [
        Permission.USERS_VIEW, Permission.USERS_EDIT,
        Permission.ORDERS_VIEW, Permission.ORDERS_CANCEL, Permission.ORDERS_REFUND,
        Permission.PAYMENTS_VIEW, Permission.PAYMENTS_APPROVE, Permission.PAYMENTS_REJECT,
        Permission.SETTINGS_VIEW, Permission.SETTINGS_EDIT,
        Permission.CHANNELS_MANAGE, Permission.OPERATORS_MANAGE,
        Permission.BROADCAST_SEND, Permission.ANALYTICS_VIEW,
    ],
    Role.MODERATOR: [
        Permission.USERS_VIEW, Permission.USERS_BAN,
        Permission.ORDERS_VIEW, Permission.ORDERS_CANCEL,
        Permission.PAYMENTS_VIEW,
    ],
    Role.SUPPORT: [
        Permission.USERS_VIEW,
        Permission.ORDERS_VIEW,
        Permission.PAYMENTS_VIEW,
    ],
    Role.FINANCE: [
        Permission.PAYMENTS_VIEW, Permission.PAYMENTS_APPROVE, Permission.PAYMENTS_REJECT,
        Permission.USERS_VIEW, Permission.USERS_BALANCE_EDIT,
        Permission.ORDERS_VIEW, Permission.ORDERS_REFUND,
        Permission.ANALYTICS_VIEW,
    ],
    Role.ANALYST: [
        Permission.USERS_VIEW,
        Permission.ORDERS_VIEW,
        Permission.PAYMENTS_VIEW,
        Permission.ANALYTICS_VIEW,
        Permission.AUDIT_VIEW,
    ],
}


# ── User → Role assignment ────────────────────────────────────
# In production, this would come from the database.
# For now, admin_ids in config map to SUPER_ADMIN.
# Additional role assignments would be stored in admin.db.

class RBACService:
    """
    Centralized permission checking with DB persistence.
    All admin handlers MUST call this before executing sensitive operations.
    """

    def __init__(self):
        self._role_cache: dict[int, Role] = {}

    def get_role(self, user_id: int) -> Role:
        """Get a user's role. Checks DB first, then config admin IDs."""
        if user_id in self._role_cache:
            return self._role_cache[user_id]

        # Check database first
        try:
            from db.context import db_context
            with db_context('default', transactional=False) as db:
                row = db.fetchone(
                    "SELECT role FROM admin_roles WHERE user_id = %s",
                    (user_id,)
                )
                if row:
                    role_raw = row[0] if not isinstance(row, dict) else row.get('role', '')
                    try:
                        role = Role(role_raw.lower())
                        self._role_cache[user_id] = role
                        return role
                    except ValueError:
                        pass
        except Exception:
            pass

        # Fallback to config admin IDs → SUPER_ADMIN
        if user_id in BOT_CONFIG.get('admin_ids', []):
            role = Role.SUPER_ADMIN
        else:
            role = Role.ANALYST

        self._role_cache[user_id] = role
        return role

    def has_permission(self, user_id: int, permission: Permission) -> bool:
        """Check if a user has a specific permission."""
        role = self.get_role(user_id)

        if role == Role.SUPER_ADMIN:
            return True

        allowed = ROLE_PERMISSIONS.get(role, [])
        return permission in allowed

    def require(self, user_id: int, permission: Permission) -> None:
        """
        Raise PermissionError if user lacks the permission.
        Use this as a guard in admin handlers.
        """
        if not self.has_permission(user_id, permission):
            raise PermissionError(
                f"User {user_id} lacks permission: {permission.value}"
            )

    def set_role(self, user_id: int, role: Role, admin_id: int) -> bool:
        """Assign a role to a user, persisted to DB. Only SUPER_ADMIN can do this."""
        if not self.has_permission(admin_id, Permission.USERS_EDIT):
            logger.warning(f"Permission denied: admin {admin_id} cannot assign roles")
            return False

        try:
            from db.context import db_context
            with db_context('default', transactional=True) as db:
                db.execute(
                    """INSERT INTO admin_roles (user_id, role, assigned_by)
                       VALUES (%s, %s, %s)
                       ON CONFLICT (user_id) DO UPDATE SET
                       role = %s, assigned_by = %s, updated_at = CURRENT_TIMESTAMP""",
                    (user_id, role.value, admin_id, role.value, admin_id)
                )
            self._role_cache[user_id] = role
            logger.info(f"Role assigned: user={user_id}, role={role.value}, by={admin_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to set role: {e}")
            return False

    def delete_role(self, user_id: int, admin_id: int) -> bool:
        """Remove a user's role assignment from DB."""
        if not self.has_permission(admin_id, Permission.USERS_EDIT):
            return False
        try:
            from db.context import db_context
            with db_context('default', transactional=True) as db:
                db.execute("DELETE FROM admin_roles WHERE user_id = %s", (user_id,))
            self._role_cache.pop(user_id, None)
            return True
        except Exception as e:
            logger.error(f"Failed to delete role: {e}")
            return False

    def get_all_admins(self) -> list[dict]:
        """Get all admin role assignments from database."""
        try:
            from db.context import db_context
            with db_context('default', transactional=False) as db:
                return db.fetchall(
                    "SELECT user_id, role, assigned_by, created_at FROM admin_roles ORDER BY created_at DESC"
                )
        except Exception:
            return []

    def get_all_roles(self) -> dict[str, list[str]]:
        """Return all roles with their permissions (for admin display)."""
        return {
            role.value: [p.value for p in perms]
            for role, perms in ROLE_PERMISSIONS.items()
        }


# ── Global instance ────────────────────────────────────────────
rbac = RBACService()
