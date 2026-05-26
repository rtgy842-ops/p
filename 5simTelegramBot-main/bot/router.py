"""
bot/router.py — Router System
─────────────────────────────────────────────────
Registers handlers in a structured, modular way.
Each handler module registers itself via a Router.

Usage (in handler module):
    from bot.router import router
    
    @router.callback('buy_number')
    def handle_buy_number(call):
        ...
    
    @router.command('start')
    def handle_start(message):
        ...
"""

import logging
from bot.error_handler import error_boundary
from bot.middleware import default_pipeline

logger = logging.getLogger(__name__)


class Router:
    """
    Central router that collects handlers from all modules.
    Each handler is wrapped with middleware + error protection.
    """

    def __init__(self):
        self._message_handlers: list[tuple[str, callable]] = []
        self._callback_handlers: list[tuple[str, callable]] = []

    def callback(self, data_pattern: str):
        """
        Decorator to register a callback query handler.
        
        Example:
            @router.callback('buy_number')
            def on_buy_number(call): ...
        """
        def decorator(func):
            protected = error_boundary.protect(func)
            
            def wrapped(call):
                if default_pipeline.process(call):
                    return protected(call)
                return None

            self._callback_handlers.append((data_pattern, wrapped))
            logger.info(f"Registered callback handler: {data_pattern} → {func.__name__}")
            return wrapped
        return decorator

    def command(self, command: str):
        """
        Decorator to register a message command handler.
        
        Example:
            @router.command('start')
            def on_start(message): ...
        """
        def decorator(func):
            protected = error_boundary.protect(func)

            def wrapped(message):
                if default_pipeline.process(message):
                    return protected(message)
                return None

            self._message_handlers.append((command, wrapped))
            logger.info(f"Registered command handler: /{command} → {func.__name__}")
            return wrapped
        return decorator

    def route_callback(self, data: str, call):
        """
        Route a callback query to the matching handler.
        Called from bot.py's main callback handler.
        """
        for pattern, handler in self._callback_handlers:
            if data == pattern or data.startswith(pattern):
                return handler(call)
        logger.debug(f"No handler for callback: {data[:80]}")
        return None

    def route_message(self, command: str, message):
        """
        Route a message command to the matching handler.
        Called from bot.py's main message handler.
        """
        for pattern, handler in self._message_handlers:
            if command == pattern:
                return handler(message)
        return None

    def register_with_bot(self, bot):
        """
        Register all collected handlers with a telebot instance.
        This wires up the actual Telegram event handlers.
        """
        # Register callback handlers
        for pattern, handler in self._callback_handlers:
            @bot.callback_query_handler(func=lambda call, p=pattern: (
                call.data == p or call.data.startswith(p)
            ))
            def _callback_wrapper(call, h=handler):
                return h(call)

        # Register message handlers
        for command, handler in self._message_handlers:
            @bot.message_handler(commands=[command])
            def _message_wrapper(message, h=handler):
                return h(message)

        logger.info(
            f"Router registered: {len(self._callback_handlers)} callback handlers, "
            f"{len(self._message_handlers)} command handlers"
        )

    def get_stats(self) -> dict:
        """Return router statistics."""
        return {
            'callback_handlers': len(self._callback_handlers),
            'command_handlers': len(self._message_handlers),
            'callback_patterns': [p for p, _ in self._callback_handlers],
            'commands': [c for c, _ in self._message_handlers],
        }


# ── Global router instance ─────────────────────────────────────
router = Router()