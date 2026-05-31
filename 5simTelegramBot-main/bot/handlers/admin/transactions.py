"""
bot/handlers/admin/transactions.py — Admin Transactions (Enterprise)
─────────────────────────────────────────────────
Uses CardPaymentRepository — no direct sqlite3.
"""

import logging
import re

from telebot import types

from bot.router import router
from config import BOT_CONFIG
from i18n import get_text

logger = logging.getLogger(__name__)
_bot = None


def init(bot_instance):
    global _bot
    _bot = bot_instance


def _get_repo():
    from db.repositories.card_payment_repository import CardPaymentRepository
    return CardPaymentRepository()


def _format_txn(user_id, t, text):
    pid = t['payment_id'] if isinstance(t, dict) else t[0]
    uid = t['user_id'] if isinstance(t, dict) else t[1]
    amt = t['amount'] if isinstance(t, dict) else t[2]
    st = t['status'] if isinstance(t, dict) else t[3]
    ct = t['created_at'] if isinstance(t, dict) else t[4]
    status_emoji = (get_text(user_id, 'transactions.status_pending') if st == 'pending'
                    else get_text(user_id, 'transactions.status_approved') if st == 'approved'
                    else get_text(user_id, 'transactions.status_rejected'))
    text += f"🆔 Payment ID: {pid}\n👤 User: {uid}\n💰 Amount: {amt:,}\n📝 Status: {status_emoji} {st}\n🕒 Date: {ct}\n➖➖➖➖➖➖➖➖\n"
    return text


@router.callback('transactions')
def handle_transactions(call):
    user_id = call.from_user.id
    if user_id not in BOT_CONFIG['admin_ids']:
        _bot.answer_callback_query(call.id, get_text(user_id, 'errors.no_access_section'))
        return
    transactions = _get_repo().list_recent(5)
    if not transactions:
        text = get_text(user_id, 'transactions.empty')
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="admin_panel"))
    else:
        text = get_text(user_id, 'transactions.recent_title', page=1)
        for t in transactions:
            text = _format_txn(user_id, t, text)
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            types.InlineKeyboardButton(get_text(user_id, 'transactions.prev_page'), callback_data="transactions_prev"),
            types.InlineKeyboardButton(get_text(user_id, 'transactions.next_page'), callback_data="transactions_next"))
        keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="admin_panel"))
    _bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)


@router.callback('transactions_prev')
def transactions_prev(call):
    paginate_transactions(call, -1)


@router.callback('transactions_next')
def transactions_next(call):
    paginate_transactions(call, 1)


def paginate_transactions(call, direction):
    user_id = call.from_user.id
    if user_id not in BOT_CONFIG['admin_ids']:
        _bot.answer_callback_query(call.id, get_text(user_id, 'errors.no_access_section'))
        return
    match = re.search(r'\(Page (\d+)\)', call.message.text)
    current_page = int(match.group(1)) if match else 1
    page = current_page + direction
    if page < 1:
        _bot.answer_callback_query(call.id, get_text(user_id, 'transactions.invalid_page'))
        return
    offset = (page - 1) * 5
    transactions = _get_repo().list_paginated(offset, 5)
    if not transactions:
        text = get_text(user_id, 'transactions.no_page')
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="admin_panel"))
    else:
        text = get_text(user_id, 'transactions.recent_title', page=page)
        for t in transactions:
            text = _format_txn(user_id, t, text)
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            types.InlineKeyboardButton(get_text(user_id, 'transactions.prev_page'), callback_data="transactions_prev"),
            types.InlineKeyboardButton(get_text(user_id, 'transactions.next_page'), callback_data="transactions_next"))
        keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="admin_panel"))
    _bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
