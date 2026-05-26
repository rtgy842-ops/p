"""
bot/error_handler.py — Centralized Exception Handling
─────────────────────────────────────────────────
Catches ALL unhandled exceptions from handlers.
Prevents single handler failure from crashing the entire bot.
"""

import logging
import traceback
from bot.client import telegram_client

logger = logging.getLogger(__name__)


class ErrorBoundary:
    """
    Decorator that wraps any handler with exception protection.
    If the handler raises, the user gets a friendly error,
    the bot continues running, and the error is logged.
    """

    @staticmethod
    def protect(handler_func):
        """Wrap a handler function with error protection."""
        def wrapper(*args, **kwargs):
            try:
                return handler_func(*args, **kwargs)
            except Exception as e:
                logger.error(
                    f"Unhandled error in {handler_func.__name__}: {e}\n"
                    f"{traceback.format_exc()}"
                )
                # Try to notify the user
                try:
                    call = args[0] if args else None
                    if call and hasattr(call, 'message'):
                        telegram_client.send(
                            call.message.chat.id,
                            "❌ An unexpected error occurred. Please try again."
                        )
                    elif call and hasattr(call, 'id'):
                        telegram_client.answer_callback(
                            call, "❌ An unexpected error occurred."
                        )
                except Exception:
                    pass
                return None
        return wrapper


# ── Global error boundary instance ─────────────────────────────
error_boundary = ErrorBoundary()