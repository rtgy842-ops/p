"""
tests/test_rbac.py — RBAC Permission Tests
─────────────────────────────────────────────────
Tests role-based access control for all admin roles.
Ensures correct permission assignments.
"""

import pytest

from services.rbac_service import Permission, RBACService, Role


class TestRBACPermissions:
    """RBAC permission validation."""

    def setup_method(self):
        self.rbac = RBACService()

    def test_super_admin_has_all_permissions(self, mock_bot_config):
        """SUPER_ADMIN should have ALL permissions (uses mock_bot_config fixture)."""
        # 1457637832 added to admin_ids by mock_bot_config fixture
        for perm in Permission:
            assert self.rbac.has_permission(1457637832, perm), \
                f"SUPER_ADMIN should have {perm.value}"

    def test_analyst_read_only(self, mock_bot_config):
        """ANALYST should only have read permissions."""
        analyst_id = 999999
        # Non-admin (not in admin_ids) defaults to ANALYST role
        assert self.rbac.has_permission(analyst_id, Permission.USERS_VIEW) is False
        # Set explicit role using admin from mock_bot_config
        self.rbac.set_role(analyst_id, Role.ANALYST, 1457637832)

        assert self.rbac.has_permission(analyst_id, Permission.ANALYTICS_VIEW)
        assert self.rbac.has_permission(analyst_id, Permission.USERS_VIEW)
        assert self.rbac.has_permission(analyst_id, Permission.AUDIT_VIEW)

        # Should NOT have edit permissions
        assert not self.rbac.has_permission(analyst_id, Permission.USERS_EDIT)
        assert not self.rbac.has_permission(analyst_id, Permission.USERS_BALANCE_EDIT)
        assert not self.rbac.has_permission(analyst_id, Permission.PAYMENTS_APPROVE)
        assert not self.rbac.has_permission(analyst_id, Permission.BROADCAST_SEND)

    def test_finance_can_manage_payments(self, mock_bot_config):
        """FINANCE role should manage payments."""
        finance_id = 888888
        # 1457637832 in admin_ids via mock_bot_config — can assign roles
        self.rbac.set_role(finance_id, Role.FINANCE, 1457637832)

        assert self.rbac.has_permission(finance_id, Permission.PAYMENTS_VIEW)
        assert self.rbac.has_permission(finance_id, Permission.PAYMENTS_APPROVE)
        assert self.rbac.has_permission(finance_id, Permission.PAYMENTS_REJECT)
        assert self.rbac.has_permission(finance_id, Permission.USERS_BALANCE_EDIT)

        # Should NOT have channel management
        assert not self.rbac.has_permission(finance_id, Permission.CHANNELS_MANAGE)
        assert not self.rbac.has_permission(finance_id, Permission.BROADCAST_SEND)

    def test_support_cannot_approve_payments(self, mock_bot_config):
        """SUPPORT should NOT approve/reject payments."""
        support_id = 777777
        self.rbac.set_role(support_id, Role.SUPPORT, 1457637832)

        assert self.rbac.has_permission(support_id, Permission.ORDERS_VIEW)
        assert not self.rbac.has_permission(support_id, Permission.PAYMENTS_APPROVE)
        assert not self.rbac.has_permission(support_id, Permission.PAYMENTS_REJECT)

    def test_require_raises_permission_error(self, mock_bot_config):
        """require() should raise on insufficient permissions."""
        analyst_id = 999999
        self.rbac.set_role(analyst_id, Role.ANALYST, 1457637832)

        with pytest.raises(PermissionError):
            self.rbac.require(analyst_id, Permission.USERS_BALANCE_EDIT)

        with pytest.raises(PermissionError):
            self.rbac.require(analyst_id, Permission.BROADCAST_SEND)

    def test_role_hierarchy(self, mock_bot_config):
        """Ensure role permissions are properly scoped."""
        super_admin = 111111
        admin = 222222
        moderator = 333333
        support = 444444
        analyst = 555555

        # Use 1457637832 (in admin_ids via mock) to assign roles
        self.rbac.set_role(super_admin, Role.SUPER_ADMIN, 1457637832)
        self.rbac.set_role(admin, Role.ADMIN, 1457637832)
        self.rbac.set_role(moderator, Role.MODERATOR, 1457637832)
        self.rbac.set_role(support, Role.SUPPORT, 1457637832)
        self.rbac.set_role(analyst, Role.ANALYST, 1457637832)

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
