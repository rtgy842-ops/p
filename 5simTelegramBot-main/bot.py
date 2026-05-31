#!/usr/bin/env python3
"""
bot.py — Customer Bot (WEBHOOK mode — receives updates via POST /)
"""
import logging
import os
import secrets as _secrets
import sys

import telebot
from flask import Flask, render_template, request

from config import BOT_CONFIG
from routes.order_details import order_details_bp
from web.health import health_bp

logger = logging.getLogger(__name__)
bot = telebot.TeleBot(BOT_CONFIG['token'])
app = Flask(__name__, static_folder='static', template_folder='templates')
app.register_blueprint(order_details_bp); app.register_blueprint(health_bp)
logging.basicConfig(stream=sys.stdout, format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# ── WEBHOOK: Register the blueprint that handles POST / from Telegram ──
from web.routes.webhook import init as webhook_init
from web.routes.webhook import webhook_bp

webhook_init(bot)
app.register_blueprint(webhook_bp)
logger.info("Webhook blueprint registered — POST / ready for Telegram updates")

from bot.handlers import membership, menu, payment, purchase, referrals, start, subscriptions
from bot.router import router

menu.init(bot); payment.init(bot); membership.init(bot); purchase.init(bot); start.register_start_handler(bot)
referrals.init(bot); subscriptions.init(bot)
router.register_with_bot(bot)
logger.info(f"Handlers: {len(router._callback_handlers)} cb + {len(router._message_handlers)} cmd")

# /start registered via bot/handlers/start.py
# /language registered via bot/handlers/language.py
# back_to_main registered via bot/handlers/purchase.py
# No duplicate handlers needed here.

# ── In-memory CSRF state store (production should use Redis) ──
import time as _time

_payment_states: dict[str, dict] = {}  # state_token -> {user_id, amount, created_at}

def _generate_payment_state(user_id: int, amount: int) -> str:
    """Generate a CSRF state token for payment verification."""
    token = _secrets.token_hex(32)
    _payment_states[token] = {'user_id': user_id, 'amount': amount, 'created_at': _time.time()}
    # Cleanup expired tokens (>30 min old)
    now = _time.time()
    expired = [k for k, v in _payment_states.items() if now - v['created_at'] > 1800]
    for k in expired:
        _payment_states.pop(k, None)
    return token

@app.route('/verify/<user_id>/<amount>')
def verify_payment(user_id, amount):
    """Verify ZarinPal payment and credit user. Uses atomic PaymentService with CSRF protection."""
    from data.dto import PaymentGateway
    from services.payment_service import PaymentService
    a = request.args.get('Authority')
    s = request.args.get('Status')
    state = request.args.get('state', '')
    if s != 'OK':
        return render_template('payment_result.html', False, message="Payment cancelled by user")

    # ── CSRF Protection: Validate state token ──
    stored = _payment_states.pop(state, None)
    if stored is None:
        logging.getLogger(__name__).warning(f"Payment CSRF: invalid/missing state token for user {user_id}")
        return render_template('payment_result.html', False, message="Invalid or expired session. Please try again.")
    if stored['user_id'] != int(user_id) or stored['amount'] != int(amount):
        logging.getLogger(__name__).warning(f"Payment CSRF: state mismatch for user {user_id}")
        return render_template('payment_result.html', False, message="Session mismatch. Please try again.")

    try:
        uid = int(user_id)
        amt = int(amount)
        payment_svc = PaymentService()
        result = payment_svc.verify_and_credit(PaymentGateway.ZARINPAL, a, uid, amt)
        if result.success:
            balance = result.new_balance
            return render_template('payment_result.html', True,
                                   amount=f"{amt:,}", ref_id=result.ref_id or '---',
                                   balance=f"{balance:,}" if balance is not None else "?")
        return render_template('payment_result.html', False,
                               message=result.error_message or "Verification failed")
    except Exception as e:
        logging.getLogger(__name__).error(f"Payment verify error: {e}")
        return render_template('payment_result.html', False, message="Internal error")

if __name__ == '__main__':
    from database import setup_databases; setup_databases(); logger.info("DB ready")
    from db.migrations import MigrationManager; MigrationManager().migrate(); logger.info("Migrations done")
    from services.provider_registry import provider_registry
    from services.sms_service import HeroSMSProvider
    provider_registry.register(HeroSMSProvider(), 'HeroSMS', priority=1); provider_registry.load_from_db()

    # Webhook is set EXTERNALLY — just run Flask to receive updates
    logger.info("Customer Bot LIVE (webhook mode — no polling)")

    port = int(os.getenv('FLASK_PORT', '5000'))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
