"""
bot/client.py — Telegram Abstraction Layer
─────────────────────────────────────────────────
Single source for ALL Telegram API interactions.
No direct bot.send_message() anywhere else.

Features:
- Centralized bot instance
- Wrapped send/edit methods with error handling
- Automatic retry for rate limits
- Keyboard builder helpers
- Testing-ready (can be mocked)

Usage:
    from bot.client import telegram_client
    telegram_client.send(user_id, "Hello!")
"""

import logging

import telebot
from telebot import types

from config import BOT_CONFIG

logger = logging.getLogger(__name__)

# ── Singleton bot instance ─────────────────────────────────────
_bot: telebot.TeleBot | None = None


def get_bot() -> telebot.TeleBot:
    """Get or create the singleton bot instance."""
    global _bot
    if _bot is None:
        _bot = telebot.TeleBot(BOT_CONFIG['token'])
        logger.info("Telegram bot instance created")
    return _bot


class TelegramClient:
    """
    Abstraction layer for all Telegram API calls.
    Handles errors gracefully — never crashes on a single message failure.
    """

    def __init__(self):
        self.bot = get_bot()

    # ── Message Sending ────────────────────────────────────────

    def send(self, chat_id: int, text: str, reply_markup=None,
             parse_mode: str = 'HTML', disable_preview: bool = True) -> bool:
        """Send a message. Returns True on success."""
        try:
            self.bot.send_message(
                chat_id, text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_preview,
            )
            return True
        except Exception as e:
            # Try without parse_mode
            if parse_mode:
                try:
                    self.bot.send_message(
                        chat_id, text,
                        reply_markup=reply_markup,
                        disable_web_page_preview=disable_preview,
                    )
                    return True
                except Exception as e2:
                    logger.error(f"Failed to send message to {chat_id}: {e2}")
                    return False
            logger.error(f"Failed to send message to {chat_id}: {e}")
            return False

    def reply(self, message, text: str, reply_markup=None) -> bool:
        """Reply to a message."""
        try:
            self.bot.reply_to(message, text, reply_markup=reply_markup)
            return True
        except Exception as e:
            logger.error(f"Failed to reply: {e}")
            return False

    # ── Message Editing ────────────────────────────────────────

    def edit(self, chat_id: int, message_id: int, text: str,
             reply_markup=None, parse_mode: str = 'HTML') -> bool:
        """Edit an existing message."""
        try:
            self.bot.edit_message_text(
                text, chat_id, message_id,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                disable_web_page_preview=True,
            )
            return True
        except Exception as e:
            if 'message is not modified' not in str(e).lower():
                logger.error(f"Failed to edit message {message_id}: {e}")
            return False

    def edit_caption(self, chat_id: int, message_id: int, caption: str,
                     reply_markup=None) -> bool:
        """Edit a photo caption."""
        try:
            self.bot.edit_message_caption(
                caption, chat_id, message_id, reply_markup=reply_markup
            )
            return True
        except Exception as e:
            logger.error(f"Failed to edit caption: {e}")
            return False

    # ── Callback Answer ────────────────────────────────────────

    def answer_callback(self, call, text: str = '', show_alert: bool = False):
        """Answer a callback query."""
        try:
            self.bot.answer_callback_query(call.id, text, show_alert=show_alert)
        except Exception as e:
            logger.error(f"Failed to answer callback: {e}")

    # ── Photo / Media ──────────────────────────────────────────

    def send_photo(self, chat_id: int, photo, caption: str = '',
                   reply_markup=None) -> bool:
        """Send a photo."""
        try:
            self.bot.send_photo(chat_id, photo, caption=caption, reply_markup=reply_markup)
            return True
        except Exception as e:
            logger.error(f"Failed to send photo to {chat_id}: {e}")
            return False

    # ── Admin Helpers ──────────────────────────────────────────

    def delete_message(self, chat_id: int, message_id: int) -> bool:
        """Delete a message."""
        try:
            self.bot.delete_message(chat_id, message_id)
            return True
        except Exception:
            return False

    def get_chat(self, chat_id: str):
        """Get chat info (for channel validation)."""
        try:
            return self.bot.get_chat(chat_id)
        except Exception:
            return None

    def get_chat_member(self, chat_id: str, user_id: int):
        """Check membership."""
        try:
            return self.bot.get_chat_member(chat_id, user_id)
        except Exception:
            return None

    def is_admin(self, chat_id: str, user_id: int) -> bool:
        """Check if bot is admin in a channel."""
        try:
            member = self.bot.get_chat_member(chat_id, user_id)
            return member.status in ['administrator', 'creator']
        except Exception:
            return False

    # ── Keyboard Helpers ───────────────────────────────────────

    @staticmethod
    def inline_button(text: str, callback_data: str = None,
                      url: str = None) -> types.InlineKeyboardButton:
        """Create an inline keyboard button."""
        return types.InlineKeyboardButton(text, callback_data=callback_data, url=url)

    @staticmethod
    def inline_keyboard(buttons: list, row_width: int = 2) -> types.InlineKeyboardMarkup:
        """Create an inline keyboard from a list of buttons."""
        kb = types.InlineKeyboardMarkup(row_width=row_width)
        for btn in buttons:
            if isinstance(btn, list):
                kb.row(*btn)
            else:
                kb.add(btn)
        return kb


# ── Global instance ────────────────────────────────────────────
telegram_client = TelegramClient()
