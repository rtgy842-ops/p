"""
bot/handlers/admin/transactions.py — Admin Transactions Viewer
"""

import logging, sqlite3
from bot.router import router
from i18n import get_text
from config import BOT_CONFIG
from telebot import types

logger = logging.getLogger(__name__)
_bot = None

def init(bot_instance):
    global _bot; _bot = bot_instance

@router.callback('transactions')
def handle_transactions(call):
    user_id = call.from_user.id
    if user_id not in BOT_CONFIG['admin_ids']: _bot.answer_callback_query(call.id, get_text(user_id, 'errors.no_access_section')); return
    conn = sqlite3.connect('users.db'); cursor = conn.cursor()
    cursor.execute('SELECT cp.payment_id, cp.user_id, cp.amount, cp.status, cp.created_at FROM card_payments cp ORDER BY cp.created_at DESC LIMIT 5')
    transactions = cursor.fetchall(); conn.close()
    if not transactions:
        text = get_text(user_id, 'transactions.empty'); keyboard = types.InlineKeyboardMarkup(); keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="admin_panel"))
    else:
        text = get_text(user_id, 'transactions.recent_title', page=1)
        for t in transactions:
            status_emoji = get_text(user_id, 'transactions.status_pending') if t[3] == 'pending' else get_text(user_id, 'transactions.status_approved') if t[3] == 'approved' else get_text(user_id, 'transactions.status_rejected')
            text += f"🆔 Payment ID: {t[0]}\n👤 User: {t[1]}\n💰 Amount: {t[2]:,}\n📝 Status: {status_emoji} {t[3]}\n🕒 Date: {t[4]}\n➖➖➖➖➖➖➖➖\n"
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'transactions.prev_page'), callback_data="transactions_prev"), types.InlineKeyboardButton(get_text(user_id, 'transactions.next_page'), callback_data="transactions_next"))
        keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="admin_panel"))
    _bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)

@router.callback('transactions_prev')
def transactions_prev(call):
    paginate_transactions(call, -1)

@router.callback('transactions_next')
def transactions_next(call):
    paginate_transactions(call, 1)

def paginate_transactions(call, direction):
    import re
    user_id = call.from_user.id
    if user_id not in BOT_CONFIG['admin_ids']: _bot.answer_callback_query(call.id, get_text(user_id, 'errors.no_access_section')); return
    match = re.search(r'\(Page (\d+)\)', call.message.text); current_page = int(match.group(1)) if match else 1
    page = current_page + direction
    if page < 1: _bot.answer_callback_query(call.id, get_text(user_id, 'transactions.invalid_page')); return
    offset = (page - 1) * 5
    conn = sqlite3.connect('users.db'); cursor = conn.cursor()
    cursor.execute('SELECT cp.payment_id, cp.user_id, cp.amount, cp.status, cp.created_at FROM card_payments cp ORDER BY cp.created_at DESC LIMIT 5 OFFSET ?', (offset,))
    transactions = cursor.fetchall(); conn.close()
    if not transactions:
        text = get_text(user_id, 'transactions.no_page'); keyboard = types.InlineKeyboardMarkup(); keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="admin_panel"))
    else:
        text = get_text(user_id, 'transactions.recent_title', page=page)
        for t in transactions:
            status_emoji = (get_text(user_id, 'transactions.status_pending') if t[3] == 'pending' else get_text(user_id, 'transactions.status_approved') if t[3] == 'approved' else get_text(user_id, 'transactions.status_rejected'))
            text += f"🆔 Payment ID: {t[0]}\n👤 User: {t[1]}\n💰 Amount: {t[2]:,}\n📝 Status: {status_emoji} {t[3]}\n🕒 Date: {t[4]}\n➖➖➖➖➖➖➖➖\n"
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'transactions.prev_page'), callback_data="transactions_prev"), types.InlineKeyboardButton(get_text(user_id, 'transactions.next_page'), callback_data="transactions_next"))
        keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="admin_panel"))
    _bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)