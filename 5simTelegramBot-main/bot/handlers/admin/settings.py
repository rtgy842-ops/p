"""
bot/handlers/admin/settings.py — Admin Settings (Enterprise)
─────────────────────────────────────────────────
Uses SettingsRepository — no direct sqlite3.
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


def _get_repo():
    from db.repositories.settings_repository import SettingsRepository
    return SettingsRepository()


@router.callback('set_profit')
def handle_set_profit(call):
    user_id = call.from_user.id
    if user_id not in BOT_CONFIG['admin_ids']:
        _bot.answer_callback_query(call.id, get_text(user_id, 'errors.no_access_section'))
        return
    try:
        val = _get_repo().get('profit_percentage')
        current_profit = float(val) if val else 0
        msg = _bot.edit_message_text(get_text(user_id, 'admin.profit_current', profit=current_profit),
                                      call.message.chat.id, call.message.message_id)
        _bot.register_next_step_handler(msg, process_profit_percentage)
    except Exception as e:
        logger.error(f"Error in set_profit: {e}")
        _bot.answer_callback_query(call.id, get_text(call.from_user.id, 'errors.general_short'))


def process_profit_percentage(message):
    admin_id = message.from_user.id
    try:
        profit = float(message.text.strip().replace(',', ''))
        if profit < 0:
            _bot.reply_to(message, get_text(admin_id, 'admin.profit_negative'))
            return
        _get_repo().set('profit_percentage', str(profit))
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            types.InlineKeyboardButton(get_text(admin_id, 'navigation.set_again'), callback_data="set_profit"),
            types.InlineKeyboardButton(get_text(admin_id, 'navigation.back_to_panel'), callback_data="admin_panel"))
        _bot.reply_to(message, get_text(admin_id, 'admin.profit_saved', profit=profit), reply_markup=keyboard)
    except ValueError:
        _bot.reply_to(message, get_text(admin_id, 'admin.profit_invalid'))
    except Exception as e:
        logger.error(f"Error: {e}")


@router.callback('set_usd_rate')
def handle_set_usd_rate(call):
    user_id = call.from_user.id
    if user_id not in BOT_CONFIG['admin_ids']:
        _bot.answer_callback_query(call.id, get_text(user_id, 'errors.no_access_section'))
        return
    msg = _bot.edit_message_text(get_text(user_id, 'admin.ruble_current'), call.message.chat.id, call.message.message_id)
    _bot.register_next_step_handler(msg, process_usd_rate)


def process_usd_rate(message):
    admin_id = message.from_user.id
    if not message.text.replace('.', '').isdigit():
        _bot.reply_to(message, get_text(admin_id, 'admin.ruble_invalid'))
        return
    rate = float(message.text)
    _get_repo().set('usd_rate', str(rate))
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(get_text(admin_id, 'navigation.back_to_panel'), callback_data="admin_panel"))
    _bot.reply_to(message, get_text(admin_id, 'admin.ruble_saved', rate=rate), reply_markup=keyboard)


@router.callback('set_card')
def handle_set_card(call):
    user_id = call.from_user.id
    if user_id not in BOT_CONFIG['admin_ids']:
        _bot.answer_callback_query(call.id, get_text(user_id, 'errors.no_access'))
        return
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton(get_text(user_id, 'payment.new_card'), callback_data="new_card"),
        types.InlineKeyboardButton(get_text(user_id, 'payment.check_card_info'), callback_data="check_card_info"),
        types.InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="admin_panel"))
    _bot.edit_message_text(get_text(user_id, 'payment.card_management'), call.message.chat.id, call.message.message_id,
                           reply_markup=keyboard)


@router.callback('new_card')
def handle_new_card(call):
    if call.from_user.id not in BOT_CONFIG['admin_ids']:
        _bot.answer_callback_query(call.id, "⛔️ Access denied")
        return
    msg = _bot.edit_message_text("💳 Please enter card number:\nExample: 6037-9974-1234-5678",
                                  call.message.chat.id, call.message.message_id)
    _bot.register_next_step_handler(msg, process_card_number)


def process_card_number(message):
    if message.from_user.id not in BOT_CONFIG['admin_ids']:
        return
    card_number = message.text.strip().replace('-', '').replace(' ', '')
    if not card_number.isdigit() or len(card_number) != 16:
        msg = _bot.reply_to(message, "❌ Invalid card number.")
        _bot.register_next_step_handler(msg, process_card_number)
        return
    _get_repo().set_card_info(card_number, '')
    msg = _bot.reply_to(message, "✅ Card number saved.\n\n👤 Please enter cardholder name:")
    _bot.register_next_step_handler(msg, process_card_holder)


def process_card_holder(message):
    if message.from_user.id not in BOT_CONFIG['admin_ids']:
        return
    card_holder = message.text.strip()
    if len(card_holder) < 3:
        msg = _bot.reply_to(message, "❌ Invalid cardholder name.")
        _bot.register_next_step_handler(msg, process_card_holder)
        return
    card_info = _get_repo().get_card_info()
    if card_info:
        _get_repo().set_card_info(card_info['card_number'], card_holder)
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_panel"))
    _bot.reply_to(message,
                  f"✅ Card info saved:\n\n💳 Card: <code>{card_info['card_number'] if card_info else '...'}</code>\n👤 Holder: <code>{card_holder}</code>",
                  reply_markup=keyboard, parse_mode='HTML')


@router.callback('check_card_info')
def check_card_info(call):
    if call.from_user.id not in BOT_CONFIG['admin_ids']:
        _bot.answer_callback_query(call.id, "⛔️ Access denied")
        return
    card_info = _get_repo().get_card_info()
    if card_info:
        _bot.answer_callback_query(call.id,
                                   f"Card Info:\nNumber: {card_info['card_number']}\nHolder: {card_info['card_holder']}",
                                   show_alert=True)
    else:
        _bot.answer_callback_query(call.id, "❌ No card info registered", show_alert=True)
