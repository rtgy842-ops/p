"""
bot/handlers/admin/settings.py — Admin Settings Handlers
"""

import logging, sqlite3
from bot.router import router
from i18n import get_text
from config import BOT_CONFIG, DB_CONFIG
from telebot import types

logger = logging.getLogger(__name__)
_bot = None

def init(bot_instance):
    global _bot; _bot = bot_instance

@router.callback('set_profit')
def handle_set_profit(call):
    user_id = call.from_user.id
    if user_id not in BOT_CONFIG['admin_ids']: _bot.answer_callback_query(call.id, get_text(user_id, 'errors.no_access_section')); return
    try:
        conn = sqlite3.connect('admin.db'); cursor = conn.cursor()
        cursor.execute('SELECT value FROM settings WHERE key = "profit_percentage"'); current_profit = float(cursor.fetchone()[0]) if cursor.fetchone() else 0
        conn.close()
        msg = _bot.edit_message_text(get_text(user_id, 'admin.profit_current', profit=current_profit), call.message.chat.id, call.message.message_id)
        _bot.register_next_step_handler(msg, process_profit_percentage)
    except Exception as e:
        logger.error(f"Error in set_profit: {e}")
        _bot.answer_callback_query(call.id, get_text(call.from_user.id, 'errors.general_short'))

def process_profit_percentage(message):
    admin_id = message.from_user.id
    try:
        profit = float(message.text.strip().replace(',', ''))
        if profit < 0: _bot.reply_to(message, get_text(admin_id, 'admin.profit_negative')); return
        conn = sqlite3.connect('admin.db'); cursor = conn.cursor()
        cursor.execute('SELECT value FROM settings WHERE key = "profit_percentage"')
        if cursor.fetchone() is None: cursor.execute('INSERT INTO settings (key, value) VALUES (?, ?)', ('profit_percentage', str(profit)))
        else: cursor.execute('UPDATE settings SET value = ? WHERE key = "profit_percentage"', (str(profit),))
        conn.commit(); conn.close()
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(types.InlineKeyboardButton(get_text(admin_id, 'navigation.set_again'), callback_data="set_profit"), types.InlineKeyboardButton(get_text(admin_id, 'navigation.back_to_panel'), callback_data="admin_panel"))
        _bot.reply_to(message, get_text(admin_id, 'admin.profit_saved', profit=profit), reply_markup=keyboard)
    except ValueError: _bot.reply_to(message, get_text(admin_id, 'admin.profit_invalid'))
    except Exception as e: logger.error(f"Error: {e}")

@router.callback('set_usd_rate')
def handle_set_usd_rate(call):
    user_id = call.from_user.id
    if user_id not in BOT_CONFIG['admin_ids']: _bot.answer_callback_query(call.id, get_text(user_id, 'errors.no_access_section')); return
    msg = _bot.edit_message_text(get_text(user_id, 'admin.ruble_current'), call.message.chat.id, call.message.message_id)
    _bot.register_next_step_handler(msg, process_usd_rate)

def process_usd_rate(message):
    admin_id = message.from_user.id
    if not message.text.replace('.', '').isdigit(): _bot.reply_to(message, get_text(admin_id, 'admin.ruble_invalid')); return
    rate = float(message.text)
    conn = sqlite3.connect('admin.db'); conn.execute('UPDATE settings SET value = ? WHERE key = "usd_rate"', (rate,)); conn.commit(); conn.close()
    keyboard = types.InlineKeyboardMarkup(); keyboard.add(types.InlineKeyboardButton(get_text(admin_id, 'navigation.back_to_panel'), callback_data="admin_panel"))
    _bot.reply_to(message, get_text(admin_id, 'admin.ruble_saved', rate=rate), reply_markup=keyboard)

@router.callback('set_card')
def handle_set_card(call):
    user_id = call.from_user.id
    if user_id not in BOT_CONFIG['admin_ids']: _bot.answer_callback_query(call.id, get_text(user_id, 'errors.no_access')); return
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'payment.new_card'), callback_data="new_card"), types.InlineKeyboardButton(get_text(user_id, 'payment.check_card_info'), callback_data="check_card_info"), types.InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="admin_panel"))
    _bot.edit_message_text(get_text(user_id, 'payment.card_management'), call.message.chat.id, call.message.message_id, reply_markup=keyboard)

@router.callback('new_card')
def handle_new_card(call):
    if call.from_user.id not in BOT_CONFIG['admin_ids']: _bot.answer_callback_query(call.id, "⛔️ شما دسترسی ادمین ندارید"); return
    msg = _bot.edit_message_text("💳 لطفاً شماره کارت را وارد کنید:\nمثال: 6037-9974-1234-5678", call.message.chat.id, call.message.message_id)
    _bot.register_next_step_handler(msg, process_card_number)

def process_card_number(message):
    if message.from_user.id not in BOT_CONFIG['admin_ids']: return
    card_number = message.text.strip().replace('-', '').replace(' ', '')
    if not card_number.isdigit() or len(card_number) != 16:
        msg = _bot.reply_to(message, "❌ شماره کارت نامعتبر است."); _bot.register_next_step_handler(msg, process_card_number); return
    conn = sqlite3.connect(DB_CONFIG['admin_db']); conn.execute('DELETE FROM card_info'); conn.execute('INSERT INTO card_info (card_number) VALUES (?)', (card_number,)); conn.commit(); conn.close()
    msg = _bot.reply_to(message, "✅ شماره کارت ذخیره شد.\n\n👤 لطفاً نام و نام خانوادگی صاحب کارت را وارد کنید:")
    _bot.register_next_step_handler(msg, process_card_holder)

def process_card_holder(message):
    if message.from_user.id not in BOT_CONFIG['admin_ids']: return
    card_holder = message.text.strip()
    if len(card_holder) < 3: msg = _bot.reply_to(message, "❌ نام صاحب کارت نامعتبر است."); _bot.register_next_step_handler(msg, process_card_holder); return
    conn = sqlite3.connect('admin.db'); conn.execute('UPDATE card_info SET card_holder = ? WHERE card_holder IS NULL', (card_holder,)); conn.commit()
    cursor = conn.cursor(); cursor.execute('SELECT card_number, card_holder FROM card_info LIMIT 1'); card_info = cursor.fetchone(); conn.close()
    if card_info:
        keyboard = types.InlineKeyboardMarkup(); keyboard.add(types.InlineKeyboardButton("🔙 برگشت به پنل مدیریت", callback_data="admin_panel"))
        _bot.reply_to(message, f"✅ اطلاعات کارت با موفقیت ذخیره شد:\n\n💳 شماره کارت: <code>{card_info[0]}</code>\n👤 صاحب کارت: <code>{card_info[1]}</code>", reply_markup=keyboard, parse_mode='HTML')

@router.callback('check_card_info')
def check_card_info(call):
    if call.from_user.id not in BOT_CONFIG['admin_ids']: _bot.answer_callback_query(call.id, "⛔️ دسترسی ندارید"); return
    conn = sqlite3.connect(DB_CONFIG['admin_db']); cursor = conn.cursor(); cursor.execute('SELECT card_number, card_holder FROM card_info LIMIT 1'); card_info = cursor.fetchone(); conn.close()
    if card_info: _bot.answer_callback_query(call.id, f"اطلاعات کارت:\nشماره: {card_info[0]}\nبه نام: {card_info[1]}", show_alert=True)
    else: _bot.answer_callback_query(call.id, "❌ اطلاعات کارتی ثبت نشده است", show_alert=True)