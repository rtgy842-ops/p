"""
bot/handlers/admin/dashboard.py — Admin Dashboard Handler
──────────────────────────────────────────────────────────
/admin command, admin_panel callback.
"""

import logging

from bot.router import router
from config import BOT_CONFIG
from i18n import get_text

logger = logging.getLogger(__name__)
_bot = None

def init(bot_instance):
    global _bot; _bot = bot_instance

@router.command('admin')
def admin_panel(message):
    if message.from_user.id not in BOT_CONFIG['admin_ids']:
        return
    from telebot import types
    user_id = message.from_user.id
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton(get_text(user_id, 'admin.stats'), callback_data="admin_stats"),
        types.InlineKeyboardButton(get_text(user_id, 'admin.set_profit'), callback_data="set_profit"),
        types.InlineKeyboardButton(get_text(user_id, 'admin.set_usd_rate'), callback_data="set_usd_rate"),
        types.InlineKeyboardButton(get_text(user_id, 'admin.manage_channels'), callback_data="manage_channels"),
        types.InlineKeyboardButton(get_text(user_id, 'admin.transactions'), callback_data="transactions"),
        types.InlineKeyboardButton(get_text(user_id, 'admin.manage_users'), callback_data="manage_users"),
        types.InlineKeyboardButton(get_text(user_id, 'admin.operator_settings'), callback_data="operator_settings"),
        types.InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="back_to_main")
    )
    _bot.send_message(message.chat.id, get_text(user_id, 'admin.panel_welcome'), reply_markup=keyboard)

@router.callback('admin_panel')
def handle_admin_panel_button(call):
    from telebot import types
    user_id = call.from_user.id
    if user_id not in BOT_CONFIG['admin_ids']:
        _bot.answer_callback_query(call.id, get_text(user_id, 'errors.no_access')); return
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton(get_text(user_id, 'admin.stats_short'), callback_data="admin_stats"),
        types.InlineKeyboardButton(get_text(user_id, 'admin.manage_users'), callback_data="manage_users"),
        types.InlineKeyboardButton(get_text(user_id, 'admin.broadcast'), callback_data="broadcast_message"),
        types.InlineKeyboardButton(get_text(user_id, 'admin.set_profit'), callback_data="set_profit"),
        types.InlineKeyboardButton(get_text(user_id, 'admin.set_card'), callback_data="set_card"),
        types.InlineKeyboardButton(get_text(user_id, 'admin.set_usd_rate'), callback_data="set_usd_rate"),
        types.InlineKeyboardButton(get_text(user_id, 'admin.transactions'), callback_data="transactions"),
        types.InlineKeyboardButton(get_text(user_id, 'admin.toggle_lock'), callback_data="toggle_lock"),
        types.InlineKeyboardButton(get_text(user_id, 'admin.operator_settings'), callback_data="operator_settings"),
        types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_main'), callback_data="back_to_main")
    )
    _bot.edit_message_text(get_text(user_id, 'admin.panel_title'), call.message.chat.id, call.message.message_id, reply_markup=keyboard)
