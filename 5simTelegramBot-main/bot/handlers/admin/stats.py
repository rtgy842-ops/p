"""
bot/handlers/admin/stats.py — Admin Statistics (Enterprise)
─────────────────────────────────────────────────
Uses UserRepository + SettingsRepository — no direct sqlite3.
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


@router.callback('admin_stats')
def handle_admin_stats(call):
    user_id = call.from_user.id
    if user_id not in BOT_CONFIG['admin_ids']:
        _bot.answer_callback_query(call.id, get_text(user_id, 'errors.no_access'))
        return
    try:
        from db.repositories.order_repository import OrderRepository
        from db.repositories.settings_repository import SettingsRepository
        from db.repositories.user_repository import UserRepository

        user_repo = UserRepository()
        settings_repo = SettingsRepository()
        order_repo = OrderRepository()

        total_users = user_repo.count_all()
        usd_rate_val = settings_repo.get('usd_rate')
        usd_rate = float(usd_rate_val) if usd_rate_val else 0
        profit_val = settings_repo.get('profit_percentage')
        profit_pct = float(profit_val) if profit_val else 30

        today_total = order_repo.sum_revenue(0)
        week_total = order_repo.sum_revenue(7)
        month_total = order_repo.sum_revenue(30)

        today_income = int(today_total - (today_total / (1 + profit_pct / 100))) if profit_pct > 0 else 0
        week_income = int(week_total - (week_total / (1 + profit_pct / 100))) if profit_pct > 0 else 0
        month_income = int(month_total - (month_total / (1 + profit_pct / 100))) if profit_pct > 0 else 0

        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            types.InlineKeyboardButton(f"{total_users:,}", callback_data="show_users"),
            types.InlineKeyboardButton(get_text(user_id, 'admin.total_users'), callback_data="show_users"))
        keyboard.add(
            types.InlineKeyboardButton(f"{usd_rate:,}", callback_data="show_rate"),
            types.InlineKeyboardButton(get_text(user_id, 'admin.ruble_label'), callback_data="show_rate"))
        keyboard.add(
            types.InlineKeyboardButton(f"{today_income:,}", callback_data="today_income"),
            types.InlineKeyboardButton(get_text(user_id, 'admin.today_income'), callback_data="today_income"))
        keyboard.add(
            types.InlineKeyboardButton(f"{week_income:,}", callback_data="week_income"),
            types.InlineKeyboardButton(get_text(user_id, 'admin.week_income'), callback_data="week_income"))
        keyboard.add(
            types.InlineKeyboardButton(f"{month_income:,}", callback_data="month_income"),
            types.InlineKeyboardButton(get_text(user_id, 'admin.month_income'), callback_data="month_income"))
        keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'admin.update_rate'), callback_data="update_rate"))
        keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_admin'), callback_data="admin_panel"))
        _bot.edit_message_text(get_text(user_id, 'admin.stats_title'), call.message.chat.id, call.message.message_id,
                               reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Error in admin_stats: {e}")
        _bot.answer_callback_query(call.id, get_text(call.from_user.id, 'errors.stats_error'))


@router.callback('update_rate')
def update_currency_rate(call):
    user_id = call.from_user.id
    if user_id not in BOT_CONFIG['admin_ids']:
        return
    from currency_service import CurrencyService
    from db.repositories.settings_repository import SettingsRepository
    currency_service = CurrencyService()
    repo = SettingsRepository()
    current_rate = currency_service.get_usd_rate()
    if current_rate:
        repo.set('usd_rate', str(current_rate))
        _bot.answer_callback_query(call.id, get_text(user_id, 'admin.rate_updated'))
        handle_admin_stats(call)
    else:
        _bot.answer_callback_query(call.id, get_text(user_id, 'admin.rate_update_error'))
