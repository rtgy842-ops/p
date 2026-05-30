"""
services/subscription_service.py — Tiered Subscription System
─────────────────────────────────────────────────
Subscription tiers with feature limits and quotas.

Tiers:
    FREE — Basic access, limited features
    PREMIUM — Full access, priority support
    RESELLER — White-label, volume discounts
    ENTERPRISE — Custom, API access, SLA
"""

from enum import Enum
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class SubscriptionTier(str, Enum):
    FREE = 'free'
    PREMIUM = 'premium'
    RESELLER = 'reseller'
    ENTERPRISE = 'enterprise'


@dataclass
class TierLimits:
    """Feature limits per subscription tier."""
    max_daily_orders: int
    max_monthly_orders: int
    price_discount_pct: int  # percentage off
    api_access: bool
    priority_support: bool
    white_label: bool
    custom_domain: bool
    analytics_export: bool


# ── Tier configurations ────────────────────────────────────────
TIER_CONFIG: dict[SubscriptionTier, TierLimits] = {
    SubscriptionTier.FREE: TierLimits(
        max_daily_orders=10,
        max_monthly_orders=100,
        price_discount_pct=0,
        api_access=False,
        priority_support=False,
        white_label=False,
        custom_domain=False,
        analytics_export=False,
    ),
    SubscriptionTier.PREMIUM: TierLimits(
        max_daily_orders=100,
        max_monthly_orders=3000,
        price_discount_pct=5,
        api_access=True,
        priority_support=True,
        white_label=False,
        custom_domain=False,
        analytics_export=True,
    ),
    SubscriptionTier.RESELLER: TierLimits(
        max_daily_orders=1000,
        max_monthly_orders=30000,
        price_discount_pct=15,
        api_access=True,
        priority_support=True,
        white_label=True,
        custom_domain=True,
        analytics_export=True,
    ),
    SubscriptionTier.ENTERPRISE: TierLimits(
        max_daily_orders=99999,
        max_monthly_orders=999999,
        price_discount_pct=25,
        api_access=True,
        priority_support=True,
        white_label=True,
        custom_domain=True,
        analytics_export=True,
    ),
}


class SubscriptionService:
    """
    Manages user subscriptions and enforces limits.
    """

    def __init__(self):
        self._default_tier = SubscriptionTier.FREE

    # ── Database-backed Tier Management ─────────────────────────

    def get_tier(self, user_id: int) -> SubscriptionTier:
        """
        Get user's subscription tier from database.
        Falls back to FREE if no subscription record exists.
        """
        try:
            from db.context import db_context
            with db_context('default', transactional=False) as db:
                row = db.fetchone(
                    "SELECT tier FROM subscriptions WHERE user_id = %s AND status = 'active'",
                    (user_id,)
                )
                if row:
                    tier_raw = row[0] if not isinstance(row, dict) else row.get('tier', 'free')
                    try:
                        return SubscriptionTier(tier_raw.lower())
                    except ValueError:
                        return self._default_tier
        except Exception as e:
            logger.warning(f"Failed to read subscription tier for user {user_id}: {e}")
        return self._default_tier

    def get_limits(self, user_id: int) -> TierLimits:
        """Get feature limits for a user."""
        tier = self.get_tier(user_id)
        return TIER_CONFIG.get(tier, TIER_CONFIG[SubscriptionTier.FREE])

    def can_place_order(self, user_id: int, orders_today: int) -> bool:
        """Check if user can place an order based on daily limit."""
        limits = self.get_limits(user_id)
        return orders_today < limits.max_daily_orders

    def get_discounted_price(self, user_id: int, base_price: int) -> int:
        """Calculate price after subscription discount."""
        limits = self.get_limits(user_id)
        if limits.price_discount_pct > 0:
            return int(base_price * (1 - limits.price_discount_pct / 100))
        return base_price

    def has_api_access(self, user_id: int) -> bool:
        """Check if user has API access."""
        return self.get_limits(user_id).api_access

    def set_tier(self, user_id: int, tier: SubscriptionTier, admin_id: int) -> bool:
        """
        Upgrade/downgrade a user's subscription.
        Persists to database. Requires admin permission.
        """
        from services.rbac_service import rbac, Permission
        if not rbac.has_permission(admin_id, Permission.USERS_EDIT):
            logger.warning(f"Permission denied: admin {admin_id} cannot edit user {user_id}")
            return False

        try:
            from db.context import db_context
            with db_context('default', transactional=True) as db:
                db.execute(
                    """INSERT INTO subscriptions (user_id, tier, status, started_at)
                       VALUES (%s, %s, 'active', CURRENT_TIMESTAMP)
                       ON CONFLICT (user_id) DO UPDATE SET
                       tier = %s, status = 'active', updated_at = CURRENT_TIMESTAMP""",
                    (user_id, tier.value, tier.value)
                )
            logger.info(f"Subscription changed: user={user_id}, tier={tier.value}, by={admin_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to set subscription tier: {e}")
            return False

    def get_subscription_info(self, user_id: int) -> dict | None:
        """Get full subscription info from database."""
        try:
            from db.context import db_context
            with db_context('default', transactional=False) as db:
                row = db.fetchone(
                    "SELECT tier, status, started_at, expires_at, auto_renew FROM subscriptions WHERE user_id = %s",
                    (user_id,)
                )
                if row:
                    return {
                        'tier': row[0] if not isinstance(row, dict) else row.get('tier'),
                        'status': row[1] if not isinstance(row, dict) else row.get('status'),
                        'started_at': str(row[2]) if not isinstance(row, dict) else str(row.get('started_at')),
                        'expires_at': str(row[3]) if not isinstance(row, dict) else str(row.get('expires_at')),
                        'auto_renew': bool(row[4]) if not isinstance(row, dict) else bool(row.get('auto_renew')),
                    }
        except Exception as e:
            logger.error(f"Failed to get subscription info: {e}")
        return None

    def get_all_tiers(self) -> dict:
        """Return all tier configurations for admin display."""
        return {
            tier.value: {
                'max_daily': limits.max_daily_orders,
                'max_monthly': limits.max_monthly_orders,
                'discount_pct': limits.price_discount_pct,
                'api_access': limits.api_access,
                'priority_support': limits.priority_support,
                'white_label': limits.white_label,
            }
            for tier, limits in TIER_CONFIG.items()
        }


# ── Global instance ────────────────────────────────────────────
subscriptions = SubscriptionService()