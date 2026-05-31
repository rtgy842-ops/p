"""
bot/handlers/subscriptions.py — Customer Subscription Handlers
─────────────────────────────────────────────────
Allows customers to:
- View current subscription plan
- See plan benefits and limits
- Upgrade/downgrade (admin only for now)
"""
import logging

from telebot import types

from bot.router import router
from i18n import get_text

logger = logging.getLogger(__name__)
_bot = None


def init(bot_instance):
    global _bot
    _bot = bot_instance


@router.callback('subscriptions')
def show_subscription_menu(call):
    """Main subscription page."""
    from services.subscription_service import SubscriptionTier, subscriptions
    user_id = call.from_user.id

    tier = subscriptions.get_tier(user_id)
    info = subscriptions.get_subscription_info(user_id)
    limits = subscriptions.get_limits(user_id)

    tier_names = {
        SubscriptionTier.FREE: "🆓 Free",
        SubscriptionTier.BASIC: "🥉 Basic",
        SubscriptionTier.PREMIUM: "🥈 Premium",
        SubscriptionTier.RESELLER: "🥇 Reseller",
        SubscriptionTier.BUSINESS: "💼 Business",
        SubscriptionTier.ENTERPRISE: "🏢 Enterprise",
    }

    text = (
        f"🎫 **Subscription**\n\n"
        f"Plan: **{tier_names.get(tier, tier.value)}**\n"
        f"Daily limit: **{limits['max_daily']}** numbers\n"
        f"Discount: **{limits['discount_pct']}%**\n"
        f"API access: {'✅' if limits['api_access'] else '❌'}\n"
    )
    if info and info.get('expires_at'):
        text += f"Expires: {info['expires_at']}\n"

    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("📊 View All Plans", callback_data="subs_plans"),
        types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_main'), callback_data="back_to_main"),
    )
    _bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                           reply_markup=kb, parse_mode='Markdown')


@router.callback('subs_plans')
def show_all_plans(call):
    """Display all subscription plans."""
    from services.subscription_service import subscriptions

    tiers = subscriptions.get_all_tiers()
    lines = ["📊 **Subscription Plans**\n"]

    for name, limits in tiers.items():
        emoji = {'free': '🆓', 'basic': '🥉', 'premium': '🥈', 'reseller': '🥇',
                 'business': '💼', 'enterprise': '🏢'}.get(name, '')
        lines.append(
            f"{emoji} **{name.upper()}**: {limits['max_daily']}/day, "
            f"{limits['discount_pct']}% off, API: {'✅' if limits['api_access'] else '❌'}"
        )

    lines.append("\n_Contact support to upgrade._")

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("◀️ Back", callback_data="subscriptions"))
    _bot.edit_message_text('\n'.join(lines), call.message.chat.id, call.message.message_id,
                           reply_markup=kb, parse_mode='Markdown')
