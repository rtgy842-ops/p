# ═══════════════════════════════════════════════════════════════
# bot.py — Enterprise Customer Bot (WEBHOOK MODE — no polling)
# ═══════════════════════════════════════════════════════════════
# Webhook is set EXTERNALLY via curl. Flask receives POST at /.
# DO NOT call remove_webhook() or polling — that causes 409.
# ═══════════════════════════════════════════════════════════════

import logging, time, os, sys, json
from flask import Flask, request, render_template
import telebot
from telebot import types
from config import BOT_CONFIG, validate_secrets
from i18n import get_text, get_user_language, set_user_language, get_all_languages
from routes.order_details import order_details_bp
from web.health import health_bp

logger = logging.getLogger(__name__)
bot = telebot.TeleBot(BOT_CONFIG['token'])
app = Flask(__name__, static_folder='static', template_folder='templates')
app.register_blueprint(order_details_bp); app.register_blueprint(health_bp)
logging.basicConfig(stream=sys.stdout, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

from bot.router import router
from bot.handlers import menu, payment, membership, purchase
menu.init(bot); payment.init(bot); membership.init(bot); purchase.init(bot)
router.register_with_bot(bot)
logger.info(f"✅ {len(router._callback_handlers)} cb + {len(router._message_handlers)} cmd handlers")

@bot.message_handler(commands=['start'])
def start_handler(message):
    try:
        from db.repositories.user_repository import UserRepository
        UserRepository().create_if_not_exists(message.from_user.id, 'fa')
        from bot.keyboards.main_keyboard import main_menu_keyboard
        bot.send_message(message.chat.id, get_text(message.from_user.id, 'welcome'), reply_markup=main_menu_keyboard(message.from_user.id))
    except Exception as e: logger.error(f"/start: {e}")

@bot.message_handler(commands=['language'])
def language_handler(message):
    uid=message.from_user.id; kb=types.InlineKeyboardMarkup(row_width=1)
    for lang in get_all_languages(): kb.add(types.InlineKeyboardButton(lang['name'], callback_data=f"setlang_{lang['code']}"))
    kb.add(types.InlineKeyboardButton(get_text(uid,'navigation.back_to_main'), callback_data="back_to_main"))
    bot.send_message(uid, get_text(uid,'language.select_title'), reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == 'back_to_main')
def back_main_cb(c):
    from bot.keyboards.main_keyboard import main_menu_keyboard
    bot.edit_message_text(get_text(c.from_user.id,'welcome_back'), c.message.chat.id, c.message.message_id, reply_markup=main_menu_keyboard(c.from_user.id))

@app.route('/', methods=['POST'])
def telegram_webhook():
    try:
        update = telebot.types.Update.de_json(request.get_data().decode('UTF-8'))
        bot.process_new_updates([update])
        return ''
    except Exception as e:
        logger.error(f"Webhook: {e}")
        return 'error', 500

@app.route('/verify/<user_id>/<amount>')
def verify_payment(user_id, amount):
    try:
        from compat.legacy_facade import payment_verify_zarinpal, add_balance
        a=request.args.get('Authority'); s=request.args.get('Status')
        if s!='OK': return render_template('payment_result.html', False, message="Cancelled")
        ok,ref=payment_verify_zarinpal(a,int(amount))
        if ok:
            nb=add_balance(int(user_id),int(amount),description='ZarinPal',ref_id=ref)
            return render_template('payment_result.html', True, amount=f"{int(amount):,}", ref_id=ref or '---', balance=f"{nb:,}" if nb else "?")
        return render_template('payment_result.html', False, message="Verification failed")
    except Exception as e: logger.error(f"Verify: {e}"); return render_template('payment_result.html', False, message="Error")

if __name__ == '__main__':
    try:
        validate_secrets()
        from database import setup_databases; setup_databases(); logging.info("✅ DB")
        from db.migrations import MigrationManager; MigrationManager().migrate(); logging.info("✅ Migrations")
        from services.provider_registry import provider_registry; from services.sms_service import HeroSMSProvider
        provider_registry.register(HeroSMSProvider(), 'HeroSMS', priority=1); provider_registry.load_from_db()
        logging.info("✅ Provider")
    except Exception as e: logging.critical(f"❌ Init: {e}", exc_info=True)

    logging.info("🌐 Webhook mode — ready to receive updates")
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
