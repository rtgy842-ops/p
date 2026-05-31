"""
bot/handlers/referrals.py — Customer Referral Handlers
─────────────────────────────────────────────────
Allows customers to:
- View their referral code
- See referral statistics & earnings
- See list of referred users
"""
import logging
from telebot import types
from bot.router import router
from i18n import get_text
from config import BOT_CONFIG

logger = logging.getLogger(__name__)
_bot = None


def init(bot_instance):
    global _bot
    _bot = bot_instance


@router.callback('referrals')
def show_referral_menu(call):
    """Main referral page."""
    from services.referral_service import referrals as ref_svc
    user_id = call.from_user.id

    code = ref_svc.get_or_create_code(user_id)
    count = ref_svc.get_referral_count(user_id)
    earnings = ref_svc.get_referral_earnings(user_id)

    invite_link = f"https://t.me/{_bot.get_me().username}?start=ref_{code}"

    text = (
        f"🔗 **Referral System**\n\n"
        f"Your code: `{code}`\n"
        f"Invite link: {invite_link}\n"
        f"Total referrals: **{count}**\n"
        f"Total earnings: **{earnings:,}** T\n\n"
        f"Share your link to earn!"
    )

    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("📋 Copy Code", callback_data=f"copy_ref_{code}"),
        types.InlineKeyboardButton("👥 My Referrals", callback_data="referrals_list"),
        types.InlineKeyboardButton("📤 Share", switch_inline_query=f"Join and earn: {invite_link}"),
        types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_main'), callback_data="back_to_main"),
    )
    _bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                           reply_markup=kb, parse_mode='Markdown')


@router.callback('referrals_list')
def show_referred_users(call):
    """List referred users."""
    from services.referral_service import referrals as ref_svc
    user_id = call.from_user.id

    referred = ref_svc.get_referred_users(user_id)

    if not referred:
        text = "👥 You haven't referred anyone yet.\n\nShare your link to start earning!"
    else:
        lines = ["👥 **Your Referrals**\n"]
        for r in referred[:20]:
            uid = r.get('referred_id', '?')
            status = r.get('status', '?')
            earned = r.get('total_earned', 0)
            icon = '✅' if status == 'active' else '⏳'
            lines.append(f"{icon} `{uid}` — +{earned:,} T")
        text = '\n'.join(lines)

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("◀️ Back", callback_data="referrals"))
    _bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                           reply_markup=kb, parse_mode='Markdown')


@router.callback('copy_ref_')
def copy_referral_code(call):
    """Show the code for copying."""
    code = call.data.split('_', 2)[2]
    _bot.answer_callback_query(call.id, f"Your code: {code}", show_alert=True)
