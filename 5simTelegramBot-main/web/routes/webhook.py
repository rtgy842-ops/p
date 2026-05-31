"""
web/routes/webhook.py — Telegram Webhook Blueprint
────────────────────────────────────────────────────
Receives Telegram updates and processes them.
"""

import logging

from flask import Blueprint, request

logger = logging.getLogger(__name__)

webhook_bp = Blueprint('webhook', __name__)

# Bot instance injected at registration
_bot = None


def init(bot_instance):
    global _bot
    _bot = bot_instance


@webhook_bp.route('/', methods=['GET', 'POST'])
def webhook():
    import telebot
    logger.info(f"Received webhook request: {request.method}")
    if request.method == 'POST':
        logger.info(f"Webhook data: {request.get_data()}")
        try:
            json_str = request.get_data().decode('UTF-8')
            update = telebot.types.Update.de_json(json_str)
            _bot.process_new_updates([update])
            return ''
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            return 'error', 500
    return 'OK'
