"""
bot/handlers/admin/stats.py — Admin Statistics Handler
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

@router.callback('admin_stats')
def handle_admin_stats(call):
    user_id = call.from_user.id
    if user_id not in BOT_CONFIG['admin_ids']:
        _bot.answer_callback_query(call.id, get_text(user_id, 'errors.no_access')); return
    try:
        users_conn = sqlite3.connect('users.db'); users_cursor = users_conn.cursor()
        users_cursor.execute('SELECT COUNT(DISTINCT user_id) FROM users'); total_users = users_cursor.fetchone()[0]
        users_conn.close()

        bot_conn = sqlite3.connect('bot.db'); bot_cursor = bot_conn.cursor()
        admin_conn = sqlite3.connect('admin.db'); admin_cursor = admin_conn.cursor()
        admin_cursor.execute('SELECT value FROM settings WHERE key = "usd_rate"'); usd_rate = float(admin_cursor.fetchone()[0] or 0) if admin_cursor.fetchone() else 0
        admin_cursor.execute('SELECT value FROM settings WHERE key = "profit_percentage"'); profit_pct = float(admin_cursor.fetchone()[0] or 30) if admin_cursor.fetchone() else 30
        admin_conn.close()

        bot_cursor.execute('SELECT COALESCE(SUM(price), 0) FROM orders WHERE date(created_at) = date("now")'); today_total = bot_cursor.fetchone()[0] or 0
        today_income = int(today_total - (today_total / (1 + profit_pct / 100))) if profit_pct > 0 else 0
        bot_cursor.execute('SELECT COALESCE(SUM(price), 0) FROM orders WHERE date(created_at) >= date("now", "-7 days")'); week_total = bot_cursor.fetchone()[0] or 0
        week_income = int(week_total - (week_total / (1 + profit_pct / 100))) if profit_pct > 0 else 0
        bot_cursor.execute('SELECT COALESCE(SUM(price), 0) FROM orders WHERE date(created_at) >= date("now", "-30 days")'); month_total = bot_cursor.fetchone()[0] or 0
        month_income = int(month_total - (month_total / (1 + profit_pct / 100))) if profit_pct > 0 else 0
        bot_conn.close()

        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(types.InlineKeyboardButton(f"{total_users:,}", callback_data="show_users"), types.InlineKeyboardButton(get_text(user_id, 'admin.total_users'), callback_data="show_users"))
        keyboard.add(types.InlineKeyboardButton(f"{usd_rate:,}", callback_data="show_rate"), types.InlineKeyboardButton(get_text(user_id, 'admin.ruble_label'), callback_data="show_rate"))
        keyboard.add(types.InlineKeyboardButton(f"{today_income:,}", callback_data="today_income"), types.InlineKeyboardButton(get_text(user_id, 'admin.today_income'), callback_data="today_income"))
        keyboard.add(types.InlineKeyboardButton(f"{week_income:,}", callback_data="week_income"), types.InlineKeyboardButton(get_text(user_id, 'admin.week_income'), callback_data="week_income"))
        keyboard.add(types.InlineKeyboardButton(f"{month_income:,}", callback_data="month_income"), types.InlineKeyboardButton(get_text(user_id, 'admin.month_income'), callback_data="month_income"))
        keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'admin.update_rate'), callback_data="update_rate"))
        keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_admin'), callback_data="admin_panel"))
        _bot.edit_message_text(get_text(user_id, 'admin.stats_title'), call.message.chat.id, call.message.message_id, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Error in admin_stats: {e}")
        _bot.answer_callback_query(call.id, get_text(call.from_user.id, 'errors.stats_error'))

@router.callback('update_rate')
def update_currency_rate(call):
    user_id = call.from_user.id
    if user_id not in BOT_CONFIG['admin_ids']: return
    from currency_service import CurrencyService
    from admin_config import AdminConfig
    currency_service = CurrencyService(); admin_config = AdminConfig()
    current_rate = currency_service.get_usd_rate()
    if current_rate:
        admin_config.set_usd_rate(current_rate)
        _bot.answer_callback_query(call.id, get_text(user_id, 'admin.rate_updated'))
        handle_admin_stats(call)
    else:
        _bot.answer_callback_query(call.id, get_text(user_id, 'admin.rate_update_error'))