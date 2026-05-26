"""
bot/handlers/language.py — Language Handler
─────────────────────────────────────────────────
Handles /language command and language selection callbacks.
THIN handler — delegates to i18n module + UserService.
"""

import logging
from telebot import types
from bot.client import telegram_client
from bot.keyboards.main_keyboard import main_menu_keyboard
from services.user_service import UserService
from i18n import get_text, set_user_language, get_all_languages

logger = logging.getLogger(__name__)

_user_service = UserService()


def register_language_handlers(bot):
    """Register language-related handlers with a telebot instance."""

    @bot.message_handler(commands=['language'])
    def handle_language_command(message):
        user_id = message.from_user.id

        keyboard = types.InlineKeyboardMarkup(row_width=1)
        for lang in get_all_languages():
            keyboard.add(types.InlineKeyboardButton(
                lang['name'],
                callback_data=f"setlang_{lang['code']}"
            ))
        keyboard.add(types.InlineKeyboardButton(
            get_text(user_id, 'navigation.back_to_main'),
            callback_data="back_to_main"
        ))

        telegram_client.send(
            message.chat.id,
            get_text(user_id, 'language.select_title'),
            reply_markup=keyboard
        )

    @bot.callback_query_handler(func=lambda call: call.data.startswith('setlang_'))
    def handle_language_selection(call):
        user_id = call.from_user.id
        lang_code = call.data.split('_')[1]

        if set_user_language(user_id, lang_code):
            telegram_client.answer_callback(call, get_text(user_id, 'language.selected'))
            telegram_client.edit(
                call.message.chat.id,
                call.message.message_id,
                get_text(user_id, 'welcome_back'),
                reply_markup=main_menu_keyboard(user_id)
            )
        else:
            telegram_client.answer_callback(call, get_text(user_id, 'errors.general_short'))

    logger.info("Registered: language handlers")