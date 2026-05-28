"""
card_payment.py — Card-to-Card Payment Handler (Enterprise Refactored)
─────────────────────────────────────────────────
Handles card payment flows: receipt submission, admin approval/rejection.
Now uses enterprise CardPaymentRepository + WalletService.
No direct sqlite3 connections.
"""

from telebot import types
import logging
from config import BOT_CONFIG
from compat.legacy_facade import add_balance as compat_add_balance
from db.repositories.card_payment_repository import CardPaymentRepository
from db.repositories.settings_repository import SettingsRepository
from i18n import get_text

logger = logging.getLogger(__name__)


class CardPayment:
    """Card-to-Card payment flow handler."""
    
    def __init__(self, bot):
        self.bot = bot
        self._payment_repo = CardPaymentRepository()
        self._settings_repo = SettingsRepository()

    def get_card_info(self):
        """Get bank card info from admin.db."""
        try:
            card_info = self._settings_repo.get_card_info()
            if card_info:
                return (card_info['card_number'], card_info['card_holder'])
            return None
        except Exception as e:
            logger.error(f"Error getting card info: {e}")
            return None

    def save_payment_request(self, user_id, amount):
        """Create a new card payment request."""
        try:
            return self._payment_repo.create(user_id, amount)
        except Exception as e:
            logger.error(f"Error saving payment request: {e}")
            return None

    def handle_new_payment(self, message):
        try:
            user_id = message.from_user.id
            amount = int(message.text.strip())
            if amount < 5000:
                self.bot.reply_to(message, get_text(user_id, 'payment.min_amount'))
                return

            card_info = self.get_card_info()
            if not card_info:
                self.bot.reply_to(message, get_text(user_id, 'payment.no_card_info'))
                return

            card_number, card_holder = card_info
            payment_id = self.save_payment_request(user_id, amount)

            if not payment_id:
                self.bot.reply_to(message, get_text(user_id, 'payment.payment_request_error'))
                return

            keyboard = types.InlineKeyboardMarkup(row_width=1)
            keyboard.add(
                types.InlineKeyboardButton(
                    get_text(user_id, 'payment.card_number_btn', card=card_number),
                    callback_data=f"copy_{card_number}"
                ),
                types.InlineKeyboardButton(
                    get_text(user_id, 'payment.card_holder_btn', holder=card_holder),
                    callback_data=f"copy_{card_holder}"
                ),
                types.InlineKeyboardButton(
                    get_text(user_id, 'payment.send_receipt'),
                    callback_data=f"send_receipt_{payment_id}"
                ),
                types.InlineKeyboardButton(
                    get_text(user_id, 'navigation.back'),
                    callback_data="add_funds"
                )
            )

            self.bot.reply_to(
                message,
                get_text(user_id, 'payment.card_info', amount=amount, card=card_number, holder=card_holder),
                reply_markup=keyboard,
                parse_mode='HTML'
            )

        except ValueError:
            self.bot.reply_to(message, get_text(message.from_user.id, 'payment.invalid_amount'))
        except Exception as e:
            logger.error(f"Error in handle_new_payment: {e}")
            self.bot.reply_to(message, get_text(message.from_user.id, 'errors.general'))

    def handle_receipt(self, message, payment_id):
        user_id = message.from_user.id
        if not message.photo:
            msg = self.bot.reply_to(message, get_text(user_id, 'payment.receipt_prompt'))
            self.bot.register_next_step_handler(msg, self.handle_receipt, payment_id)
            return

        try:
            file_id = message.photo[-1].file_id
            self._payment_repo.update_receipt(payment_id, file_id)
            
            payment = self._payment_repo.find_by_id(payment_id)
            amount = payment['amount'] if payment else 0

            # Send to admins
            keyboard = types.InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                types.InlineKeyboardButton(
                    get_text(user_id, 'payment.approve'),
                    callback_data=f"approve_payment_{payment_id}"
                ),
                types.InlineKeyboardButton(
                    get_text(user_id, 'payment.reject'),
                    callback_data=f"reject_payment_{payment_id}"
                )
            )

            for admin_id in BOT_CONFIG['admin_ids']:
                self.bot.send_photo(
                    admin_id,
                    file_id,
                    get_text(admin_id, 'payment.admin_new_request',
                             payment_id=payment_id, user_id=user_id, amount=amount),
                    reply_markup=keyboard
                )

            # Clean up old messages
            try:
                for i in range(10):
                    self.bot.delete_message(message.chat.id, message.message_id - i)
            except Exception:
                pass

            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton(
                get_text(user_id, 'navigation.back_to_main'),
                callback_data="back_to_main"
            ))
            
            self.bot.send_message(
                message.chat.id,
                get_text(user_id, 'payment.receipt_sent'),
                reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"Error handling receipt: {e}")
            self.bot.reply_to(message, get_text(message.from_user.id, 'payment.receipt_error'))

    def verify_payment(self, call, payment_id, action):
        admin_id = call.from_user.id
        if admin_id not in BOT_CONFIG['admin_ids']:
            self.bot.answer_callback_query(call.id, get_text(admin_id, 'errors.no_access'))
            return

        try:
            payment = self._payment_repo.find_by_id(payment_id)

            if not payment:
                self.bot.answer_callback_query(call.id, get_text(admin_id, 'errors.invalid_data'))
                return

            user_id = payment['user_id']
            amount = payment['amount']
            status = payment['status']

            if status != 'pending':
                self.bot.answer_callback_query(call.id, get_text(admin_id, 'errors.invalid_data'))
                return

            if action == "reject":
                msg = self.bot.edit_message_caption(
                    get_text(admin_id, 'payment.rejection_prompt'),
                    call.message.chat.id,
                    call.message.message_id
                )
                self.bot.register_next_step_handler(msg, self.process_rejection, payment_id)
                return

            # Approve: add balance + update payment status
            new_balance = compat_add_balance(user_id, amount,
                description='Card-to-card payment approved',
                ref_id=payment_id)
            
            if new_balance is not None:
                self._payment_repo.approve(payment_id, admin_id)

                keyboard = types.InlineKeyboardMarkup(row_width=2)
                keyboard.add(
                    types.InlineKeyboardButton(
                        get_text(user_id, 'main_menu.start_shopping'),
                        callback_data="buy_number"
                    ),
                    types.InlineKeyboardButton(
                        get_text(user_id, 'navigation.back'),
                        callback_data="back_to_main"
                    )
                )
                
                self.bot.send_message(
                    user_id,
                    get_text(user_id, 'payment.approved_user',
                             amount=amount, payment_id=payment_id, balance=new_balance),
                    reply_markup=keyboard
                )

                self.bot.edit_message_caption(
                    get_text(admin_id, 'payment.approved_admin',
                             amount=amount, user_id=user_id, balance=new_balance),
                    call.message.chat.id,
                    call.message.message_id
                )

                self.bot.answer_callback_query(call.id, get_text(admin_id, 'payment.approve'))
            else:
                raise Exception("Failed to update balance")

        except Exception as e:
            logger.error(f"Error in verify_payment: {e}")
            self.bot.answer_callback_query(call.id, get_text(call.from_user.id, 'errors.general_short'))

    def process_rejection(self, message, payment_id):
        admin_id = message.from_user.id
        if admin_id not in BOT_CONFIG['admin_ids']:
            return

        try:
            reason = message.text.strip()
            self._payment_repo.reject(payment_id, reason)

            payment = self._payment_repo.find_by_id(payment_id)
            if payment:
                user_id = payment['user_id']
                amount = payment['amount']
                self.bot.send_message(
                    user_id,
                    get_text(user_id, 'payment.rejected_user',
                             amount=amount, payment_id=payment_id, reason=reason)
                )

            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton(
                get_text(admin_id, 'navigation.back_to_main'),
                callback_data="back_to_main"
            ))
            
            self.bot.reply_to(
                message,
                get_text(admin_id, 'payment.rejection_sent'),
                reply_markup=keyboard
            )

        except Exception as e:
            logger.error(f"Error in process_rejection: {e}")
            self.bot.reply_to(message, get_text(message.from_user.id, 'payment.rejection_error'))