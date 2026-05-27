"""
bot/handlers/menu.py — Main Menu & Navigation Handlers
───────────────────────────────────────────────────────
back_to_main, check_balance, buy_number entry, help section.
"""

import logging
from bot.router import router
from i18n import get_text
from config import BOT_CONFIG

logger = logging.getLogger(__name__)

# ── Lazy bot reference (injected at registration time) ─────────
_bot = None


def init(bot_instance):
    global _bot
    _bot = bot_instance


@router.callback('back_to_main')
def back_to_main_menu(call):
    from bot.keyboards.main_keyboard import inline_main_keyboard
    _bot.edit_message_text(
        get_text(call.from_user.id, 'welcome_back'),
        call.message.chat.id,
        call.message.message_id,
        reply_markup=inline_main_keyboard(call.from_user.id)
    )


@router.callback('check_balance')
def handle_check_balance(call):
    from telebot import types
    from compat.legacy_facade import get_balance as compat_get_balance
    from bot.keyboards.main_keyboard import inline_main_keyboard

    user_id = call.from_user.id
    balance = compat_get_balance(user_id)

    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        types.InlineKeyboardButton(get_text(user_id, 'main_menu.add_funds'), callback_data="add_funds"),
        types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_main'), callback_data="back_to_main")
    )

    _bot.edit_message_text(
        get_text(user_id, 'wallet.title', balance=balance),
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )


@router.callback('buy_number')
def handle_buy_number_entry(call):
    from bot.keyboards.main_keyboard import inline_main_keyboard
    user_id = call.from_user.id
    _bot.edit_message_text(
        get_text(user_id, 'services.select'),
        call.message.chat.id,
        call.message.message_id,
        reply_markup=inline_main_keyboard(user_id)
    )
    # Re-show services keyboard
    from bot.handlers.services import services_keyboard_wrapper
    _bot.edit_message_text(
        get_text(user_id, 'services.select'),
        call.message.chat.id,
        call.message.message_id,
        reply_markup=services_keyboard_wrapper(user_id)
    )


@router.callback('help')
def handle_help(call):
    from telebot import types
    user_id = call.from_user.id

    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton(get_text(user_id, 'help.buy_number'), callback_data="help_buy_number"),
        types.InlineKeyboardButton(get_text(user_id, 'help.charge'), callback_data="help_charge"),
        types.InlineKeyboardButton(get_text(user_id, 'help.get_code'), callback_data="help_get_code"),
        types.InlineKeyboardButton(get_text(user_id, 'help.payment_methods'), callback_data="help_payment"),
        types.InlineKeyboardButton(get_text(user_id, 'help.delivery_time'), callback_data="help_delivery"),
        types.InlineKeyboardButton(get_text(user_id, 'help.cancel_order'), callback_data="help_cancel"),
        types.InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="back_to_main")
    )
    _bot.edit_message_text(
        get_text(user_id, 'help.title'),
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard
    )


@router.callback('help_buy_number')
def help_buy_number(call):
    from telebot import types
    user_id = call.from_user.id
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_help'), callback_data="help"))
    _bot.edit_message_text(get_text(user_id, 'help.buy_number_answer'), call.message.chat.id, call.message.message_id, reply_markup=keyboard)


@router.callback('help_charge')
def help_charge(call):
    from telebot import types
    user_id = call.from_user.id
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_help'), callback_data="help"))
    _bot.edit_message_text(get_text(user_id, 'help.charge_answer'), call.message.chat.id, call.message.message_id, reply_markup=keyboard)


@router.callback('help_get_code')
def help_get_code(call):
    from telebot import types
    user_id = call.from_user.id
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_help'), callback_data="help"))
    _bot.edit_message_text(get_text(user_id, 'help.get_code_answer'), call.message.chat.id, call.message.message_id, reply_markup=keyboard)


@router.callback('help_payment')
def help_payment(call):
    from telebot import types
    user_id = call.from_user.id
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_help'), callback_data="help"))
    _bot.edit_message_text(get_text(user_id, 'help.payment_methods_answer'), call.message.chat.id, call.message.message_id, reply_markup=keyboard)


@router.callback('help_delivery')
def help_delivery(call):
    from telebot import types
    user_id = call.from_user.id
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_help'), callback_data="help"))
    _bot.edit_message_text(get_text(user_id, 'help.delivery_time_answer'), call.message.chat.id, call.message.message_id, reply_markup=keyboard)


@router.callback('help_cancel')
def help_cancel(call):
    from telebot import types
    user_id = call.from_user.id
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_help'), callback_data="help"))
    _bot.edit_message_text(get_text(user_id, 'help.cancel_order_answer'), call.message.chat.id, call.message.message_id, reply_markup=keyboard)