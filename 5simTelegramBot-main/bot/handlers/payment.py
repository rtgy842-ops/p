"""
bot/handlers/payment.py — Payment Handlers
───────────────────────────────────────────
add_funds, zarinpal_payment, card_payment, receipt, verify.
All use compat layer (PaymentService gateways ready).
"""

import logging

from bot.router import router
from i18n import get_text

logger = logging.getLogger(__name__)

_bot = None


def init(bot_instance):
    global _bot
    _bot = bot_instance


@router.callback('add_funds')
def handle_add_funds(call):
    from telebot import types
    user_id = call.from_user.id
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        types.InlineKeyboardButton(get_text(user_id, 'payment.online'), callback_data="zarinpal_payment"),
        types.InlineKeyboardButton(get_text(user_id, 'payment.card_to_card'), callback_data="card_payment"),
        types.InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="back_to_main")
    )
    _bot.edit_message_text(get_text(user_id, 'payment.select_method'), call.message.chat.id, call.message.message_id, reply_markup=keyboard)


@router.callback('zarinpal_payment')
def handle_zarinpal_payment(call):
    user_id = call.from_user.id
    msg = _bot.edit_message_text(get_text(user_id, 'payment.enter_amount'), call.message.chat.id, call.message.message_id)
    _bot.register_next_step_handler(msg, process_zarinpal_amount)


def process_zarinpal_amount(message):
    from telebot import types

    from compat.legacy_facade import payment_create_zarinpal as compat_zarinpal_create

    try:
        user_id = message.from_user.id
        amount = int(message.text)
        if amount < 5000:
            _bot.reply_to(message, get_text(user_id, 'payment.min_amount'))
            return

        success, payment_url, authority = compat_zarinpal_create(user_id, amount, f"شارژ حساب کاربر {user_id}")
        if success and payment_url:
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(
                types.InlineKeyboardButton(get_text(user_id, 'payment.payment_button'), url=payment_url),
                types.InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="add_funds")
            )
            _bot.reply_to(message, get_text(user_id, 'payment.payment_link', amount=amount), reply_markup=keyboard)
        else:
            _bot.reply_to(message, get_text(user_id, 'payment.payment_error'))
    except ValueError:
        _bot.reply_to(message, get_text(message.from_user.id, 'payment.invalid_amount'))


@router.callback('card_payment')
def handle_card_payment(call):
    msg = _bot.edit_message_text("💳 لطفاً مبلغ مورد نظر را به تومان وارد کنید:\nمثال: 50000", call.message.chat.id, call.message.message_id)
    from card_payment import CardPayment
    cp = CardPayment(_bot)
    _bot.register_next_step_handler(msg, cp.handle_new_payment)


@router.callback('copy_')
def handle_copy(call):
    text = call.data.split("_", 1)[1]
    _bot.answer_callback_query(call.id, f"✅ کپی شد:\n{text}", show_alert=True)


@router.callback('send_receipt_')
def handle_send_receipt(call):
    payment_id = call.data.split("_")[2]
    msg = _bot.edit_message_text("🧾 لطفاً تصویر رسید پرداخت را ارسال کنید:", call.message.chat.id, call.message.message_id)
    from card_payment import CardPayment
    cp = CardPayment(_bot)
    _bot.register_next_step_handler(msg, cp.handle_receipt, payment_id)


# NOTE: approve_payment_ and reject_payment_ callbacks moved to admin_bot.py
# These are admin-only operations and must NOT be in the customer bot.
