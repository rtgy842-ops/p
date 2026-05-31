"""
bot/handlers/help.py — Help / Info Handler
─────────────────────────────────────────────────
Handles help menu navigation and FAQ answers.
THIN handler — only constructs keyboards and displays text.
"""

import logging

from telebot import types

from bot.client import telegram_client
from i18n import get_text

logger = logging.getLogger(__name__)


def register_help_handlers(bot):
    """Register help-related handlers with a telebot instance."""

    @bot.callback_query_handler(func=lambda call: call.data in [
        'help', 'help_buy_number', 'help_charge', 'help_get_code',
        'help_payment', 'help_delivery', 'help_cancel'
    ])
    def handle_help_menu(call):
        user_id = call.from_user.id
        data = call.data

        if data == 'help':
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
            telegram_client.edit(
                call.message.chat.id, call.message.message_id,
                get_text(user_id, 'help.title'),
                reply_markup=keyboard
            )
            return

        # Map callback data to answer keys
        answer_map = {
            'help_buy_number': 'help.buy_number_answer',
            'help_charge': 'help.charge_answer',
            'help_get_code': 'help.get_code_answer',
            'help_payment': 'help.payment_methods_answer',
            'help_delivery': 'help.delivery_time_answer',
            'help_cancel': 'help.cancel_order_answer',
        }

        answer_key = answer_map.get(data)
        if answer_key:
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton(
                get_text(user_id, 'navigation.back_to_help'), callback_data="help"
            ))
            telegram_client.edit(
                call.message.chat.id, call.message.message_id,
                get_text(user_id, answer_key),
                reply_markup=keyboard
            )

    logger.info("Registered: help handlers")
