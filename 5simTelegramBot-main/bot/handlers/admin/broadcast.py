"""
bot/handlers/admin/broadcast.py — Admin Broadcast Handler
"""

import logging, sqlite3
from bot.router import router
from i18n import get_text
from config import BOT_CONFIG
from telebot import types

logger = logging.getLogger(__name__)
_bot = None

def init(bot_instance):
    global _bot; _bot = bot_instance

@router.callback('broadcast_message')
def handle_broadcast(call):
    user_id = call.from_user.id
    if user_id not in BOT_CONFIG['admin_ids']: return
    msg = _bot.edit_message_text(get_text(user_id, 'admin.broadcast_prompt'), call.message.chat.id, call.message.message_id)
    _bot.register_next_step_handler(msg, process_broadcast)

def process_broadcast(message):
    if message.from_user.id not in BOT_CONFIG['admin_ids']: return
    try:
        conn = sqlite3.connect('users.db'); cursor = conn.cursor(); cursor.execute('SELECT user_id FROM users'); users = cursor.fetchall(); conn.close()
        success = failed = 0
        for user in users:
            try: _bot.send_message(user[0], get_text(message.from_user.id, 'admin.broadcast_from_admin', message=message.text)); success += 1
            except: failed += 1
        keyboard = types.InlineKeyboardMarkup(); keyboard.add(types.InlineKeyboardButton(get_text(message.from_user.id, 'navigation.back_to_users'), callback_data="manage_users"))
        _bot.reply_to(message, get_text(message.from_user.id, 'admin.broadcast_sent', success=success, failed=failed, total=success+failed), reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Broadcast error: {e}")
        keyboard = types.InlineKeyboardMarkup(); keyboard.add(types.InlineKeyboardButton(get_text(message.from_user.id, 'navigation.back_to_users'), callback_data="manage_users"))
        _bot.reply_to(message, get_text(message.from_user.id, 'admin.broadcast_error'), reply_markup=keyboard)