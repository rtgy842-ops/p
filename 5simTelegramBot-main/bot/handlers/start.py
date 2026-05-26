"""
bot/handlers/start.py — /start Handler
─────────────────────────────────────────────────
Welcomes users, shows main menu.
THIN handler — delegates to UserService, uses keyboard builders.
"""

import logging
from bot.client import telegram_client
from bot.keyboards.main_keyboard import main_menu_keyboard
from services.user_service import UserService
from i18n import get_text

logger = logging.getLogger(__name__)

_user_service = UserService()


def register_start_handler(bot):
    """Register the /start command handler with a telebot instance."""

    @bot.message_handler(commands=['start'])
    def handle_start(message):
        user_id = message.from_user.id

        # Ensure user exists
        _user_service.get_or_create(user_id)

        # Build welcome message and keyboard
        welcome_text = get_text(user_id, 'welcome')
        keyboard = main_menu_keyboard(user_id)

        telegram_client.send(message.chat.id, welcome_text, reply_markup=keyboard)

    logger.info("Registered: /start handler")


# For use with router:
def handle_start_message(message):
    """Handle /start via router."""
    user_id = message.from_user.id
    _user_service.get_or_create(user_id)
    welcome_text = get_text(user_id, 'welcome')
    keyboard = main_menu_keyboard(user_id)
    telegram_client.send(message.chat.id, welcome_text, reply_markup=keyboard)
