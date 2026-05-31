"""
web/routes/webhook.py — Telegram Webhook Blueprint (Security-Hardened)
────────────────────────────────────────────────────
Receives Telegram updates with secret-token authentication.
POST-only. Requires X-Telegram-Bot-Api-Secret-Token header.
"""

import logging
import os

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

webhook_bp = Blueprint('webhook', __name__)

# Bot instance injected at registration
_bot = None

# Load webhook secret token from environment (MUST be set in production)
_WEBHOOK_SECRET_TOKEN = os.getenv('WEBHOOK_SECRET_TOKEN', '')


def init(bot_instance):
    global _bot
    _bot = bot_instance

    if not _WEBHOOK_SECRET_TOKEN:
        logger.warning("WEBHOOK_SECRET_TOKEN is not set — webhook is UNSECURE")


def _verify_webhook_token() -> bool:
    """Verify the Telegram secret token header against the configured token."""
    import secrets as _secrets
    token = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
    if not _WEBHOOK_SECRET_TOKEN:
        # FAIL CLOSED in production. Only bypass in dev for testing.
        from config import IS_PRODUCTION
        if IS_PRODUCTION:
            logger.error("WEBHOOK_SECRET_TOKEN not set in production — rejecting request")
            return False
        return True
    return _secrets.compare_digest(token, _WEBHOOK_SECRET_TOKEN)


@webhook_bp.route('/', methods=['POST'])
def webhook():
    import telebot

    # ── Authentication: Verify secret token ──
    if not _verify_webhook_token():
        logger.warning("Webhook request rejected: invalid/missing secret token")
        return jsonify({'error': 'Forbidden'}), 403

    logger.info(f"Received webhook request: {request.method}")
    logger.debug(f"Webhook data: {request.get_data()}")
    try:
        json_str = request.get_data().decode('UTF-8')
        update = telebot.types.Update.de_json(json_str)
        _bot.process_new_updates([update])
        return ''
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return 'error', 500
