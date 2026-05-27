"""
bot/handlers/admin/__init__.py — Admin Handlers Package
─────────────────────────────────────────────────────────
init_bot for all admin sub-modules.
"""

import logging
logger = logging.getLogger(__name__)


def init(bot_instance):
    """Initialize all admin handler modules with the bot instance."""
    from bot.handlers.admin import dashboard
    from bot.handlers.admin import stats
    from bot.handlers.admin import settings
    from bot.handlers.admin import users
    from bot.handlers.admin import broadcast
    from bot.handlers.admin import transactions
    from bot.handlers.admin import channels
    from bot.handlers.admin import operators

    dashboard.init(bot_instance)
    stats.init(bot_instance)
    settings.init(bot_instance)
    users.init(bot_instance)
    broadcast.init(bot_instance)
    transactions.init(bot_instance)
    channels.init(bot_instance)
    operators.init(bot_instance)
    logger.info("All admin handler modules initialized")