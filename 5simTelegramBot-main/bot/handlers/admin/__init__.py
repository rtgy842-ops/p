"""
bot/handlers/admin/__init__.py — Admin Handlers Package
─────────────────────────────────────────────────────────
init_bot for all admin sub-modules.
"""

import logging

logger = logging.getLogger(__name__)


def init(bot_instance):
    """Initialize all admin handler modules with the bot instance."""
    from bot.handlers.admin import (
        broadcast,
        channels,
        dashboard,
        operators,
        settings,
        stats,
        transactions,
        users,
    )

    dashboard.init(bot_instance)
    stats.init(bot_instance)
    settings.init(bot_instance)
    users.init(bot_instance)
    broadcast.init(bot_instance)
    transactions.init(bot_instance)
    channels.init(bot_instance)
    operators.init(bot_instance)
    logger.info("All admin handler modules initialized")
