#!/usr/bin/env python3
"""
admin_bot.py — Standalone Admin Bot (Enterprise Entry Point)
─────────────────────────────────────────────────
COMPLETELY SEPARATE from Customer Bot (bot.py).
Requires ADMIN_BOT_TOKEN env var.
ZERO customer capabilities — admin operations only.
"""

import logging
import sys
import os

# Verify admin token is present
if not os.getenv('ADMIN_BOT_TOKEN'):
    print("❌ ADMIN_BOT_TOKEN not set. Admin Bot will NOT start.", file=sys.stderr)
    print("Set ADMIN_BOT_TOKEN in your .env file.", file=sys.stderr)
    sys.exit(0)

import telebot
from flask import Flask, request

from config import BOT_CONFIG

# Override token with admin-specific token
_ADMIN_TOKEN = os.getenv('ADMIN_BOT_TOKEN')

logging.basicConfig(
    stream=sys.stdout,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize
bot = telebot.TeleBot(_ADMIN_TOKEN)
app = Flask(__name__)

# Register admin handlers ONLY
from bot.router import router
from bot.handlers.admin_bot import init as admin_bot_init

admin_bot_init(bot)
router.register_with_bot(bot)
logger.info("✅ Admin Bot handlers registered")

# Register web blueprints
from web.health import health_bp
app.register_blueprint(health_bp)

@app.route('/', methods=['GET', 'POST'])
def admin_webhook():
    if request.method == 'POST':
        try:
            json_str = request.get_data().decode('UTF-8')
            update = telebot.types.Update.de_json(json_str)
            bot.process_new_updates([update])
            return ''
        except Exception as e:
            logger.error(f"Admin webhook error: {e}")
            return 'error', 500
    return 'Admin Bot is running'


@app.route('/admin/start')
def admin_panel_link():
    """Generate secure admin panel link."""
    token = os.getenv('ADMIN_API_TOKEN', '')
    if not token:
        return 'Admin panel not configured (set ADMIN_API_TOKEN)', 500
    return f'<a href="/admin?token={token}">Open Admin Panel</a>'


if __name__ == '__main__':
    try:
        from database import setup_databases
        setup_databases()
        logging.info("✅ Databases initialized")

        from db.migrations import MigrationManager
        mm = MigrationManager()
        if mm.migrate():
            logging.info("✅ Migrations applied")

        # Register provider in registry
        from services.provider_registry import provider_registry
        from services.sms_service import HeroSMSProvider
        provider_registry.register(HeroSMSProvider(), 'HeroSMS', priority=1)
        provider_registry.load_from_db()
        logging.info("✅ Provider registry initialized")

        bot.remove_webhook()
        import time
        time.sleep(0.5)
        webhook_url = os.getenv('ADMIN_WEBHOOK_URL', os.getenv('WEBHOOK_URL', ''))
        if webhook_url:
            bot.set_webhook(url=webhook_url + '/')
            logging.info(f"✅ Admin webhook set to {webhook_url}")

        app.run(host='0.0.0.0', port=5000, debug=False)

    except Exception as e:
        logging.error(f"❌ Fatal admin startup error: {e}", exc_info=True)
        sys.exit(1)