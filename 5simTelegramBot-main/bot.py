# ═══════════════════════════════════════════════════════════════
# bot.py — Enterprise Telegram Bot (Post-Migration)
# ═══════════════════════════════════════════════════════════════
# Handlers are now in bot/handlers/ (registered via Router).
# Balance ops use WalletService; SMS ops use SMSService.
# No direct sqlite3.connect() anywhere.
# ═══════════════════════════════════════════════════════════════

import logging
import time
import os
import sys
import json
from flask import Flask, request, render_template

import telebot
from telebot import types

from config import BOT_CONFIG, HEROSMS_CONFIG, DB_CONFIG, PAYMENT_CONFIG, COUNTRY_ID_MAP, SERVICE_CODE_MAP
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
# Lazy admin_config (defers DB until after migrations)
# ═══════════════════════════════════════════════════════════════
_admin_config = None
def _get_admin_config():
    global _admin_config
    if _admin_config is None:
        from admin_config import AdminConfig
        _admin_config = AdminConfig()
    return _admin_config

# ═══════════════════════════════════════════════════════════════
# Register ALL handler modules via Router
# ═══════════════════════════════════════════════════════════════
from bot.router import router
from bot.handlers.admin import init as admin_init
from bot.handlers import menu, payment, membership, purchase

admin_init(bot)
menu.init(bot)
payment.init(bot)
membership.init(bot)
purchase.init(bot)
router.register_with_bot(bot)
logger.info("✅ All handler modules registered via Router")

# ═══════════════════════════════════════════════════════════════
# Core Inline Handlers (not in bot/handlers/)
# ═══════════════════════════════════════════════════════════════

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
        bot.reply_to(message, get_text(message.from_user.id, 'errors.general'))

# ── /language ──────────────────────────────────────────────
@bot.message_handler(commands=['language'])
def language_handler(message):
    user_id = message.from_user.id
    from i18n import get_all_languages
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    for lang in get_all_languages():
        keyboard.add(types.InlineKeyboardButton(lang['name'], callback_data=f"setlang_{lang['code']}"))
    keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_main'), callback_data="back_to_main"))
    bot.send_message(message.chat.id, get_text(user_id, 'language.select_title'), reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data == 'language_menu')
def language_menu_handler(call):
    user_id = call.from_user.id
    from i18n import get_all_languages
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
    else:
        bot.answer_callback_query(call.id, get_text(user_id, 'errors.general_short'))

# ── back_to_main ───────────────────────────────────────────
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

# ── ZarinPal verification callback ─────────────────────────
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
                try:
                    bot.send_message(int(user_id), f"✅ Payment successful!\n\n💰 Amount: {int(amount):,} T\n🔢 Ref: {ref_id or '---'}\n💎 Balance: {new_balance:,} T")
                except: pass
                return render_template('payment_result.html', success=True,
                                       amount=f"{int(amount):,}", ref_id=ref_id or '---', balance=f"{new_balance:,}")
        return render_template('payment_result.html', success=False, message="Verification failed")
    except Exception as e:
        logger.error(f"Verify error: {e}")
        return render_template('payment_result.html', success=False, message="Error")

# ── save_user (called by middleware / handlers) ─────────────
def save_user(user):
    from db.repositories.user_repository import UserRepository
    return UserRepository().create_if_not_exists(user.id)

# ═══════════════════════════════════════════════════════════════
# Startup
# ═══════════════════════════════════════════════════════════════
if __name__ == '__main__':
    try:
        from database import setup_databases
        setup_databases()
        logging.info("✅ Databases initialized")

        from db.migrations import MigrationManager
        mm = MigrationManager()
        if mm.migrate():
            logging.info("✅ Migrations applied")

        backup_file = 'data/users_backup.json'
        if os.path.exists(backup_file):
            from db.repositories.user_repository import UserRepository
            repo = UserRepository()
            with open(backup_file, 'r', encoding='utf-8') as f:
                users_data = json.load(f)
            for uid, bal in users_data.items():
                repo.create_if_not_exists(int(uid))
                repo.add_balance(int(uid), int(bal))
            logging.info(f"✅ Restored {len(users_data)} users from backup")

        from backup_manager import BackupManager
        BackupManager(backup_interval=300).start()
        logging.info("✅ Backup service started")

        bot.remove_webhook()
        time.sleep(0.5)
        bot.set_webhook(url=BOT_CONFIG['webhook_url'])
        logging.info(f"✅ Webhook set to {BOT_CONFIG['webhook_url']}")

        app.run(host='0.0.0.0', port=5000, debug=False)

    except Exception as e:
        logging.error(f"❌ Fatal startup error: {e}", exc_info=True)
        exit(1)
