#!/usr/bin/env python3
"""
admin_bot.py — Standalone Admin Bot (Polling Mode)
─────────────────────────────────────────────────
Uses POLLING (no webhook/SSL/nginx needed).
Flask serves /ping for Docker health checks.
"""

import logging, sys, os, time, threading
import telebot
from flask import Flask, request

logging.basicConfig(stream=sys.stdout, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

_TOKEN = os.getenv('BOT_TOKEN', os.getenv('ADMIN_BOT_TOKEN', ''))
bot = telebot.TeleBot(_TOKEN)
app = Flask(__name__)

from bot.router import router
from bot.handlers.admin_bot import init as admin_bot_init
admin_bot_init(bot); router.register_with_bot(bot)
logger.info(f"✅ Admin handlers: {len(router._callback_handlers)} callback + {len(router._message_handlers)} cmd")

from web.health import health_bp; app.register_blueprint(health_bp)
from web.routes.admin_panel import admin_panel_bp; app.register_blueprint(admin_panel_bp)

@app.route('/')
def root(): return 'Admin Bot is running'
@app.route('/admin/start')
def admin_panel_link():
    token = os.getenv('ADMIN_API_TOKEN', '')
    if not token: return 'Admin panel not configured', 500
    web_url = os.getenv('WEBSITE_URL', os.getenv('WEBHOOK_URL', ''))
    return f'<a href="{web_url}/admin?token={token}">🔗 Open Admin Panel</a>'

if __name__ == '__main__':
    try:
        from database import setup_databases; setup_databases()
        logging.info("✅ DB"); from db.migrations import MigrationManager; MigrationManager().migrate()
        logging.info("✅ Migrations"); from services.provider_registry import provider_registry; from services.sms_service import HeroSMSProvider
        provider_registry.register(HeroSMSProvider(), 'HeroSMS', priority=1); provider_registry.load_from_db()
        logging.info("✅ Provider")
    except Exception as e: logging.critical(f"❌ Init: {e}", exc_info=True)

    try: bot.remove_webhook(); time.sleep(1); logging.info("✅ Webhook removed — polling mode")
    except: pass

    threading.Thread(target=lambda: bot.polling(none_stop=True, timeout=30), daemon=True).start()
    logging.info("🚀 Admin polling started — bot is LIVE")
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
