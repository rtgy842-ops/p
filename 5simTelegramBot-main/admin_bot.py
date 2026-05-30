#!/usr/bin/env python3
"""
admin_bot.py — Standalone Admin Bot (Webhook Mode)
─────────────────────────────────────────────────
Uses WEBHOOK set EXTERNALLY (via curl).
DO NOT call remove_webhook() or set_webhook() from here.
"""

import logging
import sys
import os
import time

import telebot
from flask import Flask, request

logging.basicConfig(
    stream=sys.stdout,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

_TOKEN = os.getenv('BOT_TOKEN', os.getenv('ADMIN_BOT_TOKEN', ''))

bot = telebot.TeleBot(_TOKEN)
app = Flask(__name__)

from bot.router import router
from bot.handlers.admin_bot import init as admin_bot_init

admin_bot_init(bot)
router.register_with_bot(bot)
logger.info("✅ Admin Bot handlers registered")

from web.health import health_bp
app.register_blueprint(health_bp)

from web.routes.admin_panel import admin_panel_bp
app.register_blueprint(admin_panel_bp)
logger.info("✅ Admin panel registered")


@app.route('/', methods=['POST'])
def admin_webhook():
    try:
        json_str = request.get_data().decode('UTF-8')
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return ''
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return 'error', 500


@app.route('/admin/start')
def admin_panel_link():
    token = os.getenv('ADMIN_API_TOKEN', '')
    if not token:
        return 'Admin panel not configured', 500
    web_url = os.getenv('WEBSITE_URL', os.getenv('WEBHOOK_URL', ''))
    return f'<a href="{web_url}/admin?token={token}">🔗 Open Admin Panel</a>'


if __name__ == '__main__':
    try:
        from database import setup_databases; setup_databases()
        logging.info("✅ DB initialized")
        from db.migrations import MigrationManager; MigrationManager().migrate()
        logging.info("✅ Migrations done")
        from services.provider_registry import provider_registry
        from services.sms_service import HeroSMSProvider
        provider_registry.register(HeroSMSProvider(), 'HeroSMS', priority=1)
        provider_registry.load_from_db()
        logging.info("✅ Provider ready")
    except Exception as e:
        logging.critical(f"❌ Init error: {e}", exc_info=True)

    logging.info("🌐 Admin Flask starting on port 5000 — ready for webhook updates")
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
