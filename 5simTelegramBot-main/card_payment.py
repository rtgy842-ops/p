from telebot import types
import sqlite3
import logging
import time
from config import BOT_CONFIG, DB_CONFIG
from database import add_balance, save_transaction
from i18n import get_text

class CardPayment:
    def __init__(self, bot):
        self.bot = bot
        self.setup_database()

    def setup_database(self):
        try:
            # ایجاد جدول پرداخت‌های کارت به کارت
            conn = sqlite3.connect(DB_CONFIG['users_db'])
            cursor = conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS card_payments
                (payment_id TEXT PRIMARY KEY,
                 user_id INTEGER,
                 amount INTEGER,
                 status TEXT DEFAULT 'pending',
                 receipt TEXT,
                 admin_response TEXT,
                 created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error(f"Error in setup_database: {e}")

    def get_card_info(self):
        try:
            conn = sqlite3.connect(DB_CONFIG['admin_db'])
            cursor = conn.cursor()
            cursor.execute('SELECT card_number, card_holder FROM card_info LIMIT 1')
            card_info = cursor.fetchone()
            conn.close()
            return card_info
        except Exception as e:
            logging.error(f"Error getting card info: {e}")
            return None

    def save_payment_request(self, user_id, amount):
        try:
            payment_id = f"CP{int(time.time())}{user_id}"
            conn = sqlite3.connect(DB_CONFIG['users_db'])
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO card_payments (payment_id, user_id, amount) VALUES (?, ?, ?)',
                (payment_id, user_id, amount)
            )
            conn.commit()
            conn.close()
            return payment_id
        except Exception as e:
            logging.error(f"Error saving payment request: {e}")
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
                types.InlineKeyboardButton(get_text(user_id, 'payment.card_number_btn', card=card_number), callback_data=f"copy_{card_number}"),
                types.InlineKeyboardButton(get_text(user_id, 'payment.card_holder_btn', holder=card_holder), callback_data=f"copy_{card_holder}"),
                types.InlineKeyboardButton(get_text(user_id, 'payment.send_receipt'), callback_data=f"send_receipt_{payment_id}"),
                types.InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="add_funds")
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
            logging.error(f"Error in handle_new_payment: {e}")
            self.bot.reply_to(message, get_text(message.from_user.id, 'errors.general'))

    def handle_receipt(self, message, payment_id):
        user_id = message.from_user.id
        if not message.photo:
            msg = self.bot.reply_to(message, get_text(user_id, 'payment.receipt_prompt'))
            self.bot.register_next_step_handler(msg, self.handle_receipt, payment_id)
            return

        try:
            conn = sqlite3.connect(DB_CONFIG['users_db'])
            cursor = conn.cursor()
            cursor.execute('UPDATE card_payments SET receipt = ? WHERE payment_id = ?',
                         (message.photo[-1].file_id, payment_id))
            cursor.execute('SELECT amount FROM card_payments WHERE payment_id = ?', (payment_id,))
            amount = cursor.fetchone()[0]
            conn.commit()
            conn.close()

            # ارسال به ادمین‌ها
            keyboard = types.InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                types.InlineKeyboardButton(get_text(user_id, 'payment.approve'), callback_data=f"approve_payment_{payment_id}"),
                types.InlineKeyboardButton(get_text(user_id, 'payment.reject'), callback_data=f"reject_payment_{payment_id}")
            )

            for admin_id in BOT_CONFIG['admin_ids']:
                self.bot.send_photo(
                    admin_id,
                    message.photo[-1].file_id,
                    get_text(admin_id, 'payment.admin_new_request', payment_id=payment_id, user_id=user_id, amount=amount),
                    reply_markup=keyboard
                )

            # حذف پیام‌های قبلی
            try:
                for i in range(10):
                    self.bot.delete_message(message.chat.id, message.message_id - i)
            except:
                pass

            # ارسال پیام جدید با دکمه برگشت
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_main'), callback_data="back_to_main"))
            
            self.bot.send_message(
                message.chat.id,
                get_text(user_id, 'payment.receipt_sent'),
                reply_markup=keyboard
            )

        except Exception as e:
            logging.error(f"Error handling receipt: {e}")
            self.bot.reply_to(message, get_text(message.from_user.id, 'payment.receipt_error'))

    def verify_payment(self, call, payment_id, action):
        admin_id = call.from_user.id
        if admin_id not in BOT_CONFIG['admin_ids']:
            self.bot.answer_callback_query(call.id, get_text(admin_id, 'errors.no_access'))
            return

        try:
            conn = sqlite3.connect(DB_CONFIG['users_db'])
            cursor = conn.cursor()
            cursor.execute('SELECT user_id, amount, status FROM card_payments WHERE payment_id = ?', (payment_id,))
            payment = cursor.fetchone()

            if not payment:
                self.bot.answer_callback_query(call.id, get_text(admin_id, 'errors.invalid_data'))
                return

            user_id, amount, status = payment

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

            # افزایش موجودی کاربر
            new_balance = add_balance(user_id, amount)
            if new_balance is not None:
                # ثبت تراکنش
                save_transaction(
                    user_id=user_id,
                    amount=amount,
                    type_trans='deposit',
                    description='شارژ حساب از طریق کارت به کارت',
                    ref_id=payment_id
                )
                cursor.execute('''
                    UPDATE card_payments
                    SET status = 'approved',
                        admin_response = ?
                    WHERE payment_id = ?
                ''', (f"تایید شده توسط {admin_id}", payment_id))
                conn.commit()

                # ارسال پیام به کاربر
                keyboard = types.InlineKeyboardMarkup(row_width=2)
                keyboard.add(
                    types.InlineKeyboardButton(get_text(user_id, 'main_menu.start_shopping'), callback_data="buy_number"),
                    types.InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="back_to_main")
                )
                
                self.bot.send_message(
                    user_id,
                    get_text(user_id, 'payment.approved_user', amount=amount, payment_id=payment_id, balance=new_balance),
                    reply_markup=keyboard
                )

                # آپدیت پیام ادمین
                self.bot.edit_message_caption(
                    get_text(admin_id, 'payment.approved_admin', amount=amount, user_id=user_id, balance=new_balance),
                    call.message.chat.id,
                    call.message.message_id
                )

                self.bot.answer_callback_query(call.id, get_text(admin_id, 'payment.approve'))
            else:
                raise Exception("Failed to update balance")

        except Exception as e:
            logging.error(f"Error in verify_payment: {e}")
            self.bot.answer_callback_query(call.id, get_text(call.from_user.id, 'errors.general_short'))
        finally:
            if 'conn' in locals():
                conn.close()

    def process_rejection(self, message, payment_id):
        admin_id = message.from_user.id
        if admin_id not in BOT_CONFIG['admin_ids']:
            return

        try:
            reason = message.text.strip()
            conn = sqlite3.connect(DB_CONFIG['users_db'])
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE card_payments
                SET status = 'rejected',
                    admin_response = ?
                WHERE payment_id = ?
            ''', (reason, payment_id))
            
            cursor.execute('SELECT user_id, amount FROM card_payments WHERE payment_id = ?', (payment_id,))
            payment = cursor.fetchone()
            conn.commit()
            conn.close()

            if payment:
                user_id, amount = payment
                self.bot.send_message(
                    user_id,
                    get_text(user_id, 'payment.rejected_user', amount=amount, payment_id=payment_id, reason=reason)
                )

            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton(get_text(admin_id, 'navigation.back_to_main'), callback_data="back_to_main"))
            
            self.bot.reply_to(
                message,
                get_text(admin_id, 'payment.rejection_sent'),
                reply_markup=keyboard
            )

        except Exception as e:
            logging.error(f"Error in process_rejection: {e}")
            self.bot.reply_to(message, get_text(message.from_user.id, 'payment.rejection_error'))