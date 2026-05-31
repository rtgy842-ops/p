#!/usr/bin/env python3
"""
admin_bot.py — Admin Bot (WEBHOOK mode — receives updates via POST /)
"""
import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

import telebot
from flask import Flask

logging.basicConfig(stream=sys.stdout, format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

_TOKEN = os.getenv('ADMIN_BOT_TOKEN', '')
if not _TOKEN:
    raise RuntimeError("ADMIN_BOT_TOKEN is required. Admin bot must use a separate token from BOT_TOKEN.")
bot = telebot.TeleBot(_TOKEN)
app = Flask(__name__)

from bot.handlers.admin_bot import init as admin_bot_init
from bot.router import router

admin_bot_init(bot); router.register_with_bot(bot)
logger.info(f"Admin handlers: {len(router._callback_handlers)} cb + {len(router._message_handlers)} cmd")

from web.health import health_bp; app.register_blueprint(health_bp)
from web.routes.admin_panel import admin_panel_bp; app.register_blueprint(admin_panel_bp)

# ── WEBHOOK: Register the blueprint that handles POST / from Telegram ──
from web.routes.webhook import init as webhook_init
from web.routes.webhook import webhook_bp

webhook_init(bot)
app.register_blueprint(webhook_bp)
logger.info("Webhook blueprint registered — POST / ready for Telegram admin updates")

@app.route('/')
def root(): return 'Admin Bot is running'
@app.route('/admin/start')
def link():
    t=os.getenv('ADMIN_API_TOKEN',''); w=os.getenv('WEBSITE_URL',os.getenv('WEBHOOK_URL',''))
    return f'<a href="{w}/admin?token={t}">🔗 Admin Panel</a>' if t else 'Not configured'

if __name__ == '__main__':
    from database import setup_databases; setup_databases(); logger.info("DB ready")
    from db.migrations import MigrationManager; MigrationManager().migrate(); logger.info("Migrations done")
    from services.provider_registry import provider_registry
    from services.sms_service import HeroSMSProvider
    provider_registry.register(HeroSMSProvider(), 'HeroSMS', priority=1); provider_registry.load_from_db()

    # Webhook is set EXTERNALLY — just run Flask to receive updates
    logger.info("Admin Bot LIVE (webhook mode — no polling)")

    port = int(os.getenv('FLASK_PORT', '5000'))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
