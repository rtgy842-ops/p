# ═══════════════════════════════════════════════════════════════
# bot.py — Enterprise Customer Bot (Polling Mode, 409-Safe)
# ═══════════════════════════════════════════════════════════════
import logging, time, os, sys, json, threading
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
logger.info(f"✅ {len(router._callback_handlers)} callback + {len(router._message_handlers)} cmd handlers")


@bot.message_handler(commands=['start'])
def start_handler(message):
    try:
        user_id = message.from_user.id
        from db.repositories.user_repository import UserRepository
        UserRepository().create_if_not_exists(user_id, 'fa')
        from bot.keyboards.main_keyboard import main_menu_keyboard
        bot.send_message(message.chat.id, get_text(user_id, 'welcome'), reply_markup=main_menu_keyboard(user_id))
    except Exception as e: logger.error(f"/start: {e}", exc_info=True)

@bot.message_handler(commands=['language'])
def language_handler(message):
    uid=message.from_user.id; kb=types.InlineKeyboardMarkup(row_width=1)
    for lang in get_all_languages(): kb.add(types.InlineKeyboardButton(lang['name'], callback_data=f"setlang_{lang['code']}"))
    kb.add(types.InlineKeyboardButton(get_text(uid,'navigation.back_to_main'), callback_data="back_to_main"))
    bot.send_message(message.chat.id, get_text(uid,'language.select_title'), reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == 'language_menu')
def lang_menu_cb(c):
    uid=c.from_user.id; kb=types.InlineKeyboardMarkup(row_width=1)
    for lang in get_all_languages(): kb.add(types.InlineKeyboardButton(lang['name'], callback_data=f"setlang_{lang['code']}"))
    kb.add(types.InlineKeyboardButton(get_text(uid,'navigation.back_to_main'), callback_data="back_to_main"))
    bot.edit_message_text(get_text(uid,'language.select_title'), c.message.chat.id, c.message.message_id, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith('setlang_'))
def setlang_cb(c):
    uid=c.from_user.id; lang=c.data.split('_')[1]
    if set_user_language(uid, lang):
        from bot.keyboards.main_keyboard import main_menu_keyboard
        bot.answer_callback_query(c.id, get_text(uid,'language.selected'))
        bot.edit_message_text(get_text(uid,'welcome_back'), c.message.chat.id, c.message.message_id, reply_markup=main_menu_keyboard(uid))

@bot.callback_query_handler(func=lambda c: c.data == "back_to_main")
def back_main_cb(c):
    from bot.keyboards.main_keyboard import main_menu_keyboard
    bot.edit_message_text(get_text(c.from_user.id,'welcome_back'), c.message.chat.id, c.message.message_id, reply_markup=main_menu_keyboard(c.from_user.id))

@app.route('/verify/<user_id>/<amount>')
def verify_payment(user_id, amount):
    try:
        from compat.legacy_facade import payment_verify_zarinpal, add_balance
        a=request.args.get('Authority'); s=request.args.get('Status')
        if s!='OK': return render_template('payment_result.html', success=False, message="Payment cancelled")
        ok,ref=payment_verify_zarinpal(a,int(amount))
        if ok:
            nb=add_balance(int(user_id), int(amount), description='ZarinPal charge', ref_id=ref)
            if nb is not None:
                try: bot.send_message(int(user_id), f"✅ Payment!\n💰 {int(amount):,} T\n💎 {nb:,} T")
                except: pass
                return render_template('payment_result.html', success=True, amount=f"{int(amount):,}", ref_id=ref or '---', balance=f"{nb:,}")
        return render_template('payment_result.html', success=False, message="Verification failed")
    except Exception as e: logger.error(f"Verify: {e}"); return render_template('payment_result.html', success=False, message="Error")


def start_polling():
    """Start polling with retry on 409 conflict."""
    # Force-delete webhook and wait for propagation
    for _ in range(5):
        try:
            bot.remove_webhook()
            time.sleep(2)
            break
        except Exception:
            time.sleep(2)

    logger.info("Starting polling loop...")
    while True:
        try:
            bot.polling(none_stop=False, timeout=30, long_polling_timeout=20)
        except Exception as e:
            msg = str(e)
            if '409' in msg or 'Conflict' in msg:
                logger.warning(f"409 conflict — waiting 5s then retrying...")
                time.sleep(5)
                # Force delete webhook again
                try: bot.remove_webhook()
                except: pass
                time.sleep(3)
                continue
            logger.error(f"Polling error: {e}")
            time.sleep(5)


# ═══════════════════════════════════════════════════════════════
if __name__ == '__main__':
    try:
        validate_secrets(); from database import setup_databases; setup_databases()
        logging.info("✅ DB"); from db.migrations import MigrationManager; MigrationManager().migrate()
        logging.info("✅ Migrations"); from services.provider_registry import provider_registry; from services.sms_service import HeroSMSProvider
        provider_registry.register(HeroSMSProvider(), 'HeroSMS', priority=1); provider_registry.load_from_db()
        logging.info("✅ Provider")
    except Exception as e: logging.critical(f"❌ Init: {e}", exc_info=True)

    threading.Thread(target=start_polling, daemon=True).start()
    logging.info("🚀 Customer Bot LIVE — polling mode")
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
