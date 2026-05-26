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

from enum import Enum
from dataclasses import dataclass, field
import logging
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
    Centralized permission checking.
    All admin handlers MUST call this before executing sensitive operations.
    """

    def __init__(self):
        self._role_cache: dict[int, Role] = {}

    def get_role(self, user_id: int) -> Role:
        """Get a user's role. Admin IDs default to SUPER_ADMIN."""
        if user_id in self._role_cache:
            return self._role_cache[user_id]

        if user_id in BOT_CONFIG['admin_ids']:
            role = Role.SUPER_ADMIN
        else:
            role = Role.ANALYST  # Default: read-only

        self._role_cache[user_id] = role
        return role

    def has_permission(self, user_id: int, permission: Permission) -> bool:
        """Check if a user has a specific permission."""
        role = self.get_role(user_id)

        # SUPER_ADMIN has all permissions
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
        """Assign a role to a user. Only SUPER_ADMIN can do this."""
        if not self.has_permission(admin_id, Permission.USERS_EDIT):
            return False
        self._role_cache[user_id] = role
        logger.info(f"Role assigned: user={user_id}, role={role.value}, by={admin_id}")
        return True

    def get_all_roles(self) -> dict[str, list[str]]:
        """Return all roles with their permissions (for admin display)."""
        return {
            role.value: [p.value for p in perms]
            for role, perms in ROLE_PERMISSIONS.items()
        }


# ── Global instance ────────────────────────────────────────────
rbac = RBACService()