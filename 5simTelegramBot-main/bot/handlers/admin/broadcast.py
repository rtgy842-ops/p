"""
bot/handlers/admin/broadcast.py — Admin Broadcast (Enterprise)
─────────────────────────────────────────────────
Uses UserRepository — no direct sqlite3.
"""

import logging

from telebot import types

from bot.router import router
from config import BOT_CONFIG
from i18n import get_text

logger = logging.getLogger(__name__)
_bot = None


def init(bot_instance):
    global _bot
    _bot = bot_instance


@router.callback('broadcast_message')
def handle_broadcast(call):
    user_id = call.from_user.id
    if user_id not in BOT_CONFIG['admin_ids']:
        return
    msg = _bot.edit_message_text(get_text(user_id, 'admin.broadcast_prompt'),
                                  call.message.chat.id, call.message.message_id)
    _bot.register_next_step_handler(msg, process_broadcast)


def process_broadcast(message):
    if message.from_user.id not in BOT_CONFIG['admin_ids']:
        return
    try:
        from db.repositories.user_repository import UserRepository
        repo = UserRepository()
        users = repo.get_all_ids()
        success = failed = 0
        for row in users:
            uid = row['user_id'] if isinstance(row, dict) else row[0]
            try:
                _bot.send_message(uid, get_text(message.from_user.id, 'admin.broadcast_from_admin',
                                                message=message.text))
                success += 1
            except Exception:
                failed += 1
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(
            get_text(message.from_user.id, 'navigation.back_to_users'), callback_data="manage_users"))
        _bot.reply_to(message,
                      get_text(message.from_user.id, 'admin.broadcast_sent',
                               success=success, failed=failed, total=success + failed),
                      reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Broadcast error: {e}")
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(
            get_text(message.from_user.id, 'navigation.back_to_users'), callback_data="manage_users"))
        _bot.reply_to(message, get_text(message.from_user.id, 'admin.broadcast_error'), reply_markup=keyboard)
