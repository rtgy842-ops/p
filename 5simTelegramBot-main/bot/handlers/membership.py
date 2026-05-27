"""
bot/handlers/membership.py — Channel Membership Check Handler
──────────────────────────────────────────────────────────────
check_membership — verifies user joined required channels.
"""

import logging
from bot.router import router
from i18n import get_text
from config import BOT_CONFIG
from admin_config import AdminConfig

logger = logging.getLogger(__name__)

_bot = None


def init(bot_instance):
    global _bot
    _bot = bot_instance


@router.callback('check_membership')
def check_membership(call):
    from telebot import types
    from bot.keyboards.main_keyboard import inline_main_keyboard

    try:
        user_id = call.from_user.id
        admin_config = AdminConfig()
        channels = admin_config.get_required_channels()

        if not channels:
            _bot.edit_message_text(
                get_text(user_id, 'welcome_approved').split('\n')[0],
                call.message.chat.id, call.message.message_id,
                reply_markup=inline_main_keyboard(user_id)
            )
            return

        not_subscribed = []
        for channel in channels:
            try:
                member = _bot.get_chat_member(f"@{channel[0]}", user_id)
                if member.status in ['left', 'kicked', 'restricted']:
                    channel_info = _bot.get_chat(f"@{channel[0]}")
                    not_subscribed.append((channel_info.title or channel[1], channel[2]))
            except Exception as e:
                logger.error(f"Error checking membership for {channel[0]}: {e}")
                continue

        if not_subscribed:
            text = get_text(user_id, 'channels.membership_check')
            keyboard = types.InlineKeyboardMarkup(row_width=1)
            for channel_name, channel_link in not_subscribed:
                text += f"• {channel_name}\n"
                keyboard.add(types.InlineKeyboardButton(
                    get_text(user_id, 'channels.join_channel', channel=channel_name), url=channel_link))
            keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'channels.check_again'), callback_data="check_membership"))
            _bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
        else:
            _bot.edit_message_text(get_text(user_id, 'welcome_approved'), call.message.chat.id, call.message.message_id,
                                   reply_markup=inline_main_keyboard(user_id))

    except Exception as e:
        logger.error(f"Error in check_membership: {e}")
        _bot.answer_callback_query(call.id, get_text(call.from_user.id, 'errors.general_short'))