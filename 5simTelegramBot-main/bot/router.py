"""
bot/router.py — Router System (Fixed: exact-match first)
─────────────────────────────────────────────────
Registers handlers in a structured, modular way.
Each handler module registers itself via a Router.

FIX: Exact-match patterns are tried BEFORE prefix patterns.
     This prevents 'buy_number' from matching 'buy_number_telegram_...'
"""

import logging

from bot.error_handler import error_boundary
from bot.middleware import default_pipeline

logger = logging.getLogger(__name__)


class Router:
    """Central router that collects handlers from all modules."""

    def __init__(self):
        self._message_handlers: list[tuple[str, callable]] = []
        self._callback_handlers: list[tuple[str, callable]] = []

    def callback(self, data_pattern: str):
        """Decorator to register a callback query handler."""
        def decorator(func):
            protected = error_boundary.protect(func)
            def wrapped(call):
                if default_pipeline.process(call):
                    return protected(call)
                return None
            self._callback_handlers.append((data_pattern, wrapped))
            logger.info(f"Registered callback handler: {data_pattern} -> {func.__name__}")
            return wrapped
        return decorator

    def command(self, command: str):
        """Decorator to register a message command handler."""
        def decorator(func):
            protected = error_boundary.protect(func)
            def wrapped(message):
                if default_pipeline.process(message):
                    return protected(message)
                return None
            self._message_handlers.append((command, wrapped))
            logger.info(f"Registered command handler: /{command} -> {func.__name__}")
            return wrapped
        return decorator

    def route_callback(self, data: str, call):
        """
        Route a callback query to the matching handler.
        Exact matches first, then prefix matches.
        """
        # Step 1: Exact match
        for pattern, handler in self._callback_handlers:
            if data == pattern:
                return handler(call)
        # Step 2: Prefix match (for dynamic callbacks like buy_number_telegram_...)
        for pattern, handler in self._callback_handlers:
            if data.startswith(pattern):
                return handler(call)
        logger.debug(f"No handler for callback: {data[:80]}")
        return None

    def route_message(self, command: str, message):
        """Route a message command to the matching handler."""
        for pattern, handler in self._message_handlers:
            if command == pattern:
                return handler(message)
        return None

    def register_with_bot(self, bot):
        """Register all collected handlers with a telebot instance."""
        for pattern, handler in self._callback_handlers:
            @bot.callback_query_handler(func=lambda call, p=pattern: (
                call.data == p or call.data.startswith(p)
            ))
            def _callback_wrapper(call, h=handler):
                return h(call)

        for command, handler in self._message_handlers:
            @bot.message_handler(commands=[command])
            def _message_wrapper(message, h=handler):
                return h(message)

        logger.info(
            f"Router registered: {len(self._callback_handlers)} callback handlers, "
            f"{len(self._message_handlers)} command handlers"
        )

    def get_stats(self) -> dict:
        return {
            'callback_handlers': len(self._callback_handlers),
            'command_handlers': len(self._message_handlers),
            'callback_patterns': [p for p, _ in self._callback_handlers],
            'commands': [c for c, _ in self._message_handlers],
        }


router = Router()
