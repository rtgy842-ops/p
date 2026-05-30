"""
bot/handlers/menu.py — Main Menu & Navigation Handlers
───────────────────────────────────────────────────────
NOTE: Main handlers (back_to_main, check_balance, buy_number, help, help_*)
are now centralized in bot/handlers/purchase.py to avoid duplication.
This file exists only for backward compatibility.
"""

import logging
from bot.router import router

logger = logging.getLogger(__name__)
_bot = None


def init(bot_instance):
    global _bot
    _bot = bot_instance