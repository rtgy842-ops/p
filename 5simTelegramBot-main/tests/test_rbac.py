"""
tests/test_rbac.py — RBAC Permission Tests
─────────────────────────────────────────────────
Tests role-based access control for all admin roles.
Ensures correct permission assignments.
"""

import pytest
from services.rbac_service import RBACService, Role, Permission


class TestRBACPermissions:
    """RBAC permission validation."""

    def setup_method(self):
        self.rbac = RBACService()

    def test_super_admin_has_all_permissions(self):
        """SUPER_ADMIN should have ALL permissions."""
        for perm in Permission:
            assert self.rbac.has_permission(1457637832, perm), \
                f"SUPER_ADMIN should have {perm.value}"

    def test_analyst_read_only(self):
        """ANALYST should only have read permissions."""
        # Mock a non-admin user with ANALYST role
        analyst_id = 999999

        # Should have read permissions
        assert self.rbac.has_permission(analyst_id, Permission.USERS_VIEW) is False
        # Non-admin defaults to ANALYST which CAN view but NOT edit
        # Set explicit role
        self.rbac.set_role(analyst_id, Role.ANALYST, 1457637832)

        assert self.rbac.has_permission(analyst_id, Permission.ANALYTICS_VIEW)
        assert self.rbac.has_permission(analyst_id, Permission.USERS_VIEW)
        assert self.rbac.has_permission(analyst_id, Permission.AUDIT_VIEW)

        # Should NOT have edit permissions
        assert not self.rbac.has_permission(analyst_id, Permission.USERS_EDIT)
        assert not self.rbac.has_permission(analyst_id, Permission.USERS_BALANCE_EDIT)
        assert not self.rbac.has_permission(analyst_id, Permission.PAYMENTS_APPROVE)
        assert not self.rbac.has_permission(analyst_id, Permission.BROADCAST_SEND)

    def test_finance_can_manage_payments(self):
        """FINANCE role should manage payments."""
        finance_id = 888888
        self.rbac.set_role(finance_id, Role.FINANCE, 1457637832)

        assert self.rbac.has_permission(finance_id, Permission.PAYMENTS_VIEW)
        assert self.rbac.has_permission(finance_id, Permission.PAYMENTS_APPROVE)
        assert self.rbac.has_permission(finance_id, Permission.PAYMENTS_REJECT)
        assert self.rbac.has_permission(finance_id, Permission.USERS_BALANCE_EDIT)

        # Should NOT have channel management
        assert not self.rbac.has_permission(finance_id, Permission.CHANNELS_MANAGE)
        assert not self.rbac.has_permission(finance_id, Permission.BROADCAST_SEND)

    def test_support_cannot_approve_payments(self):
        """SUPPORT should NOT approve/reject payments."""
        support_id = 777777
        self.rbac.set_role(support_id, Role.SUPPORT, 1457637832)

        assert self.rbac.has_permission(support_id, Permission.ORDERS_VIEW)
        assert not self.rbac.has_permission(support_id, Permission.PAYMENTS_APPROVE)
        assert not self.rbac.has_permission(support_id, Permission.PAYMENTS_REJECT)

    def test_require_raises_permission_error(self):
        """require() should raise on insufficient permissions."""
        analyst_id = 999999
        self.rbac.set_role(analyst_id, Role.ANALYST, 1457637832)

        with pytest.raises(PermissionError):
            self.rbac.require(analyst_id, Permission.USERS_BALANCE_EDIT)

        with pytest.raises(PermissionError):
            self.rbac.require(analyst_id, Permission.BROADCAST_SEND)

    def test_role_hierarchy(self):
        """Ensure role permissions are properly scoped."""
        # SUPER_ADMIN > ADMIN > MODERATOR > SUPPORT > ANALYST
        super_admin = 111111
        admin = 222222
        moderator = 333333
        support = 444444
        analyst = 555555

        self.rbac.set_role(super_admin, Role.SUPER_ADMIN, super_admin)
        self.rbac.set_role(admin, Role.ADMIN, super_admin)
        self.rbac.set_role(moderator, Role.MODERATOR, super_admin)
        self.rbac.set_role(support, Role.SUPPORT, super_admin)
        self.rbac.set_role(analyst, Role.ANALYST, super_admin)

        # SUPER_ADMIN can do everything
        assert self.rbac.has_permission(super_admin, Permission.SETTINGS_EDIT)
        assert self.rbac.has_permission(super_admin, Permission.API_KEYS_MANAGE)

        # ADMIN can manage settings but not API keys
        assert self.rbac.has_permission(admin, Permission.SETTINGS_EDIT)
        assert not self.rbac.has_permission(admin, Permission.API_KEYS_MANAGE)

        # MODERATOR can ban users but not edit settings
        assert self.rbac.has_permission(moderator, Permission.USERS_BAN)
        assert not self.rbac.has_permission(moderator, Permission.SETTINGS_EDIT)

        # SUPPORT can view only
        assert self.rbac.has_permission(support, Permission.USERS_VIEW)
        assert not self.rbac.has_permission(support, Permission.USERS_BAN)

        # ANALYST can view analytics and audit
        assert self.rbac.has_permission(analyst, Permission.ANALYTICS_VIEW)
        assert self.rbac.has_permission(analyst, Permission.AUDIT_VIEW)
