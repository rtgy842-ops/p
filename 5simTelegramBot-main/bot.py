# ═══════════════════════════════════════════════════════════════
# bot.py — Enterprise Customer Bot (Docker-Optimized)
# ═══════════════════════════════════════════════════════════════
# Customer Bot ONLY — NO admin capabilities.
# Uses polling mode inside Docker (webhook set externally or via Nginx).
# ═══════════════════════════════════════════════════════════════

import logging
import time
import os
import sys
import json
from flask import Flask, request, render_template

import telebot
from telebot import types

from config import BOT_CONFIG, validate_secrets
from i18n import get_text, get_user_language, set_user_language, get_all_languages
from routes.order_details import order_details_bp
from web.health import health_bp

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# Flask + Blueprints
# ═══════════════════════════════════════════════════════════════
bot = telebot.TeleBot(BOT_CONFIG['token'])
app = Flask(__name__, static_folder='static', template_folder='templates')
app.register_blueprint(order_details_bp)
app.register_blueprint(health_bp)

# ═══════════════════════════════════════════════════════════════
# Logging
# ═══════════════════════════════════════════════════════════════
logging.basicConfig(stream=sys.stdout, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ═══════════════════════════════════════════════════════════════
# Register CUSTOMER-ONLY handler modules via Router
# ═══════════════════════════════════════════════════════════════
from bot.router import router
from bot.handlers import menu, payment, membership, purchase

menu.init(bot)
payment.init(bot)
membership.init(bot)
purchase.init(bot)
router.register_with_bot(bot)
logger.info("✅ Customer bot handlers registered")


# ── /start ─────────────────────────────────────────────────
@bot.message_handler(commands=['start'])
def start_handler(message):
    try:
        user_id = message.from_user.id
        from db.repositories.user_repository import UserRepository
        UserRepository().create_if_not_exists(user_id, 'fa')
        from bot.keyboards.main_keyboard import main_menu_keyboard
        bot.send_message(message.chat.id, get_text(user_id, 'welcome'),
                         reply_markup=main_menu_keyboard(user_id))
    except Exception as e:
        logger.error(f"Error in /start: {e}", exc_info=True)


# ── /language ──────────────────────────────────────────────
@bot.message_handler(commands=['language'])
def language_handler(message):
    user_id = message.from_user.id
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    for lang in get_all_languages():
        keyboard.add(types.InlineKeyboardButton(lang['name'], callback_data=f"setlang_{lang['code']}"))
    keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_main'), callback_data="back_to_main"))
    bot.send_message(message.chat.id, get_text(user_id, 'language.select_title'), reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data == 'language_menu')
def language_menu_handler(call):
    user_id = call.from_user.id
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    for lang in get_all_languages():
        keyboard.add(types.InlineKeyboardButton(lang['name'], callback_data=f"setlang_{lang['code']}"))
    keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_main'), callback_data="back_to_main"))
    bot.edit_message_text(get_text(user_id, 'language.select_title'), call.message.chat.id,
                          call.message.message_id, reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith('setlang_'))
def handle_language_selection(call):
    user_id = call.from_user.id
    lang_code = call.data.split('_')[1]
    if set_user_language(user_id, lang_code):
        from bot.keyboards.main_keyboard import main_menu_keyboard
        bot.answer_callback_query(call.id, get_text(user_id, 'language.selected'))
        bot.edit_message_text(get_text(user_id, 'welcome_back'), call.message.chat.id,
                              call.message.message_id, reply_markup=main_menu_keyboard(user_id))

@bot.callback_query_handler(func=lambda call: call.data == "back_to_main")
def back_to_main(call):
    from bot.keyboards.main_keyboard import main_menu_keyboard
    bot.edit_message_text(get_text(call.from_user.id, 'welcome_back'), call.message.chat.id,
                          call.message.message_id, reply_markup=main_menu_keyboard(call.from_user.id))


# ── Webhook endpoint ───────────────────────────────────────
@app.route('/', methods=['GET', 'POST'])
def webhook():
    if request.method == 'POST':
        try:
            json_str = request.get_data().decode('UTF-8')
            update = telebot.types.Update.de_json(json_str)
            bot.process_new_updates([update])
            return ''
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            return 'error', 500
    return 'OK'


@app.route('/verify/<user_id>/<amount>')
def verify_payment(user_id, amount):
    try:
        from compat.legacy_facade import payment_verify_zarinpal, add_balance
        authority = request.args.get('Authority')
        status = request.args.get('Status')
        if status != 'OK':
            return render_template('payment_result.html', success=False, message="Payment cancelled")
        success, ref_id = payment_verify_zarinpal(authority, int(amount))
        if success:
            new_balance = add_balance(int(user_id), int(amount), description='ZarinPal charge', ref_id=ref_id)
            if new_balance is not None:
                try: bot.send_message(int(user_id), f"✅ Payment successful!\n\n💰 {int(amount):,} T\n🔢 {ref_id or '---'}\n💎 {new_balance:,} T")
                except: pass
                return render_template('payment_result.html', success=True,
                                       amount=f"{int(amount):,}", ref_id=ref_id or '---', balance=f"{new_balance:,}")
        return render_template('payment_result.html', success=False, message="Verification failed")
    except Exception as e:
        logger.error(f"Verify error: {e}")
        return render_template('payment_result.html', success=False, message="Error")


# ═══════════════════════════════════════════════════════════════
# STARTUP — Resilient (no fatal exits)
# ═══════════════════════════════════════════════════════════════
if __name__ == '__main__':
    try:
        validate_secrets()
        logging.info("✅ Secrets validated")

        from database import setup_databases
        setup_databases()
        logging.info("✅ DB initialized")

        from db.migrations import MigrationManager
        MigrationManager().migrate()
        logging.info("✅ Migrations done")

        from services.provider_registry import provider_registry
        from services.sms_service import HeroSMSProvider
        provider_registry.register(HeroSMSProvider(), 'HeroSMS', priority=1)
        provider_registry.load_from_db()
        logging.info("✅ Provider ready")

        # Try webhook, fall back to polling
        try:
            bot.remove_webhook()
            time.sleep(1)
            bot.set_webhook(url=BOT_CONFIG['webhook_url'])
            logging.info(f"✅ Webhook: {BOT_CONFIG['webhook_url']}")
        except Exception:
            logging.warning("⚠️ Webhook failed — using polling mode (fine for Docker)")
            import threading
            threading.Thread(target=bot.polling, kwargs={'none_stop': True}, daemon=True).start()

        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

    except Exception as e:
        logging.critical(f"❌ Fatal: {e}", exc_info=True)
        # Don't exit — stay alive for Docker to show the error
        logging.warning("Bot staying alive despite error for diagnostics")
        while True:
            time.sleep(60)
