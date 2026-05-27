"""
web/routes/payment.py — Payment Verification Route
─────────────────────────────────────────────────────
/verify/<user_id>/<amount> — ZarinPal callback handler.
"""

import logging
from flask import Blueprint, request, render_template

logger = logging.getLogger(__name__)

payment_bp = Blueprint('payment_web', __name__)

_bot = None


def init(bot_instance):
    global _bot
    _bot = bot_instance


@payment_bp.route('/verify/<user_id>/<amount>')
def verify_payment(user_id, amount):
    from compat.legacy_facade import (
        payment_verify_zarinpal as compat_zarinpal_verify,
        add_balance as compat_add_balance,
    )

    try:
        logger.info(f"Payment verification started for user {user_id}, amount {amount}")
        authority = request.args.get('Authority')
        status = request.args.get('Status')

        if status != 'OK':
            return render_template('payment_result.html', success=False, message="پرداخت توسط کاربر لغو شد")

        success, ref_id = compat_zarinpal_verify(authority, int(amount))

        if success:
            new_balance = compat_add_balance(int(user_id), int(amount),
                description='شارژ حساب از طریق درگاه زرین‌پال', ref_id=ref_id)

            if new_balance is not None:
                success_message = f"""✅ پرداخت شما با موفقیت انجام شد\n\n💰 مبلغ: {int(amount):,} تومان\n🔢 کد پیگیری: {ref_id or '---'}\n💎 موجودی فعلی: {new_balance:,} تومان"""
                try:
                    _bot.send_message(int(user_id), success_message)
                except Exception as e:
                    logger.error(f"Error sending message to user: {e}")

                return render_template('payment_result.html', success=True,
                    amount=f"{int(amount):,}", ref_id=ref_id or '---', balance=f"{new_balance:,}")
            else:
                return render_template('payment_result.html', success=False, message="خطا در بروزرسانی موجودی")
        else:
            return render_template('payment_result.html', success=False, message="خطا در تایید پرداخت")

    except Exception as e:
        logger.error(f"Payment verification error: {e}", exc_info=True)
        return render_template('payment_result.html', success=False, message="خطا در پردازش پرداخت")