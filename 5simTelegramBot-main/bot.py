import telebot
import requests
import json
import sqlite3
from telebot import types
from flask import Flask, request, render_template, render_template_string, jsonify, send_from_directory, redirect, url_for, session, send_file, Blueprint
import logging
from admin_config import AdminConfig
import locale
from config import BOT_CONFIG, HEROSMS_CONFIG, DB_CONFIG, PAYMENT_CONFIG, COUNTRY_ID_MAP, SERVICE_CODE_MAP
from data.service_countries import (
    SERVICE_COUNTRIES, ALL_SERVICES, SERVICE_DISPLAY_KEYS,
    get_countries_for_service as _get_countries_for_service,
    get_default_operator as _get_default_operator,
    get_country_name as _get_country_name
)
from i18n import get_text, set_user_language, get_user_language
from currency_service import CurrencyService
from datetime import datetime, timedelta
from database import setup_databases, add_balance, save_transaction, get_user_balance, setup_users_database
from wallet import Wallet
from payment import ZarinPal
from operator_config import OperatorConfig
import os
from persiantools.jdatetime import JalaliDateTime
import time
from card_payment import CardPayment
from backup_manager import BackupManager
import logging.handlers
from routes.order_details import order_details_bp  # برای مسیرهای جزئیات سفارش

locale.setlocale(locale.LC_ALL, '')

# تنظیمات اولیه
# HEROSMS_API_KEY = 'cb28fe1389Abce0053b2fb3bA48d6b4c'
# HEROSMS_API_URL = 'https://hero-sms.com/stubs/handler_api.php'
# WEBHOOK_URL = 'https://082a-209-38-109-245.ngrok-free.app'

bot = telebot.TeleBot(BOT_CONFIG['token'])
app = Flask(__name__, static_folder='static')
app.register_blueprint(order_details_bp)  # ثبت Blueprint مسیرهای جزئیات سفارش

# تنظیمات logging — Docker-friendly: logs to stdout (captured by Docker)
import sys
logging.basicConfig(
    stream=sys.stdout,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# تنظیم ادمین
admin_config = AdminConfig()

# ایجاد دیتابیس
def setup_database():
    try:
        conn = sqlite3.connect(DB_CONFIG['users_db'])
        cursor = conn.cursor()

        # ایجاد جدول users اگر وجود ندارد
        cursor.execute('''CREATE TABLE IF NOT EXISTS users
            (user_id INTEGER PRIMARY KEY,
             balance INTEGER DEFAULT 0)''')

        # ایجاد جدول orders اگر وجود ندارد
        cursor.execute('''CREATE TABLE IF NOT EXISTS orders
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
             user_id INTEGER,
             phone_number TEXT,
             service TEXT,
             country TEXT,
             price INTEGER,
             order_id TEXT UNIQUE,
             status TEXT DEFAULT 'active',
             order_date DATETIME DEFAULT CURRENT_TIMESTAMP,
             FOREIGN KEY (user_id) REFERENCES users(user_id))''')

        conn.commit()
        conn.close()
        logging.info("✅ دیتابیس با موفقیت راه‌اندازی شد")
        return True
    except Exception as e:
        logging.error(f"❌ خطا در راه‌اندازی دیتابیس: {e}")
        return False

def setup_admin_database():
    try:
        conn = sqlite3.connect(DB_CONFIG['admin_db'])
        cursor = conn.cursor()
        
        # ایجاد جدول اطلاعات کارت
        cursor.execute('''CREATE TABLE IF NOT EXISTS card_info
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
             card_number TEXT,
             card_holder TEXT)''')
             
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Error in setup_admin_database: {e}")

# توابع مدیریت موجودی کاربر از database.py import شده‌اند (get_user_balance, add_balance)

# تابع جدید برای دریافت سرویس‌های موجود از hero-sms.com
def get_available_services():
    try:
        services = [
            "Telegram",
            "WhatsApp",
            "Instagram",
            "Facebook",
            "Twitter",
            "Viber",
            "WeChat",
            "Snapchat",
            "TikTok",
            "LinkedIn"
        ]
        logging.info(f"Retrieved {len(services)} services")
        return services
    except Exception as e:
        logging.error(f"Error in get_available_services: {e}")
        return []

# تابع جدید برای دریافت کشورهای موجود برای یک سرویس خاص
def get_countries_for_service(service):
    conn = sqlite3.connect('sms_bot.db')
    cursor = conn.cursor()
    
    # استفاده از المصدر الموحد (Single Source of Truth)
    if service in SERVICE_COUNTRIES:
        return [
            {'code': country[0], 'name': country[1]}
            for country in SERVICE_COUNTRIES[service]
        ]
    
    # در غیر این صورت، کشورهای پیش‌فرض یا همه کشورها را از دیتابیس برگردان
    try:
        cursor.execute("SELECT DISTINCT country_code, country_name FROM products WHERE service = ?", (service,))
        countries = [{'code': row[0], 'name': row[1]} for row in cursor.fetchall()]
        conn.close()
        return countries
    except Exception as e:
        logging.error(f"خطا در دریافت کشورها: {e}")
        conn.close()
        return []

# تابع دریافت قیمت‌ها از hero-sms.com (SMS-Activate Protocol)
def get_prices(product):
    """دریافت قیمت‌های یک سرویس از hero-sms.com"""
    try:
        service_code = SERVICE_CODE_MAP.get(product, product)
        params = {
            'api_key': HEROSMS_CONFIG['api_key'],
            'action': 'getPrices',
            'service': service_code
        }
        response = requests.get(
            HEROSMS_CONFIG['api_url'],
            params=params,
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"خطا در دریافت قیمت‌ها: {e}")
        return None

# تابع دریافت محصولات موجود از hero-sms.com (SMS-Activate Protocol)
def get_products(country='any', operator='any'):
    """دریافت وضعیت شماره‌های موجود"""
    try:
        params = {
            'api_key': HEROSMS_CONFIG['api_key'],
            'action': 'getNumbersStatus'
        }
        if country != 'any':
            country_id = COUNTRY_ID_MAP.get(country, country)
            params['country'] = country_id
        response = requests.get(
            HEROSMS_CONFIG['api_url'],
            params=params,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        logger.info(f"پاسخ API برای محصولات {country}/{operator}: {data}")
        return data
    except Exception as e:
        logger.error(f"خطا در دریافت محصولات: {e}")
        return None

# تنظیم وب‌هوک
@app.route('/', methods=['GET', 'POST'])
def webhook():
    logging.info(f"Received webhook request: {request.method}")
    if request.method == 'POST':
        logging.info(f"Webhook data: {request.get_data()}")
        try:
            json_str = request.get_data().decode('UTF-8')
            update = telebot.types.Update.de_json(json_str)
            bot.process_new_updates([update])
            return ''
        except Exception as e:
            print(f"خطا در پردازش webhook: {e}")
            return 'error', 500
    return 'OK'

# حذف تابع main_keyboard و جایگزینی با inline_main_keyboard
def inline_main_keyboard(user_id):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    # دکمه‌های اصلی (چند زبانه)
    keyboard.add(
        types.InlineKeyboardButton(get_text(user_id, 'main_menu.buy_number'), callback_data='buy_number'),
        types.InlineKeyboardButton(get_text(user_id, 'main_menu.balance'), callback_data='check_balance'),
        types.InlineKeyboardButton(get_text(user_id, 'main_menu.my_orders'), callback_data='my_orders'),
        types.InlineKeyboardButton(get_text(user_id, 'main_menu.help'), callback_data='help')
    )
    
    # اضافه کردن دکمه پنل مدیریت فقط برای ادمین
    if user_id in BOT_CONFIG['admin_ids']:
        keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'main_menu.admin_panel'), callback_data='admin_panel'))
    
    return keyboard

# نمایش سرویس‌های موجود
def services_keyboard(user_id):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    
    # سرویس‌های اصلی که دو به دو نمایش داده می‌شوند
    main_services = [
        ('telegram', 'telegram'),
        ('whatsapp', 'whatsapp'),
        ('instagram', 'instagram'),
        ('google', 'google')
    ]
    
    # اضافه کردن دکمه‌ها دو به دو
    for i in range(0, len(main_services), 2):
        buttons = []
        for j in range(2):
            if i + j < len(main_services):
                service_id, service_key = main_services[i + j]
                name = get_text(user_id, f'services.{service_key}')
                buttons.append(types.InlineKeyboardButton(name, callback_data=f'service_{service_id}'))
        keyboard.row(*buttons)
    
    # اضافه کردن دکمه برگشت به منوی اصلی
    keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_main'), callback_data="back_to_main"))
    
    return keyboard

# تغییر start handler
@bot.message_handler(commands=['start'])
def start_handler(message):
    try:
        user_id = message.from_user.id
        keyboard = inline_main_keyboard(user_id)
        
        welcome_text = get_text(user_id, 'welcome')

        bot.send_message(
            message.chat.id,
            welcome_text,
            reply_markup=keyboard
        )
        
    except Exception as e:
        logging.error(f"Error in start_handler: {e}")
        bot.reply_to(message, get_text(message.from_user.id, 'errors.general'))

# ── Language Selection ─────────────────────────────────────────
@bot.message_handler(commands=['language'])
def language_handler(message):
    user_id = message.from_user.id
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    for lang in get_user_language.__module__ and get_all_languages() if True else []:
        pass
    
    from i18n import get_all_languages
    for lang in get_all_languages():
        keyboard.add(types.InlineKeyboardButton(
            lang['name'],
            callback_data=f"setlang_{lang['code']}"
        ))
    
    keyboard.add(types.InlineKeyboardButton(
        get_text(user_id, 'navigation.back_to_main'),
        callback_data="back_to_main"
    ))
    
    bot.send_message(
        message.chat.id,
        get_text(user_id, 'language.select_title'),
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('setlang_'))
def handle_language_selection(call):
    user_id = call.from_user.id
    lang_code = call.data.split('_')[1]
    
    from i18n import set_user_language
    if set_user_language(user_id, lang_code):
        bot.answer_callback_query(call.id, get_text(user_id, 'language.selected'))
        # Refresh the main keyboard with new language
        bot.edit_message_text(
            get_text(user_id, 'welcome_back'),
            call.message.chat.id,
            call.message.message_id,
            reply_markup=inline_main_keyboard(user_id)
        )
    else:
        bot.answer_callback_query(call.id, get_text(user_id, 'errors.general_short'))

# اضافه کردن handler برای بررسی مجدد عضویت
@bot.callback_query_handler(func=lambda call: call.data == "check_membership")
def check_membership(call):
    try:
        user_id = call.from_user.id
        channels = admin_config.get_required_channels()
        if not channels:
            bot.edit_message_text(
                get_text(user_id, 'welcome_approved').split('\n')[0],
                call.message.chat.id,
                call.message.message_id,
                reply_markup=inline_main_keyboard(user_id)
            )
            return
            
        not_subscribed = []
        for channel in channels:
            try:
                member = bot.get_chat_member(f"@{channel[0]}", user_id)
                if member.status in ['left', 'kicked', 'restricted']:
                    channel_info = bot.get_chat(f"@{channel[0]}")
                    not_subscribed.append((
                        channel_info.title or channel[1],
                        channel[2]
                    ))
            except Exception as e:
                logger.error(f"خطا در بررسی عضویت کانال {channel[0]}: {e}")
                continue
        
        if not_subscribed:
            text = get_text(user_id, 'channels.membership_check')
            keyboard = types.InlineKeyboardMarkup(row_width=1)
            
            for channel_name, channel_link in not_subscribed:
                text += f"• {channel_name}\n"
                keyboard.add(types.InlineKeyboardButton(
                    get_text(user_id, 'channels.join_channel', channel=channel_name),
                    url=channel_link
                ))
            
            keyboard.add(types.InlineKeyboardButton(
                get_text(user_id, 'channels.check_again'),
                callback_data="check_membership"
            ))
            
            bot.edit_message_text(
                text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=keyboard
            )
        else:
            bot.edit_message_text(
                get_text(user_id, 'welcome_approved'),
                call.message.chat.id,
                call.message.message_id,
                reply_markup=inline_main_keyboard(user_id)
            )
            
    except Exception as e:
        logger.error(f"خطا در بررسی عضویت: {e}")
        bot.answer_callback_query(call.id, get_text(call.from_user.id, 'errors.general_short'))

# ایجاد نمونه از کلاس Wallet
wallet = Wallet()

# آپدیت تابع handle_main_menu برای بخش موجودی
@bot.callback_query_handler(func=lambda call: call.data in ['buy_number', 'check_balance', 'help', 'help_buy_number', 'help_charge', 'help_get_code', 'help_payment', 'help_delivery', 'help_cancel'])
def handle_main_menu(call):
    try:
        user_id = call.from_user.id
        
        if call.data == 'check_balance':
            balance = get_user_balance(user_id)
            keyboard = types.InlineKeyboardMarkup(row_width=1)
            keyboard.add(
                types.InlineKeyboardButton(get_text(user_id, 'main_menu.add_funds'), callback_data="add_funds"),
                types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_main'), callback_data="back_to_main")
            )
            
            message_text = get_text(user_id, 'wallet.title', balance=balance)
            bot.edit_message_text(
                message_text,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            return

        elif call.data == 'buy_number':
            bot.edit_message_text(
                get_text(user_id, 'services.select'),
                call.message.chat.id,
                call.message.message_id,
                reply_markup=services_keyboard(user_id)
            )
            
        elif call.data == 'help':
            keyboard = types.InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                types.InlineKeyboardButton(get_text(user_id, 'help.buy_number'), callback_data="help_buy_number"),
                types.InlineKeyboardButton(get_text(user_id, 'help.charge'), callback_data="help_charge"),
                types.InlineKeyboardButton(get_text(user_id, 'help.get_code'), callback_data="help_get_code"),
                types.InlineKeyboardButton(get_text(user_id, 'help.payment_methods'), callback_data="help_payment"),
                types.InlineKeyboardButton(get_text(user_id, 'help.delivery_time'), callback_data="help_delivery"),
                types.InlineKeyboardButton(get_text(user_id, 'help.cancel_order'), callback_data="help_cancel"),
                types.InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="back_to_main")
            )
            bot.edit_message_text(
                get_text(user_id, 'help.title'),
                call.message.chat.id,
                call.message.message_id,
                reply_markup=keyboard
            )
            
        elif call.data == "help_buy_number":
            answer = get_text(user_id, 'help.buy_number_answer')
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_help'), callback_data="help"))
            bot.edit_message_text(answer, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
            
        elif call.data == "help_charge":
            answer = get_text(user_id, 'help.charge_answer')
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_help'), callback_data="help"))
            bot.edit_message_text(answer, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
            
        elif call.data == "help_get_code":
            answer = get_text(user_id, 'help.get_code_answer')
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_help'), callback_data="help"))
            bot.edit_message_text(answer, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
            
        elif call.data == "help_payment":
            answer = get_text(user_id, 'help.payment_methods_answer')
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_help'), callback_data="help"))
            bot.edit_message_text(answer, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
            
        elif call.data == "help_delivery":
            answer = get_text(user_id, 'help.delivery_time_answer')
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_help'), callback_data="help"))
            bot.edit_message_text(answer, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
            
        elif call.data == "help_cancel":
            answer = get_text(user_id, 'help.cancel_order_answer')
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_help'), callback_data="help"))
            bot.edit_message_text(answer, call.message.chat.id, call.message.message_id, reply_markup=keyboard)

    except Exception as e:
        logging.error(f"Error in handle_main_menu: {e}")
        bot.answer_callback_query(call.id, get_text(call.from_user.id, 'errors.general'))

@bot.callback_query_handler(func=lambda call: call.data == "back_to_main")
def back_to_main_menu(call):
    bot.edit_message_text(
        get_text(call.from_user.id, 'welcome_back'),
        call.message.chat.id,
        call.message.message_id,
        reply_markup=inline_main_keyboard(call.from_user.id)
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('service_'))
def handle_service_selection(call):
    try:
        user_id = call.from_user.id
        service = call.data.split('_')[1]
        products = get_products()
        
        if not products:
            bot.answer_callback_query(call.id, get_text(user_id, 'services.error_fetch'))
            return
            
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        
        # استفاده از المصدر الموحد (Single Source of Truth)
        countries = _get_countries_for_service(service)
        
        # نمایش کشورها دو به دو
        for i in range(0, len(countries), 2):
            buttons = []
            for j in range(2):
                if i + j < len(countries):
                    country_code = countries[i + j]
                    country_name = get_text(user_id, f'countries.{country_code}')
                    buttons.append(types.InlineKeyboardButton(country_name, callback_data=f'country_{service}_{country_code}'))
            keyboard.row(*buttons)
        
        # اضافه کردن دکمه برگشت به لیست سرویس‌ها
        keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_services'), callback_data="back_to_services"))
        
        bot.edit_message_text(
            get_text(user_id, 'countries.select', service=service),
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"خطا در پردازش انتخاب سرویس: {e}", exc_info=True)
        bot.answer_callback_query(call.id, get_text(call.from_user.id, 'errors.general'))

currency_service = CurrencyService()

def create_required_tables():
    try:
        conn = sqlite3.connect('bot.db')
        cursor = conn.cursor()
        
        # ایجاد جدول settings
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        ''')
        
        # تنظیمات پیش‌فرض
        default_settings = [
            ('usd_rate', '60000'),  # نرخ پیش‌فرض دلار به تومان
            ('profit_percentage', '30'),  # درصد سود پیش‌فرض
        ]
        
        # اضافه کردن تنظیمات پیش‌فرض
        cursor.executemany('''
            INSERT OR IGNORE INTO settings (key, value)
            VALUES (?, ?)
        ''', default_settings)
        
        # ایجاد جدول سفارش‌ها
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY,
                phone_number TEXT,
                service TEXT,
                country TEXT,
                operator TEXT,
                price INTEGER,
                status TEXT,
                date DATETIME,
                user_id INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # ایجاد جدول کدهای فعال‌سازی
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activation_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER,
                code TEXT,
                status TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES orders(id)
            )
        """)
        
        conn.commit()
        conn.close()
        logging.info("Required tables created successfully")
        
    except Exception as e:
        logging.error(f"Error creating required tables: {e}")
        raise

def get_price_for_operator(country, product, operator):
    try:
        conn = sqlite3.connect('bot.db')
        cursor = conn.cursor()
        
        # اول مطمئن شویم که جدول settings وجود دارد
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        ''')
        
        # بررسی وجود تنظیمات پیش‌فرض
        cursor.execute('SELECT COUNT(*) FROM settings')
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO settings (key, value) VALUES
                ("usd_rate", "60000"),
                ("profit_percentage", "20")
            ''')
            conn.commit()
        
        # دریافت نرخ دلار و درصد سود
        cursor.execute('SELECT value FROM settings WHERE key = "usd_rate"')
        usd_rate = float(cursor.fetchone()[0]) if usd_rate_result else 0
        
        cursor.execute('SELECT value FROM settings WHERE key = "profit_percentage"')
        profit_percentage = float(cursor.fetchone()[0]) if profit_result else 0
        
        # دریافت قیمت پایه
        base_price = get_prices(product)
        if not base_price:
            logging.error(f"No base price found for product {product}")
            return None
            
        # محاسبه قیمت نهایی
        final_price = base_price * usd_rate * (1 + profit_percentage/100)

        logging.info(f"Price calculation successful: base={base_price}, rate={usd_rate}, profit={profit_percentage}%")
        return round(final_price, 2)
        
    except sqlite3.Error as e:
        logging.error(f"Database error in price calculation: {e}")
        return None
    except Exception as e:
        logging.error(f"General error in price calculation: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_current_usd_rate():
    try:
        # همیشه از مقدار ذخیره شده در دیتابیس استفاده می‌کنیم
        conn = sqlite3.connect('admin.db')  # استفاده از admin.db به جای bot.db
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key='usd_rate'")
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return float(result[0])
        else:
            logging.error("نرخ دلار در دیتابیس یافت نشد")
            return 0  # برگرداندن صفر در صورت عدم وجود مقدار
    except Exception as e:
        logging.error(f"خطا در دریافت نرخ دلار از دیتابیس: {e}")
        return 0  # برگرداندن صفر در صورت بروز خطا

def ensure_settings_table_exists():
    try:
        conn = sqlite3.connect('bot.db')
        cursor = conn.cursor()
        
        # بررسی وجود جدول
        cursor.execute(''' SELECT count(name) FROM sqlite_master WHERE type='table' AND name='settings' ''')
        
        # اگر جدول وجود نداشت، آن را بساز
        if cursor.fetchone()[0] == 0:
            create_required_tables()
            logging.info("Settings table created")
        
        conn.close()
        return True
        
    except Exception as e:
        logging.error(f"Error checking settings table: {e}")
        return False

# در ابتدای فایل، این import را اضافه کنید
from operator_config import OperatorConfig

# یک نمونه از کلاس OperatorConfig ایجاد کنید
operator_config = OperatorConfig()

@bot.callback_query_handler(func=lambda call: call.data.startswith('country_'))
def handle_country_selection(call):
    try:
        user_id = call.from_user.id
        
        # اطمینان از وجود جدول settings
        ensure_settings_table_exists()
        
        parts = call.data.split('_')
        service = parts[1]
        country = parts[2]
        
        # دریافت اطلاعات اپراتور از تنظیمات
        operator, country_name = operator_config.get_operator_info(service, country)
        
        # اگر کشور در تنظیمات یافت نشد، از ترجمه استفاده کنیم
        if not country_name:
            country_name = get_text(user_id, f'countries.{country}')
        
        # اگر اپراتور تعریف نشده باشد، از مقدار پیش‌فرض استفاده کنیم
        if not operator:
            operator = "virtual4"  # اپراتور پیش‌فرض
            logging.warning(f"هیچ اپراتوری برای {service} در {country} تعریف نشده. از اپراتور پیش‌فرض استفاده می‌شود.")
        
        # دریافت قیمت سرویس برای این کشور از hero-sms.com
        country_id = COUNTRY_ID_MAP.get(country, country)
        service_code = SERVICE_CODE_MAP.get(service, service)
        
        params = {
            'api_key': HEROSMS_CONFIG['api_key'],
            'action': 'getPrices',
            'country': country_id,
            'service': service_code
        }
        
        response = requests.get(
            HEROSMS_CONFIG['api_url'],
            params=params,
            timeout=10
        )
        
        price_info = {
            'price_usd': 0,
            'price_toman': 0,
            'available_count': 0,
            'operator': operator
        }
        
        price_text = ""
        
        if response.status_code == 200:
            data = response.json()
            
            if country_id in data and service_code in data[country_id]:
                operators_data = data[country_id][service_code]
                
                # بررسی آیا اپراتور تعریف شده موجود است
                if operator in operators_data and operators_data[operator]['count'] > 0:
                    operator_data = operators_data[operator]
                    price = operator_data['cost']
                    available_count = operator_data['count']
                else:
                    # اگر اپراتور تعریف شده موجود نیست، کمترین قیمت را پیدا کنیم
                    min_price = float('inf')
                    price = 0
                    available_count = 0
                    
                    for op_name, op_data in operators_data.items():
                        if op_data['count'] > 0 and op_data['cost'] < min_price:
                            min_price = op_data['cost']
                            price = min_price
                            available_count = op_data['count']
                            price_info['operator'] = op_name
                            
                    if min_price == float('inf'):
                        logging.warning(f"هیچ اپراتوری با موجودی برای {service} در {country} یافت نشد.")
                        price = 0
                        available_count = 0
                
                if price > 0:
                    # دریافت نرخ دلار و درصد سود از دیتابیس
                    conn = sqlite3.connect('admin.db')
                    cursor = conn.cursor()
                    
                    cursor.execute('SELECT value FROM settings WHERE key = "usd_rate"')
                    usd_rate_result = cursor.fetchone()
                    usd_rate = float(usd_rate_result[0]) if usd_rate_result else 0
                    
                    cursor.execute('SELECT value FROM settings WHERE key = "profit_percentage"')
                    profit_result = cursor.fetchone()
                    profit_percentage = float(profit_result[0]) if profit_result else 0
                    
                    conn.close()
                    
                    # محاسبه قیمت نهایی
                    price_info['price_usd'] = price
                    price_info['price_toman'] = round(price * usd_rate * (1 + profit_percentage/100))
                    price_info['available_count'] = available_count
                    
                    price_text = get_text(user_id, 'purchase.price_line',
                        price=price_info['price_toman'],
                        count=price_info['available_count'],
                        operator=price_info['operator'])
                    
                    logging.info(f"""
                    محاسبه قیمت برای {country}:
                    اپراتور: {price_info['operator']}
                    قیمت پایه (دلار): {price}
                    نرخ دلار: {usd_rate}
                    درصد سود: {profit_percentage}%
                    قیمت نهایی (تومان): {price_info['price_toman']}
                    تعداد موجود: {available_count}
                    """)
        
        # ایجاد کیبورد
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        
        if price_info['available_count'] > 0:
            # دکمه خرید با اپراتور مشخص شده
            keyboard.add(types.InlineKeyboardButton(
                get_text(user_id, 'purchase.buy_button', operator=price_info['operator']),
                callback_data=f"buy_number_{service}_{country}_{price_info['operator']}"
            ))
        else:
            # اگر موجودی نداریم، پیغام خطا نمایش دهیم
            keyboard.add(types.InlineKeyboardButton(
                get_text(user_id, 'purchase.unavailable'),
                callback_data="no_operator"
            ))
        
        keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_services'), callback_data="back_to_services"))
        
        # متن پیام
        message_text = get_text(user_id, 'countries.selected', country=country_name, service=service)
        if price_text:
            message_text += f"\n\n{price_text}"
        message_text += f"\n\n{get_text(user_id, 'purchase.buy_prompt')}"
        
        bot.edit_message_text(
            message_text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard
        )
        
    except Exception as e:
        logging.error(f"Error in handle_country_selection: {e}")
        bot.answer_callback_query(call.id, get_text(call.from_user.id, 'errors.general_short'))
        bot.send_message(call.message.chat.id, get_text(call.from_user.id, 'errors.general'))

@bot.callback_query_handler(func=lambda call: call.data == "back_to_services")
def back_to_services(call):
    bot.edit_message_text(
        get_text(call.from_user.id, 'services.select'),
        call.message.chat.id,
        call.message.message_id,
        reply_markup=services_keyboard(call.from_user.id)
    )

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    try:
        # پردازش پیام
        pass
    except Exception as e:
        bot.reply_to(message, get_text(message.from_user.id, 'errors.general'))
        print(f"خطای کلی: {e}")

# تغییر در تابع admin_panel
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id not in BOT_CONFIG['admin_ids']:
        return
    
    user_id = message.from_user.id
    
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton(get_text(user_id, 'admin.stats'), callback_data="admin_stats"),
        types.InlineKeyboardButton(get_text(user_id, 'admin.set_profit'), callback_data="set_profit"),
        types.InlineKeyboardButton(get_text(user_id, 'admin.set_usd_rate'), callback_data="set_usd_rate"),
        types.InlineKeyboardButton(get_text(user_id, 'admin.manage_channels'), callback_data="manage_channels"),
        types.InlineKeyboardButton(get_text(user_id, 'admin.transactions'), callback_data="transactions"),
        types.InlineKeyboardButton(get_text(user_id, 'admin.manage_users'), callback_data="manage_users"),
        types.InlineKeyboardButton(get_text(user_id, 'admin.operator_settings'), callback_data="operator_settings"),
        types.InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="back_to_main")
    )
    
    bot.send_message(
        message.chat.id,
        get_text(user_id, 'admin.panel_welcome'),
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: call.data == "admin_stats")
def handle_admin_stats(call):
    user_id = call.from_user.id
    if user_id not in BOT_CONFIG['admin_ids']:
        bot.answer_callback_query(call.id, get_text(user_id, 'errors.no_access'))
        return

    try:
        # اتصال به دیتابیس کاربران
        users_conn = sqlite3.connect(DB_CONFIG['users_db'])
        users_cursor = users_conn.cursor()
        
        # تعداد کل کاربران
        users_cursor.execute('SELECT COUNT(DISTINCT user_id) FROM users')
        total_users = users_cursor.fetchone()[0]
        users_conn.close()
        
        # اتصال به دیتابیس ربات
        bot_conn = sqlite3.connect('bot.db')
        bot_cursor = bot_conn.cursor()
        
        # دریافت نرخ فعلی دلار
        current_rate = get_current_usd_rate()
        
        # دریافت درصد سود از جدول settings
        admin_conn = sqlite3.connect('admin.db')
        admin_cursor = admin_conn.cursor()
        admin_cursor.execute('SELECT value FROM settings WHERE key = "profit_percentage"')
        profit_percentage = float(admin_cursor.fetchone()[0] or 30)
        admin_conn.close()
        
        # محاسبه درآمدها از جدول orders
        # درآمد امروز
        bot_cursor.execute('''
            SELECT COALESCE(SUM(price), 0) FROM orders
            WHERE date(created_at) = date('now')
        ''')
        today_total = bot_cursor.fetchone()[0] or 0
        today_income = int(today_total - (today_total / (1 + profit_percentage/100)))
        
        # درآمد هفته
        bot_cursor.execute('''
            SELECT COALESCE(SUM(price), 0) FROM orders
            WHERE date(created_at) >= date('now', '-7 days')
        ''')
        week_total = bot_cursor.fetchone()[0] or 0
        week_income = int(week_total - (week_total / (1 + profit_percentage/100)))
        
        # درآمد ماه
        bot_cursor.execute('''
            SELECT COALESCE(SUM(price), 0) FROM orders
            WHERE date(created_at) >= date('now', '-30 days')
        ''')
        month_total = bot_cursor.fetchone()[0] or 0
        month_income = int(month_total - (month_total / (1 + profit_percentage/100)))
        
        bot_conn.close()
        
        # ایجاد کیبورد
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        
        # ردیف اول: تعداد کاربران
        keyboard.add(
            types.InlineKeyboardButton(f"{total_users:,}", callback_data="show_users"),
            types.InlineKeyboardButton(get_text(user_id, 'admin.total_users'), callback_data="show_users")
        )
        
        # ردیف دوم: نرخ دلار
        keyboard.add(
            types.InlineKeyboardButton(f"{current_rate:,}", callback_data="show_rate"),
            types.InlineKeyboardButton(get_text(user_id, 'admin.ruble_label'), callback_data="show_rate")
        )
        
        # ردیف سوم: درآمد امروز
        keyboard.add(
            types.InlineKeyboardButton(f"{today_income:,}", callback_data="today_income"),
            types.InlineKeyboardButton(get_text(user_id, 'admin.today_income'), callback_data="today_income")
        )
        
        # ردیف چهارم: درآمد هفتگی
        keyboard.add(
            types.InlineKeyboardButton(f"{week_income:,}", callback_data="week_income"),
            types.InlineKeyboardButton(get_text(user_id, 'admin.week_income'), callback_data="week_income")
        )
        
        # ردیف پنجم: درآمد ماهانه
        keyboard.add(
            types.InlineKeyboardButton(f"{month_income:,}", callback_data="month_income"),
            types.InlineKeyboardButton(get_text(user_id, 'admin.month_income'), callback_data="month_income")
        )
        
        # ردیف ششم: بروزرسانی نرخ دلار
        keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'admin.update_rate'), callback_data="update_rate"))
        
        # ردیف هفتم: بازگشت
        keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_admin'), callback_data="admin_panel"))
        
        # ارسال پیام با آمار
        bot.edit_message_text(
            get_text(user_id, 'admin.stats_title'),
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard
        )
        
    except Exception as e:
        logging.error(f"Error in handle_admin_stats: {e}")
        bot.answer_callback_query(call.id, get_text(call.from_user.id, 'errors.stats_error'))

@bot.callback_query_handler(func=lambda call: call.data == "update_rate")
def update_currency_rate(call):
    user_id = call.from_user.id
    if user_id not in BOT_CONFIG['admin_ids']:
        return
        
    current_rate = currency_service.get_usd_rate()
    if current_rate:
        admin_config.set_usd_rate(current_rate)
        bot.answer_callback_query(call.id, get_text(user_id, 'admin.rate_updated'))
        handle_admin_stats(call)
    else:
        bot.answer_callback_query(call.id, get_text(user_id, 'admin.rate_update_error'))

@bot.callback_query_handler(func=lambda call: call.data == "admin_panel")
def handle_admin_panel_button(call):
    user_id = call.from_user.id
    if user_id not in BOT_CONFIG['admin_ids']:
        bot.answer_callback_query(call.id, get_text(user_id, 'errors.no_access'))
        return

    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton(get_text(user_id, 'admin.stats_short'), callback_data="admin_stats"),
        types.InlineKeyboardButton(get_text(user_id, 'admin.manage_users'), callback_data="manage_users"),
        types.InlineKeyboardButton(get_text(user_id, 'admin.broadcast'), callback_data="broadcast_message"),
        types.InlineKeyboardButton(get_text(user_id, 'admin.set_profit'), callback_data="set_profit"),
        types.InlineKeyboardButton(get_text(user_id, 'admin.set_card'), callback_data="set_card"),
        types.InlineKeyboardButton(get_text(user_id, 'admin.set_usd_rate'), callback_data="set_usd_rate"),
        types.InlineKeyboardButton(get_text(user_id, 'admin.transactions'), callback_data="transactions"),
        types.InlineKeyboardButton(get_text(user_id, 'admin.toggle_lock'), callback_data="toggle_lock"),
        types.InlineKeyboardButton(get_text(user_id, 'admin.operator_settings'), callback_data="operator_settings"),
        types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_main'), callback_data="back_to_main")
    )
    
    bot.edit_message_text(
        get_text(user_id, 'admin.panel_title'),
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: call.data == "set_card")
def handle_set_card(call):
    user_id = call.from_user.id
    if user_id not in BOT_CONFIG['admin_ids']:
        bot.answer_callback_query(call.id, get_text(user_id, 'errors.no_access'))
        return
        
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton(get_text(user_id, 'payment.new_card'), callback_data="new_card"),
        types.InlineKeyboardButton(get_text(user_id, 'payment.check_card_info'), callback_data="check_card_info"),
        types.InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="admin_panel")
    )
    
    bot.edit_message_text(
        get_text(user_id, 'payment.card_management'),
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: call.data == "manage_users")
def handle_manage_users(call):
    try:
        user_id = call.from_user.id
        if user_id not in BOT_CONFIG['admin_ids']:
            bot.answer_callback_query(call.id, get_text(user_id, 'errors.no_access_section'))
            return
            
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            types.InlineKeyboardButton(get_text(user_id, 'admin.users_list_title')[:20], callback_data="users_list"),
            types.InlineKeyboardButton(get_text(user_id, 'admin.user_search'), callback_data="search_user"),
            types.InlineKeyboardButton(get_text(user_id, 'admin.broadcast'), callback_data="broadcast_message"),
            types.InlineKeyboardButton(get_text(user_id, 'admin.group_discount'), callback_data="group_discount")
        )
        keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="admin_panel"))
        
        bot.edit_message_text(
            get_text(user_id, 'admin.users_section_title'),
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard
        )
        
    except Exception as e:
        logging.error(f"Error in handle_manage_users: {e}")
        bot.answer_callback_query(call.id, get_text(call.from_user.id, 'errors.general'))
        print(f"Error in handle_manage_users: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "users_list")
def handle_users_list(call):
    try:
        user_id = call.from_user.id
        if user_id not in BOT_CONFIG['admin_ids']:
            bot.answer_callback_query(call.id, get_text(user_id, 'errors.no_access_section'))
            return
            
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT user_id, balance
            FROM users
            ORDER BY user_id DESC
            LIMIT 10
        ''')
        users = cursor.fetchall()
        conn.close()
        
        if not users:
            text = get_text(user_id, 'admin.users_list_empty')
        else:
            text = get_text(user_id, 'admin.users_list_title')
            for user in users:
                text += f"🆔 ID: {user[0]}\n"
                text += f"💰 {get_text(user_id, 'common.toman')}: {user[1]:,}\n"
                text += "➖➖➖➖➖➖➖➖\n"
        
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            types.InlineKeyboardButton(get_text(user_id, 'user_menu.prev_page'), callback_data="users_prev_page"),
            types.InlineKeyboardButton(get_text(user_id, 'user_menu.next_page'), callback_data="users_next_page")
        )
        keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_users'), callback_data="manage_users"))
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard
        )
    except Exception as e:
        logging.error(f"Error in users_list: {e}")
        bot.answer_callback_query(call.id, get_text(call.from_user.id, 'errors.list_error'))
        print(f"Error in users_list: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "search_user")
def handle_search_user(call):
    user_id = call.from_user.id
    if user_id not in BOT_CONFIG['admin_ids']:
        return
        
    msg = bot.edit_message_text(
        get_text(user_id, 'admin.search_user_prompt'),
        call.message.chat.id,
        call.message.message_id
    )
    bot.register_next_step_handler(msg, process_user_search)

def process_user_search(message):
    user_id = message.from_user.id
    if user_id not in BOT_CONFIG['admin_ids']:
        return
        
    try:
        search_term = message.text.strip()
        if not search_term.isdigit():
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.search_again'), callback_data="search_user"))
            keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_users'), callback_data="manage_users"))
            bot.reply_to(message, get_text(user_id, 'admin.search_user_invalid'), reply_markup=keyboard)
            return
            
        target_id = int(search_term)
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT user_id, balance FROM users WHERE user_id = ?', (target_id,))
        
        user = cursor.fetchone()
        conn.close()
        
        if user:
            keyboard = types.InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                types.InlineKeyboardButton(get_text(user_id, 'admin.modify_balance'), callback_data=f"modify_balance_{user[0]}"),
                types.InlineKeyboardButton(get_text(user_id, 'admin.send_message'), callback_data=f"send_message_{user[0]}")
            )
            keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_users'), callback_data="manage_users"))
            
            text = get_text(user_id, 'admin.search_user_found', user_id=user[0], balance=user[1])
            
            bot.reply_to(message, text, reply_markup=keyboard)
        else:
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.search_again'), callback_data="search_user"))
            keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_users'), callback_data="manage_users"))
            bot.reply_to(message, get_text(user_id, 'admin.search_user_not_found'), reply_markup=keyboard)
            
    except Exception as e:
        logging.error(f"Error in process_user_search: {e}")
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_users'), callback_data="manage_users"))
        bot.reply_to(message, get_text(user_id, 'errors.search_error'), reply_markup=keyboard)
        print(f"Error in process_user_search: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('modify_balance_'))
def handle_modify_balance(call):
    user_id = call.from_user.id
    if user_id not in BOT_CONFIG['admin_ids']:
        return
        
    target_id = call.data.split('_')[2]
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton(get_text(user_id, 'admin.add_balance_btn'), callback_data=f"add_balance_{target_id}"),
        types.InlineKeyboardButton(get_text(user_id, 'admin.reduce_balance_btn'), callback_data=f"reduce_balance_{target_id}")
    )
    keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_search'), callback_data=f"search_user"))
    
    bot.edit_message_text(
        get_text(user_id, 'admin.select_balance_action'),
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith(('add_balance_', 'reduce_balance_')))
def handle_balance_amount(call):
    user_id = call.from_user.id
    if user_id not in BOT_CONFIG['admin_ids']:
        return
        
    parts = call.data.split('_')
    action = parts[0]
    target_id = parts[2]
    
    msg = bot.edit_message_text(
        get_text(user_id, 'admin.enter_amount_prompt'),
        call.message.chat.id,
        call.message.message_id
    )
    bot.register_next_step_handler(msg, process_balance_change, action, target_id)

def process_balance_change(message, action, target_id):
    admin_id = message.from_user.id
    try:
        if admin_id not in BOT_CONFIG['admin_ids']:
            return
            
        amount = int(message.text.strip().replace(',', ''))
        if amount <= 0:
            raise ValueError(get_text(admin_id, 'admin.amount_must_be_positive'))
            
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT balance FROM users WHERE user_id = ?', (target_id,))
        current_balance = cursor.fetchone()
        
        if current_balance is None:
            bot.reply_to(message, get_text(admin_id, 'admin.user_not_found_db'))
            return
            
        current_balance = current_balance[0]
        
        if action == "add":
            new_balance = current_balance + amount
        else:
            if current_balance < amount:
                bot.reply_to(message, get_text(admin_id, 'admin.insufficient_balance_admin'))
                return
            new_balance = current_balance - amount
        
        cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (new_balance, target_id))
        conn.commit()
        conn.close()
        
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(get_text(admin_id, 'navigation.back_to_search'), callback_data="search_user"))
        
        try:
            polarity_text = get_text(admin_id, 'admin.balance_added') if action == 'add' else get_text(admin_id, 'admin.balance_reduced')
            bot.send_message(
                target_id,
                get_text(admin_id, 'admin.balance_changed', polarity=polarity_text, amount=amount, balance=new_balance)
            )
        except Exception as e:
            print(f"Error sending message to user: {e}")
            
        action_text = get_text(admin_id, 'admin.balance_added') if action == 'add' else get_text(admin_id, 'admin.balance_reduced')
        bot.reply_to(
            message,
            get_text(admin_id, 'admin.balance_admin_confirm', action=action_text, balance=new_balance),
            reply_markup=keyboard
        )
        
    except ValueError as e:
        bot.reply_to(message, str(e))
    except Exception as e:
        logging.error(f"Error in process_balance_change: {e}")
        print(f"Error in process_balance_change: {e}")
        bot.reply_to(message, get_text(admin_id if 'admin_id' in dir() else message.from_user.id, 'errors.general_short'))

@bot.callback_query_handler(func=lambda call: call.data == "broadcast_message")
def handle_broadcast(call):
    user_id = call.from_user.id
    if user_id not in BOT_CONFIG['admin_ids']:
        return
        
    msg = bot.edit_message_text(
        get_text(user_id, 'admin.broadcast_prompt'),
        call.message.chat.id,
        call.message.message_id
    )
    bot.register_next_step_handler(msg, process_broadcast)

def process_broadcast(message):
    if message.from_user.id not in BOT_CONFIG['admin_ids']:
        return
        
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users')
        users = cursor.fetchall()
        conn.close()
        
        success = 0
        failed = 0
        
        for user in users:
            try:
                bot.send_message(user[0], get_text(message.from_user.id, 'admin.broadcast_from_admin', message=message.text))
                success += 1
            except Exception as e:
                print(f"Error sending message to user {user[0]}: {e}")
                failed += 1
                
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(get_text(message.from_user.id, 'navigation.back_to_users'), callback_data="manage_users"))
        
        bot.reply_to(
            message,
            get_text(message.from_user.id, 'admin.broadcast_sent', success=success, failed=failed, total=success+failed),
            reply_markup=keyboard
        )
        
    except Exception as e:
        logging.error(f"Error in process_broadcast: {e}")
        print(f"Error in process_broadcast: {e}")
        
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(get_text(message.from_user.id, 'navigation.back_to_users'), callback_data="manage_users"))
        
        bot.reply_to(
            message,
            get_text(message.from_user.id, 'admin.broadcast_error'),
            reply_markup=keyboard
        )

# هندلر تنظیم درصد سود
@bot.callback_query_handler(func=lambda call: call.data == "set_profit")
def handle_set_profit(call):
    try:
        user_id = call.from_user.id
        if user_id not in BOT_CONFIG['admin_ids']:
            bot.answer_callback_query(call.id, get_text(user_id, 'errors.no_access_section'))
            return
            
        conn = sqlite3.connect('admin.db')
        cursor = conn.cursor()
        cursor.execute('SELECT value FROM settings WHERE key = "profit_percentage"')
        current_profit = cursor.fetchone()
        conn.close()
        
        current_profit = float(current_profit[0]) if current_profit else 0
            
        msg = bot.edit_message_text(
            get_text(user_id, 'admin.profit_current', profit=current_profit),
            call.message.chat.id,
            call.message.message_id
        )
        bot.register_next_step_handler(msg, process_profit_percentage)
    except Exception as e:
        logging.error(f"Error in set_profit: {e}")
        bot.answer_callback_query(call.id, get_text(call.from_user.id, 'errors.general_short'))

def process_profit_percentage(message):
    admin_id = message.from_user.id
    try:
        try:
            profit = float(message.text.strip().replace(',', ''))
        except ValueError:
            bot.reply_to(message, get_text(admin_id, 'admin.profit_invalid'))
            return
            
        if profit < 0:
            bot.reply_to(message, get_text(admin_id, 'admin.profit_negative'))
            return
            
        conn = sqlite3.connect('admin.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT value FROM settings WHERE key = "profit_percentage"')
        if cursor.fetchone() is None:
            cursor.execute('INSERT INTO settings (key, value) VALUES (?, ?)', ('profit_percentage', str(profit)))
        else:
            cursor.execute('UPDATE settings SET value = ? WHERE key = "profit_percentage"', (str(profit),))
        
        conn.commit()
        conn.close()
        
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            types.InlineKeyboardButton(get_text(admin_id, 'navigation.set_again'), callback_data="set_profit"),
            types.InlineKeyboardButton(get_text(admin_id, 'navigation.back_to_panel'), callback_data="admin_panel")
        )
        
        bot.reply_to(
            message,
            get_text(admin_id, 'admin.profit_saved', profit=profit),
            reply_markup=keyboard
        )
        
    except Exception as e:
        logging.error(f"Error in process_profit_percentage: {e}")
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(get_text(message.from_user.id, 'navigation.back_to_panel'), callback_data="admin_panel"))
        bot.reply_to(message, get_text(message.from_user.id, 'errors.general_short'), reply_markup=keyboard)

# هندلر تنظیم نرخ دلار
@bot.callback_query_handler(func=lambda call: call.data == "set_usd_rate")
def handle_set_usd_rate(call):
    try:
        user_id = call.from_user.id
        if user_id not in BOT_CONFIG['admin_ids']:
            bot.answer_callback_query(call.id, get_text(user_id, 'errors.no_access_section'))
            return
            
        msg = bot.edit_message_text(
            get_text(user_id, 'admin.ruble_current'),
            call.message.chat.id,
            call.message.message_id
        )
        bot.register_next_step_handler(msg, process_usd_rate)
    except Exception as e:
        logging.error(f"Error in set_usd_rate: {e}")
        bot.answer_callback_query(call.id, get_text(call.from_user.id, 'errors.general_short'))

def process_usd_rate(message):
    admin_id = message.from_user.id
    try:
        if not message.text.replace('.', '').isdigit():
            bot.reply_to(message, get_text(admin_id, 'admin.ruble_invalid'))
            return
            
        rate = float(message.text)
        conn = sqlite3.connect('admin.db')
        cursor = conn.cursor()
        cursor.execute('UPDATE settings SET value = ? WHERE key = "usd_rate"', (rate,))
        conn.commit()
        conn.close()
        
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(get_text(admin_id, 'navigation.back_to_panel'), callback_data="admin_panel"))
        
        bot.reply_to(
            message,
            get_text(admin_id, 'admin.ruble_saved', rate=rate),
            reply_markup=keyboard
        )
    except Exception as e:
        logging.error(f"Error in process_usd_rate: {e}")
        bot.reply_to(message, get_text(message.from_user.id, 'errors.general_short'))

# هندلر نمایش تراکنش‌ها
@bot.callback_query_handler(func=lambda call: call.data == "transactions")
def handle_transactions(call):
    try:
        user_id = call.from_user.id
        if user_id not in BOT_CONFIG['admin_ids']:
            bot.answer_callback_query(call.id, get_text(user_id, 'errors.no_access_section'))
            return
            
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT cp.payment_id, cp.user_id, cp.amount, cp.status, cp.created_at
            FROM card_payments cp
            ORDER BY cp.created_at DESC
            LIMIT 5
        ''')
        transactions = cursor.fetchall()
        conn.close()
        
        if not transactions:
            text = get_text(user_id, 'transactions.empty')
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="admin_panel"))
        else:
            text = get_text(user_id, 'transactions.recent_title', page=1)
            for t in transactions:
                status_emoji = get_text(user_id, 'transactions.status_pending') if t[3] == 'pending' else get_text(user_id, 'transactions.status_approved') if t[3] == 'approved' else get_text(user_id, 'transactions.status_rejected')
                text += f"🆔 Payment ID: {t[0]}\n"
                text += f"👤 User: {t[1]}\n"
                text += f"💰 Amount: {t[2]:,}\n"
                text += f"📝 Status: {status_emoji} {t[3]}\n"
                text += f"🕒 Date: {t[4]}\n"
                text += "➖➖➖➖➖➖➖➖\n"
            
            keyboard = types.InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                types.InlineKeyboardButton(get_text(user_id, 'transactions.prev_page'), callback_data="transactions_prev"),
                types.InlineKeyboardButton(get_text(user_id, 'transactions.next_page'), callback_data="transactions_next")
            )
            keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="admin_panel"))
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard
        )
    except Exception as e:
        logging.error(f"Error in transactions: {e}")
        print(f"Error in transactions: {e}")
        bot.answer_callback_query(call.id, get_text(call.from_user.id, 'errors.general_short'))

# هندلر تغییر صفحه تراکنش‌ها
@bot.callback_query_handler(func=lambda call: call.data.startswith('transactions_'))
def handle_transactions_pagination(call):
    try:
        user_id = call.from_user.id
        if user_id not in BOT_CONFIG['admin_ids']:
            bot.answer_callback_query(call.id, get_text(user_id, 'errors.no_access_section'))
            return
            
        action = call.data.split('_')[1]
        # Parse page number - more robust
        import re
        match = re.search(r'\(Page (\d+)\)', call.message.text)
        if match:
            current_page = int(match.group(1))
        else:
            current_page = 1
        
        if action == 'prev' and current_page > 1:
            page = current_page - 1
        elif action == 'next':
            page = current_page + 1
        else:
            bot.answer_callback_query(call.id, get_text(user_id, 'transactions.invalid_page'))
            return
            
        offset = (page - 1) * 5
        
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT cp.payment_id, cp.user_id, cp.amount, cp.status, cp.created_at
            FROM card_payments cp
            ORDER BY cp.created_at DESC
            LIMIT 5 OFFSET ?
        ''', (offset,))
        transactions = cursor.fetchall()
        conn.close()
        
        if not transactions:
            text = get_text(user_id, 'transactions.no_page')
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="admin_panel"))
        else:
            text = get_text(user_id, 'transactions.recent_title', page=page)
            for t in transactions:
                status_emoji = get_text(user_id, 'transactions.status_pending') if t[3] == 'pending' else get_text(user_id, 'transactions.status_approved') if t[3] == 'approved' else get_text(user_id, 'transactions.status_rejected')
                text += f"🆔 Payment ID: {t[0]}\n"
                text += f"👤 User: {t[1]}\n"
                text += f"💰 Amount: {t[2]:,}\n"
                text += f"📝 Status: {status_emoji} {t[3]}\n"
                text += f"🕒 Date: {t[4]}\n"
                text += "➖➖➖➖➖➖➖➖\n"
            
            keyboard = types.InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                types.InlineKeyboardButton(get_text(user_id, 'transactions.prev_page'), callback_data="transactions_prev"),
                types.InlineKeyboardButton(get_text(user_id, 'transactions.next_page'), callback_data="transactions_next")
            )
            keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="admin_panel"))
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard
        )
        
    except Exception as e:
        logging.error(f"Error in transactions pagination: {e}")
        print(f"Error in transactions pagination: {e}")
        bot.answer_callback_query(call.id, get_text(call.from_user.id, 'errors.general_short'))

def save_user(user):
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        # بررسی وجود کاربر
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user.id,))
        existing_user = cursor.fetchone()
        
        if existing_user is None:
            # اگر کاربر وجود نداشت، اضافه کن با موجودی صفر
            cursor.execute('''
                INSERT INTO users (user_id, balance)
                VALUES (?, 0)
            ''', (user.id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        logging.error(f"Error saving user: {e}")
        print(f"Error saving user: {e}")  # اضافه کردن لاگ اضافی برای دیباگ
        return False

@bot.callback_query_handler(func=lambda call: call.data == "manage_channels")
def handle_manage_channels(call):
    try:
        user_id = call.from_user.id
        if user_id not in BOT_CONFIG['admin_ids']:
            bot.answer_callback_query(call.id, get_text(user_id, 'errors.no_access_section'))
            return
            
        channels = admin_config.get_required_channels()
        logging.info(f"Retrieved channels for display: {channels}")
        
        text = get_text(user_id, 'channels.management_title')
        
        if channels and len(channels) > 0:
            text += get_text(user_id, 'channels.list_title')
            for i, channel in enumerate(channels, 1):
                try:
                    chat_info = bot.get_chat(f"@{channel[0]}")
                    text += f"{i}. {chat_info.title}\n"
                    text += f"🆔 @{channel[0]}\n"
                    text += f"🔗 {channel[2]}\n"
                    text += "➖➖➖➖➖➖➖➖\n"
                except Exception as e:
                    logging.error(f"Error getting chat info for @{channel[0]}: {e}")
                    text += f"{i}. @{channel[0]} ({get_text(user_id, 'channels.unreachable')})\n"
                    text += "➖➖➖➖➖➖➖➖\n"
        else:
            text += get_text(user_id, 'channels.no_channels')
            
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            types.InlineKeyboardButton(get_text(user_id, 'channels.add_channel'), callback_data="add_channel"),
            types.InlineKeyboardButton(get_text(user_id, 'channels.remove_channel'), callback_data="remove_channel")
        )
        keyboard.add(
            types.InlineKeyboardButton(get_text(user_id, 'channels.check_status'), callback_data="check_channels_status"),
            types.InlineKeyboardButton(get_text(user_id, 'channels.lock_status'), callback_data="toggle_lock")
        )
        keyboard.add(
            types.InlineKeyboardButton(get_text(user_id, 'channels.add_bot'), url="https://t.me/HajNumber_Bot")
        )
        keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_admin'), callback_data="admin_panel"))
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
        
    except Exception as e:
        logging.error(f"Error in manage_channels: {e}")
        bot.answer_callback_query(call.id, get_text(call.from_user.id, 'errors.general_short'))

@bot.callback_query_handler(func=lambda call: call.data == "add_channel")
def handle_add_channel(call):
    try:
        user_id = call.from_user.id
        text = get_text(user_id, 'channels.add_prompt')

        msg = bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton(get_text(user_id, 'channels.add_bot'), url="https://t.me/HajNumber_Bot")
            )
        )
        bot.register_next_step_handler(msg, process_channel_username)
    except Exception as e:
        logging.error(f"Error in add_channel: {e}")
        bot.answer_callback_query(call.id, get_text(call.from_user.id, 'errors.general_short'))

def process_channel_username(message):
    user_id = message.from_user.id
    try:
        if user_id not in BOT_CONFIG['admin_ids']:
            return
            
        username = message.text.strip()
        if not username.startswith('@'):
            raise ValueError(get_text(user_id, 'channels.invalid_username'))
            
        username = username[1:]
        
        try:
            chat_info = bot.get_chat(f"@{username}")
            bot_member = bot.get_chat_member(f"@{username}", bot.get_me().id)
            
            if bot_member.status not in ['administrator', 'creator']:
                keyboard = types.InlineKeyboardMarkup(row_width=1)
                keyboard.add(
                    types.InlineKeyboardButton(get_text(user_id, 'channels.add_bot'), url="https://t.me/HajNumber_Bot"),
                    types.InlineKeyboardButton(get_text(user_id, 'navigation.retry'), callback_data="add_channel"),
                    types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_channels'), callback_data="manage_channels")
                )
                bot.reply_to(message, get_text(user_id, 'channels.bot_not_admin'), reply_markup=keyboard)
                return
                
            try:
                invite_link = bot.export_chat_invite_link(f"@{username}")
            except:
                invite_link = f"https://t.me/{username}"
            
            admin_config.add_required_channel(
                username=username,
                display_name=chat_info.title,
                invite_link=invite_link
            )
            
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_channels'), callback_data="manage_channels"))
            
            bot.reply_to(
                message,
                get_text(user_id, 'channels.channel_added', name=chat_info.title, username=username, link=invite_link),
                reply_markup=keyboard
            )
            
        except telebot.apihelper.ApiException as e:
            keyboard = types.InlineKeyboardMarkup(row_width=1)
            if "chat not found" in str(e).lower():
                keyboard.add(
                    types.InlineKeyboardButton(get_text(user_id, 'navigation.retry'), callback_data="add_channel"),
                    types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_channels'), callback_data="manage_channels")
                )
                bot.reply_to(message, get_text(user_id, 'channels.channel_not_found'), reply_markup=keyboard)
            elif "bot is not a member" in str(e).lower():
                keyboard.add(
                    types.InlineKeyboardButton(get_text(user_id, 'channels.add_bot'), url="https://t.me/HajNumber_Bot"),
                    types.InlineKeyboardButton(get_text(user_id, 'navigation.retry'), callback_data="add_channel"),
                    types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_channels'), callback_data="manage_channels")
                )
                bot.reply_to(message, get_text(user_id, 'channels.bot_not_member'), reply_markup=keyboard)
            else:
                keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_channels'), callback_data="manage_channels"))
                bot.reply_to(message, get_text(user_id, 'errors.api_error'), reply_markup=keyboard)
                
    except ValueError as e:
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.retry'), callback_data="add_channel"))
        keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_channels'), callback_data="manage_channels"))
        bot.reply_to(message, str(e), reply_markup=keyboard)
        
    except Exception as e:
        logging.error(f"Error in process_channel_username: {e}")
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_channels'), callback_data="manage_channels"))
        bot.reply_to(message, get_text(user_id, 'errors.general_short'), reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data == "remove_channel")
def handle_remove_channel(call):
    try:
        user_id = call.from_user.id
        channels = admin_config.get_required_channels()
        if not channels:
            bot.answer_callback_query(call.id, get_text(user_id, 'channels.no_channels_to_remove'))
            return
            
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        for channel in channels:
            keyboard.add(types.InlineKeyboardButton(
                f"❌ {channel[1]} (@{channel[0]})",
                callback_data=f"del_channel_{channel[0]}"
            ))
        keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_channels'), callback_data="manage_channels"))
        
        bot.edit_message_text(
            get_text(user_id, 'channels.remove_select'),
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard
        )
        
    except Exception as e:
        logging.error(f"Error in remove_channel: {e}")
        bot.answer_callback_query(call.id, get_text(call.from_user.id, 'errors.general_short'))

@bot.callback_query_handler(func=lambda call: call.data.startswith('del_channel_'))
def handle_delete_channel(call):
    try:
        username = call.data.split('_')[2]
        admin_config.remove_required_channel(username)
        
        bot.answer_callback_query(call.id, get_text(call.from_user.id, 'channels.channel_removed'))
        handle_manage_channels(call)
        
    except Exception as e:
        logging.error(f"Error in delete_channel: {e}")
        bot.answer_callback_query(call.id, get_text(call.from_user.id, 'errors.general_short'))

@bot.callback_query_handler(func=lambda call: call.data == "check_channels_status")
def handle_check_channels_status(call):
    try:
        user_id = call.from_user.id
        channels = admin_config.get_required_channels()
        if not channels:
            bot.answer_callback_query(call.id, get_text(user_id, 'channels.no_channels'))
            return
            
        text = get_text(user_id, 'channels.status_title')
        all_ok = True
        
        for channel in channels:
            try:
                bot_member = bot.get_chat_member(f"@{channel[0]}", bot.get_me().id)
                chat_info = bot.get_chat(f"@{channel[0]}")
                
                if bot_member.status in ['administrator', 'creator']:
                    text += f"✅ {chat_info.title}\n"
                    text += f"🆔 @{channel[0]}\n"
                    text += get_text(user_id, 'channels.status_bot_admin') + "\n"
                else:
                    text += f"⚠️ {chat_info.title}\n"
                    text += f"🆔 @{channel[0]}\n"
                    text += get_text(user_id, 'channels.status_bot_not_admin') + "\n"
                    all_ok = False
                    
            except Exception as e:
                text += f"❌ @{channel[0]}\n"
                text += get_text(user_id, 'channels.status_error') + "\n"
                all_ok = False
                
            text += "➖➖➖➖➖➖➖➖\n"
            
        text += f"\n{get_text(user_id, 'channels.all_ok') if all_ok else get_text(user_id, 'channels.some_issues')}"
        
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_channels'), callback_data="manage_channels"))
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard
        )
        
    except Exception as e:
        logging.error(f"Error in check_channels_status: {e}")
        bot.answer_callback_query(call.id, get_text(call.from_user.id, 'errors.general_short'))

@bot.callback_query_handler(func=lambda call: call.data == "toggle_lock")
def handle_toggle_lock(call):
    try:
        user_id = call.from_user.id
        current_status = admin_config.get_lock_status()
        new_status = not current_status
        admin_config.set_lock_status(new_status)
        
        status_text = get_text(user_id, 'channels.lock_active') if new_status else get_text(user_id, 'channels.lock_inactive')
        bot.answer_callback_query(call.id, get_text(user_id, 'channels.lock_toggled', status=status_text))
        handle_manage_channels(call)
        
    except Exception as e:
        logging.error(f"Error in toggle_lock: {e}")
        bot.answer_callback_query(call.id, get_text(call.from_user.id, 'errors.general_short'))

@bot.callback_query_handler(func=lambda call: call.data == "no_operator")
def handle_no_operator(call):
    bot.answer_callback_query(call.id, get_text(call.from_user.id, 'services.no_operator'))

# ایجاد دایرکتوری logs اگر وجود ندارد
if not os.path.exists('logs'):
    os.makedirs('logs')

# تنظیم لاگر مخصوص فرآیند خرید
purchase_logger = logging.getLogger('purchase_logger')
purchase_logger.setLevel(logging.INFO)

# تنظیم فایل لاگ با چرخش روزانه
purchase_handler = logging.handlers.TimedRotatingFileHandler(
    'logs/purchase.log',
    when='midnight',
    interval=1,
    backupCount=7,
    encoding='utf-8'
)

# تنظیم فرمت لاگ
purchase_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
purchase_handler.setFormatter(purchase_formatter)
purchase_logger.addHandler(purchase_handler)

# اضافه کردن لاگ‌ها در بخش خرید
def handle_buy_number(call):
    try:
        purchase_logger = logging.getLogger('purchase_logger')
        purchase_logger.info(f"Starting purchase process for user {call.from_user.id}")

        # دریافت اطلاعات از callback_data
        _, service, country = call.data.split('_')
        purchase_logger.info(f"Service: {service}, Country: {country}")

        # بررسی موجودی کاربر
        user_balance = get_user_balance(call.from_user.id)
        purchase_logger.info(f"User balance: {user_balance}")

        # دریافت قیمت
        price = get_prices(product)
        purchase_logger.info(f"Product price: {price}")

        if user_balance < price:
            purchase_logger.warning(f"Insufficient balance for user {call.from_user.id}")
            bot.answer_callback_query(call.id, "❌ موجودی شما کافی نیست")
            return

        # خرید شماره از hero-sms.com API
        country_id = COUNTRY_ID_MAP.get(country, country)
        service_code = SERVICE_CODE_MAP.get(service, service)
        
        buy_params = {
            'api_key': HEROSMS_CONFIG['api_key'],
            'action': 'getNumber',
            'service': service_code,
            'country': country_id
        }
        
        purchase_logger.info(f"Sending request to hero-sms.com API...")
        response = requests.get(
            HEROSMS_CONFIG['api_url'],
            params=buy_params,
            timeout=30
        )
        
        purchase_logger.info(f"hero-sms.com API Response Status: {response.status_code}")
        purchase_logger.info(f"hero-sms.com API Response: {response.text}")

        if response.status_code == 200:
            resp_text = response.text.strip()
            if resp_text.startswith('ACCESS_NUMBER:'):
                parts = resp_text.split(':')
                order = {
                    'id': parts[1],
                    'phone': parts[2]
                }
            else:
                purchase_logger.error(f"hero-sms.com API unexpected response: {resp_text}")
                bot.answer_callback_query(call.id, f"❌ خطا در خرید شماره: {resp_text}")
                return
            
            # کم کردن موجودی
            new_balance = add_balance(call.from_user.id, -price)
            logging.info(f"New balance after purchase: {new_balance}")

            try:
                # بررسی وجود جدول
                conn = sqlite3.connect(DB_CONFIG['users_db'])
                cursor = conn.cursor()
                
                # ایجاد جدول اگر وجود ندارد
                cursor.execute('''CREATE TABLE IF NOT EXISTS orders
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     user_id INTEGER,
                     phone_number TEXT,
                     service TEXT,
                     country TEXT,
                     price INTEGER,
                     order_id TEXT UNIQUE,
                     status TEXT DEFAULT 'active',
                     order_date DATETIME DEFAULT CURRENT_TIMESTAMP)''')
                
                # ذخیره اطلاعات سفارش
                cursor.execute('''
                    INSERT INTO orders 
                    (user_id, phone_number, service, country, price, order_id, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    call.from_user.id,
                    order['phone'],
                    service,
                    country,
                    price,
                    order['id'],
                    'active'
                ))
                conn.commit()
                logging.info(f"Order saved successfully. Order ID: {order['id']}")

                # ارسال پیام موفقیت به کاربر
                keyboard = types.InlineKeyboardMarkup(row_width=2)
                keyboard.add(
                    types.InlineKeyboardButton("📱 مشاهده جزئیات", url=f"{BOT_CONFIG['website_url']}/number/{order['id']}"),
                    types.InlineKeyboardButton("🔙 برگشت", callback_data="back_to_main")
                )

                bot.edit_message_text(
                    f"✅ خرید با موفقیت انجام شد!\n\n"
                    f"📱 شماره: {order['phone']}\n"
                    f"🌍 کشور: {country}\n"
                    f"🔰 سرویس: {service}\n"
                    f"💰 مبلغ پرداخت شده: {price:,} تومان\n"
                    f"💎 موجودی فعلی: {new_balance:,} تومان",
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=keyboard
                )
                logging.info("Success message sent to user")

            except sqlite3.Error as db_error:
                logging.error(f"Database error: {db_error}")
                # برگرداندن پول در صورت خطا
                add_balance(call.from_user.id, price)
                bot.answer_callback_query(call.id, "❌ خطا در ثبت سفارش")
            finally:
                conn.close()

        else:
            purchase_logger.error(f"hero-sms.com API error: {response.text}")
            bot.answer_callback_query(call.id, "❌ خطا در خرید شماره")

    except Exception as e:
        logging.error(f"Error in handle_buy_number: {e}", exc_info=True)
        bot.answer_callback_query(call.id, "❌ خطای غیرمنتظره")

def buy_activation_number(country, operator, product, forwarding=False, forwarding_number=None, reuse=None, voice=None, ref=None, max_price=None):
    """
    خرید شماره از سرویس hero-sms.com (SMS-Activate Protocol)
    پاسخ موفق: ACCESS_NUMBER:ID:PHONE
    """
    try:
        country_id = COUNTRY_ID_MAP.get(country, country)
        service_code = SERVICE_CODE_MAP.get(product, product)
        
        params = {
            'api_key': HEROSMS_CONFIG['api_key'],
            'action': 'getNumber',
            'service': service_code,
            'country': country_id
        }
        
        if operator and operator != 'any':
            params['operator'] = operator
        if forwarding:
            params['forwarding'] = '1'
            if forwarding_number:
                params['number'] = forwarding_number
        if reuse:
            params['reuse'] = '1'
        if voice:
            params['voice'] = '1'
        if ref:
            params['ref'] = ref
        if max_price:
            params['maxPrice'] = str(max_price)
        
        logging.info(f"Sending request to hero-sms.com API: URL={HEROSMS_CONFIG['api_url']}, Params={params}")
        
        response = requests.get(
            HEROSMS_CONFIG['api_url'],
            params=params,
            timeout=30
        )
        
        logging.info(f"hero-sms.com API response status: {response.status_code}")
        logging.info(f"hero-sms.com API response body: {response.text}")
        
        resp_text = response.text.strip()
        
        # بررسی خطاهای متنی SMS-Activate
        if resp_text == 'NO_NUMBERS':
            return {
                'success': False,
                'error': 'در حال حاضر شماره‌ای برای این سرویس موجود نیست. لطفاً اپراتور دیگری را امتحان کنید.'
            }
        elif resp_text == 'NO_BALANCE':
            return {
                'success': False,
                'error': 'موجودی حساب hero-sms.com کافی نیست.'
            }
        elif resp_text.startswith('ERROR'):
            return {
                'success': False,
                'error': f'خطای API: {resp_text}'
            }
        elif resp_text.startswith('ACCESS_NUMBER:'):
            # موفقیت: ACCESS_NUMBER:ID:PHONE
            parts = resp_text.split(':')
            activation_id = parts[1]
            phone = parts[2]
            return {
                'success': True,
                'data': {
                    'order_id': activation_id,
                    'phone': phone,
                    'operator': operator,
                    'product': product,
                    'price': 0,
                    'status': 'PENDING',
                    'expires': '',
                    'created_at': '',
                    'country': country
                }
            }
        else:
            return {
                'success': False,
                'error': f'پاسخ غیرمنتظره API: {resp_text}'
            }
        
    except requests.exceptions.RequestException as e:
        error_msg = f"خطا در ارتباط با سرور: {str(e)}"
        logging.error(error_msg)
        return {
            'success': False,
            'error': error_msg
        }
    except Exception as e:
        error_msg = f"خطای غیرمنتظره: {str(e)}"
        logging.error(error_msg)
        return {
            'success': False,
            'error': error_msg
        }

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_number_'))
def handle_buy_number(call):
    try:
        user_id = call.from_user.id
        
        # بررسی موجودی کاربر
        balance = get_user_balance(user_id)
        logging.info(f"User {user_id} balance checked: {balance}")
        
        parts = call.data.split('_')
        # فرمت جدید: buy_number_service_country_operator
        service = parts[2]
        country = parts[3]
        operator = parts[4]  # حالا اپراتور را از callback_data می‌گیریم
        
        # دریافت نام کشور از تنظیمات
        config_operator, country_name = operator_config.get_operator_info(service, country)
        
        # اگر نام کشور در تنظیمات نباشد، از i18n استفاده می‌کنیم
        if not country_name:
            country_name = get_text(user_id, f'countries.{country}')
            
        # دریافت قیمت از hero-sms.com
        country_id = COUNTRY_ID_MAP.get(country, country)
        service_code = SERVICE_CODE_MAP.get(service, service)
        
        params = {
            'api_key': HEROSMS_CONFIG['api_key'],
            'action': 'getPrices',
            'country': country_id,
            'service': service_code
        }
        
        response = requests.get(
            HEROSMS_CONFIG['api_url'],
            params=params,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            
            if country_id in data and service_code in data[country_id]:
                operators_data = data[country_id][service_code]
                
                if operator in operators_data and operators_data[operator]['count'] > 0:
                    price_usd = operators_data[operator]['cost']
                    
                    # دریافت نرخ دلار و درصد سود از دیتابیس
                    conn = sqlite3.connect('admin.db')
                    cursor = conn.cursor()
                    
                    cursor.execute('SELECT value FROM settings WHERE key = "usd_rate"')
                    usd_rate_result = cursor.fetchone()
                    usd_rate = float(usd_rate_result[0]) if usd_rate_result else 0
                    
                    cursor.execute('SELECT value FROM settings WHERE key = "profit_percentage"')
                    profit_result = cursor.fetchone()
                    profit_percentage = float(profit_result[0]) if profit_result else 0
                    
                    conn.close()
                    
                    price_toman = round(price_usd * usd_rate * (1 + profit_percentage/100))
                    
                    if balance < price_toman:
                        # موجودی ناکافی
                        bot.answer_callback_query(call.id, "⚠️")
                        keyboard = types.InlineKeyboardMarkup(row_width=1)
                        keyboard.add(
                            types.InlineKeyboardButton(get_text(user_id, 'main_menu.add_funds'), callback_data="add_funds"),
                            types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_services'), callback_data="back_to_services")
                        )
                        deficit = price_toman - balance
                        bot.edit_message_text(
                            get_text(user_id, 'purchase.insufficient_balance', balance=balance, price=price_toman, deficit=deficit),
                            call.message.chat.id,
                            call.message.message_id,
                            reply_markup=keyboard
                        )
                        return
                    
                    # خرید شماره
                    bot.edit_message_text(
                        get_text(user_id, 'purchase.buying', service=service, country=country_name),
                        call.message.chat.id,
                        call.message.message_id
                    )
                    
                    # خرید شماره با استفاده از API
                    result = buy_activation_number(country, operator, service)
                    logging.info(f"Buy number result: {result}")
                    
                    # بررسی نتیجه خرید
                    if result and isinstance(result, dict) and result.get('success') and 'data' in result:
                        # دریافت اطلاعات از ساختار جدید
                        order_data = result['data']
                        activation_id = order_data['order_id']
                        phone_number = order_data['phone']
                        status = order_data['status']
                        
                        # کم کردن موجودی کاربر
                        add_balance(user_id, -price_toman)
                        
                        # ثبت تراکنش در دیتابیس
                        order_info = {
                            'user_id': user_id,
                            'activation_id': activation_id,
                            'service': service,
                            'country': country,
                            'operator': operator,
                            'phone': phone_number,
                            'price': price_toman,
                            'status': status.lower()
                        }
                        
                        # ذخیره در دیتابیس و دریافت شناسه سفارش
                        order_id = save_order(order_info)
                        
                        if order_id:
                            # استفاده از یک URL کامل با هاست
                            details_url = f"{BOT_CONFIG['website_url']}/number_details/{order_id}"
                            
                            keyboard = types.InlineKeyboardMarkup(row_width=1)
                            keyboard.add(
                                types.InlineKeyboardButton(get_text(user_id, 'purchase.get_code'), callback_data=f"get_code_{activation_id}"),
                                types.InlineKeyboardButton(get_text(user_id, 'purchase.cancel_order'), callback_data=f"cancel_order_{activation_id}"),
                                types.InlineKeyboardButton(get_text(user_id, 'purchase.view_details_web'), url=details_url),
                                types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_services'), callback_data="back_to_services")
                            )
                            
                            bot.edit_message_text(
                                get_text(user_id, 'purchase.success',
                                    service=service, country=country_name,
                                    phone=phone_number, operator=operator,
                                    price=price_toman),
                                call.message.chat.id,
                                call.message.message_id,
                                reply_markup=keyboard
                            )
                        else:
                            # خطا در ذخیره اطلاعات
                            logging.error("Error saving order to database")
                            bot.edit_message_text(
                                get_text(user_id, 'purchase.save_error'),
                                call.message.chat.id,
                                call.message.message_id,
                                reply_markup=services_keyboard(user_id)
                            )
                    else:
                        # خطا در خرید شماره
                        error_msg = get_text(user_id, 'errors.general')
                        if isinstance(result, dict):
                            if 'message' in result:
                                error_msg = result['message']
                            elif result.get('error'):
                                error_msg = result['error']
                        
                        logging.error(f"Error buying number: {error_msg}")
                        bot.edit_message_text(
                            get_text(user_id, 'purchase.buy_error', error=error_msg),
                            call.message.chat.id,
                            call.message.message_id,
                            reply_markup=services_keyboard(user_id)
                        )
                else:
                    # اپراتور موجود نیست
                    op_unavail = get_text(user_id, 'purchase.operator_unavailable', operator=operator, country=country_name, service=service)
                    bot.answer_callback_query(call.id, op_unavail[:50])
                    bot.edit_message_text(
                        op_unavail,
                        call.message.chat.id,
                        call.message.message_id,
                        reply_markup=services_keyboard(user_id)
                    )
            else:
                # کشور یا سرویس موجود نیست
                bot.answer_callback_query(call.id, get_text(user_id, 'purchase.service_country_unavailable'))
                bot.edit_message_text(
                    get_text(user_id, 'purchase.service_country_unavailable'),
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=services_keyboard(user_id)
                )
        else:
            # خطا در دریافت قیمت‌ها
            bot.answer_callback_query(call.id, get_text(user_id, 'purchase.price_fetch_error'))
            bot.edit_message_text(
                get_text(user_id, 'purchase.price_fetch_error'),
                call.message.chat.id,
                call.message.message_id,
                reply_markup=services_keyboard(user_id)
            )
            
    except Exception as e:
        logging.error(f"Error in handle_buy_number: {e}")
        import traceback
        logging.error(f"Traceback: {traceback.format_exc()}")
        bot.answer_callback_query(call.id, get_text(call.from_user.id, 'errors.general_short'))
        bot.send_message(call.message.chat.id, get_text(call.from_user.id, 'errors.general'))

@bot.callback_query_handler(func=lambda call: call.data.startswith('get_code_'))
def handle_get_code(call):
    try:
        user_id = call.from_user.id
        order_id = call.data.split('_')[2]
        
        # دریافت کد از hero-sms.com (SMS-Activate Protocol: getStatus)
        check_params = {
            'api_key': HEROSMS_CONFIG['api_key'],
            'action': 'getStatus',
            'id': order_id
        }
        
        check_url = HEROSMS_CONFIG['api_url']
        logging.info(f"Checking order status: {check_url} with params {check_params}")
        
        response = requests.get(
            check_url,
            params=check_params,
            timeout=30
        )
        
        logging.info(f"Check status response: {response.status_code}")
        logging.info(f"Check status data: {response.text}")
        
        if response.status_code == 200:
            resp_text = response.text.strip()
            
            if resp_text.startswith('STATUS_OK:'):
                # کد دریافت شده: STATUS_OK:12345
                parts = resp_text.split(':')
                code_text = parts[1] if len(parts) > 1 else ''
                
                keyboard = types.InlineKeyboardMarkup()
                keyboard.add(types.InlineKeyboardButton(
                    get_text(user_id, 'purchase.view_details'),
                    url=f"{BOT_CONFIG['website_url']}/number_details/{order_id}"
                ))
                keyboard.add(types.InlineKeyboardButton(
                    get_text(user_id, 'navigation.back_to_main'),
                    callback_data="back_to_main"
                ))
                
                # آپدیت وضعیت سفارش در دیتابیس
                conn = sqlite3.connect('bot.db')
                cursor = conn.cursor()
                cursor.execute('UPDATE orders SET status = ? WHERE id = ?', ('RECEIVED', order_id))
                
                # ذخیره کد در جدول activation_codes
                from datetime import datetime
                cursor.execute("""
                    INSERT INTO activation_codes (order_id, code, created_at)
                    VALUES (?, ?, ?)
                """, (order_id, code_text, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                
                conn.commit()
                conn.close()
                
                bot.edit_message_text(
                    f"✅ {get_text(user_id, 'order.code_received', phone='', code=code_text, time='')}\n\n📱 کد: <b>{code_text}</b>",
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=keyboard,
                    parse_mode='HTML'
                )
            elif resp_text == 'STATUS_WAIT_CODE' or resp_text == 'STATUS_WAIT_RETRY':
                bot.answer_callback_query(call.id, get_text(user_id, 'order.code_not_received'))
            elif resp_text == 'STATUS_CANCEL':
                bot.answer_callback_query(call.id, get_text(user_id, 'order.cancelled_simple', refund=''))
            else:
                bot.answer_callback_query(call.id, get_text(user_id, 'order.code_not_received'))
        else:
            bot.answer_callback_query(call.id, get_text(user_id, 'order.status_check_error'))
            
    except Exception as e:
        logging.error(f"خطا در دریافت کد: {e}")
        bot.answer_callback_query(call.id, get_text(call.from_user.id, 'errors.general'))

def refund_order_amount(order_id):
    """
    برگرداندن مبلغ سفارش به کاربر در هنگام لغو سفارش
    """
    try:
        # دریافت اطلاعات سفارش
        conn_orders = sqlite3.connect('bot.db')
        cursor_orders = conn_orders.cursor()
        
        # جستجوی سفارش بر اساس activation_id
        cursor_orders.execute('''
            SELECT user_id, price, status FROM orders 
            WHERE activation_id = ?
        ''', (order_id,))
        
        order = cursor_orders.fetchone()
        
        if not order:
            logging.error(f"سفارش با شناسه {order_id} یافت نشد")
            conn_orders.close()
            return False, "سفارش یافت نشد"
            
        user_id, price, status = order
        
        # اگر سفارش قبلاً لغو شده باشد، وجه را برنگردان
        if status.upper() == "CANCELED":
            logging.warning(f"سفارش {order_id} قبلاً لغو شده است")
            conn_orders.close()
            return False, "سفارش قبلاً لغو شده است"
            
        # بروزرسانی وضعیت سفارش
        cursor_orders.execute('''
            UPDATE orders SET status = "CANCELED" 
            WHERE activation_id = ?
        ''', (order_id,))
        
        conn_orders.commit()
        conn_orders.close()
        
        # دریافت موجودی قبل از افزایش
        current_balance = get_user_balance(user_id)
        
        if current_balance is None:
            logging.error(f"کاربر با شناسه {user_id} یافت نشد")
            return False, "کاربر یافت نشد"
            
        # افزایش موجودی کاربر با استفاده از تابع موجود
        add_balance(user_id, price)
        
        # دریافت موجودی جدید (برای لاگ)
        new_balance = get_user_balance(user_id)
        
        logging.info(f"مبلغ {price} تومان به حساب کاربر {user_id} برگشت داده شد. موجودی جدید: {new_balance}")
        
        # برگرداندن هر دو مقدار: مبلغ برگشتی و موجودی جدید
        return True, {'refund_amount': price, 'new_balance': new_balance}
        
    except Exception as e:
        logging.error(f"خطا در برگرداندن وجه: {e}")
        import traceback
        logging.error(traceback.format_exc())
        
        if 'conn_orders' in locals():
            conn_orders.close()
            
        return False, str(e)

@bot.callback_query_handler(func=lambda call: call.data.startswith('cancel_order_'))
def handle_cancel_order(call):
    try:
        user_id = call.from_user.id
        # دریافت شناسه سفارش
        order_id = int(call.data.split('_')[2])
        
        # اطلاع به کاربر
        bot.edit_message_text(
            get_text(user_id, 'order.cancelling'),
            call.message.chat.id,
            call.message.message_id
        )
        
        # درخواست لغو سفارش به hero-sms.com (SMS-Activate: setStatus with status=8 = cancel)
        cancel_params = {
            'api_key': HEROSMS_CONFIG['api_key'],
            'action': 'setStatus',
            'id': order_id,
            'status': '8'
        }
        
        response = requests.get(
            HEROSMS_CONFIG['api_url'],
            params=cancel_params,
            timeout=30
        )
        
        if response.status_code == 200:
            # برگرداندن وجه به کاربر با استفاده از تابع جدید
            success, result = refund_order_amount(order_id)
            
            if success:
                # نمایش پیام موفقیت
                if isinstance(result, dict):
                    refund_amount = result['refund_amount']
                    new_balance = result['new_balance']
                    success_message = get_text(user_id, 'order.cancelled', balance=new_balance, refund=refund_amount)
                else:
                    success_message = get_text(user_id, 'order.cancelled_simple', refund=result)
            else:
                # لغو سفارش انجام شده اما مشکلی در برگرداندن وجه بوده
                success_message = get_text(user_id, 'order.cancelled_warning', warning=str(result))
                
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_menu'), callback_data="buy_number"))
            
            bot.edit_message_text(
                success_message,
                call.message.chat.id,
                call.message.message_id,
                reply_markup=keyboard
            )
            
        # ... ادامه کد بدون تغییر ...
    except Exception as e:
        logging.error(f"خطا در لغو سفارش: {e}")
        import traceback
        logging.error(traceback.format_exc())
        
        bot.edit_message_text(
            get_text(call.from_user.id, 'order.cancel_error'),
            call.message.chat.id,
            call.message.message_id,
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton(get_text(call.from_user.id, 'navigation.back'), callback_data="my_orders")
            )
        )

# ایجاد نمونه از کلاس OperatorConfig
operator_config = OperatorConfig()

# و در تابع initialize یا main
def initialize_bot():
    try:
        conn = sqlite3.connect('bot.db')
        cursor = conn.cursor()
        
        # ایجاد جدول settings در شروع برنامه
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        ''')
        
        # بررسی و اضافه کردن تنظیمات پیش‌فرض
        cursor.execute('SELECT COUNT(*) FROM settings')
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO settings (key, value) VALUES 
                ("usd_rate", "0.35"),
                ("profit_percentage", "20")
            ''')
        
        conn.commit()
        logging.info("Bot initialized successfully with required tables")
        
    except sqlite3.Error as e:
        logging.error(f"Database initialization error: {e}")
    finally:
        if conn:
            conn.close()

@bot.callback_query_handler(func=lambda call: call.data == "operator_settings")
def handle_operator_settings(call):
    try:
        user_id = call.from_user.id
        if user_id not in BOT_CONFIG['admin_ids']:
            bot.answer_callback_query(call.id, get_text(user_id, 'errors.no_access'))
            return
            
        settings = operator_config.get_all_settings()
        
        text = get_text(user_id, 'operators.settings_title')
        
        # استفاده از المصدر الموحد (Single Source of Truth)
        for svc_key in ALL_SERVICES:
            svc_name = get_text(user_id, f'operators.service_{svc_key}')
            text += f"🔹 {svc_name}:\n"
            for country_code in _get_countries_for_service(svc_key):
                country_name = get_text(user_id, f'countries.{country_code}')
                operator = next((s[2] for s in settings if s[0] == svc_key and s[1] == country_code), get_text(user_id, 'operators.not_set'))
                text += f"  • {country_name}: {operator}\n"
            text += "\n"
            
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            types.InlineKeyboardButton(get_text(user_id, 'operators.change_settings'), callback_data="change_operator"),
            types.InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="admin_panel")
        )
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard
        )
    except Exception as e:
        logging.error(f"Error in operator_settings: {e}")
        bot.answer_callback_query(call.id, get_text(call.from_user.id, 'errors.general'))

@bot.callback_query_handler(func=lambda call: call.data == "change_operator")
def handle_change_operator(call):
    try:
        user_id = call.from_user.id
        if user_id not in BOT_CONFIG['admin_ids']:
            bot.answer_callback_query(call.id, get_text(user_id, 'errors.no_access'))
            return
            
        text = get_text(user_id, 'operators.select_service')
        
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            types.InlineKeyboardButton(get_text(user_id, 'operators.service_telegram'), callback_data="select_service_telegram"),
            types.InlineKeyboardButton(get_text(user_id, 'operators.service_whatsapp'), callback_data="select_service_whatsapp"),
            types.InlineKeyboardButton(get_text(user_id, 'operators.service_instagram'), callback_data="select_service_instagram"),
            types.InlineKeyboardButton(get_text(user_id, 'operators.service_google'), callback_data="select_service_google"),
            types.InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="operator_settings")
        )
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard
        )
    except Exception as e:
        logging.error(f"خطا در تغییر اپراتور: {e}")
        bot.answer_callback_query(call.id, get_text(call.from_user.id, 'errors.general'))

@bot.callback_query_handler(func=lambda call: call.data.startswith('select_service_'))
def handle_select_service(call):
    try:
        user_id = call.from_user.id
        if user_id not in BOT_CONFIG['admin_ids']:
            bot.answer_callback_query(call.id, get_text(user_id, 'errors.no_access'))
            return
            
        service = call.data.split('_')[2]
        
        if service not in SERVICE_COUNTRIES:
            bot.answer_callback_query(call.id, get_text(user_id, 'operators.invalid_service'))
            return
        
        text = get_text(user_id, 'operators.select_country', service=service)
        
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        for country_code in _get_countries_for_service(service):
            country_name = get_text(user_id, f'countries.{country_code}')
            keyboard.add(types.InlineKeyboardButton(country_name, callback_data=f"select_country_{service}_{country_code}"))
        
        keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="change_operator"))
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard
        )
    except Exception as e:
        logging.error(f"خطا در انتخاب سرویس: {e}")
        bot.answer_callback_query(call.id, get_text(call.from_user.id, 'errors.general'))

@bot.callback_query_handler(func=lambda call: call.data.startswith('select_country_'))
def handle_select_country(call):
    try:
        user_id = call.from_user.id
        _, service, country = call.data.split('_')[1:]
        msg = bot.edit_message_text(
            get_text(user_id, 'operators.enter_operator'),
            call.message.chat.id,
            call.message.message_id
        )
        bot.register_next_step_handler(msg, process_operator_change, service, country)
        
    except Exception as e:
        logging.error(f"Error in select_country: {e}")
        bot.answer_callback_query(call.id, get_text(call.from_user.id, 'errors.general'))

def process_operator_change(message, service, country):
    try:
        user_id = message.from_user.id
        operator = message.text.strip().lower()
        
        if operator_config.set_operator(service, country, operator):
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_settings'), callback_data="operator_settings"))
            
            bot.reply_to(
                message,
                get_text(user_id, 'operators.operator_changed', service=service, country=country, operator=operator),
                reply_markup=keyboard
            )
        else:
            bot.reply_to(message, get_text(user_id, 'operators.operator_change_error'))
            
    except Exception as e:
        logging.error(f"Error in process_operator_change: {e}")
        bot.reply_to(message, get_text(message.from_user.id, 'errors.general'))


@bot.callback_query_handler(func=lambda call: call.data == 'my_orders')
def handle_my_orders(call):
    user_id = call.from_user.id
    
    try:
        orders_url = f"{BOT_CONFIG['webhook_url'].rstrip('/')}/orders/{user_id}"
        
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            types.InlineKeyboardButton(get_text(user_id, 'order.view_orders_web'), url=orders_url)
        )
        keyboard.add(
            types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_menu'), callback_data="back_to_main")
        )
        
        bot.edit_message_text(
            get_text(user_id, 'order.my_orders_title'),
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Error in handle_my_orders: {e}")
        bot.answer_callback_query(call.id, get_text(call.from_user.id, 'order.orders_error'))

@app.route('/orders/<int:user_id>')
def user_orders(user_id):
    try:
        # اضافه کردن لاگ برای شروع
        logger.info(f"Fetching orders for user_id: {user_id}")
        
        # دریافت سفارش‌های کاربر از دیتابیس
        conn = sqlite3.connect('bot.db')
        cursor = conn.cursor()
        
        # بررسی وجود جدول
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='orders'
        """)
        if not cursor.fetchone():
            logger.error("Table 'orders' does not exist")
            return "جدول سفارش‌ها وجود ندارد", 500
            
        # دریافت سفارش‌ها
        cursor.execute('''
            SELECT activation_id, phone, service, country, price, status, created_at
            FROM orders 
            WHERE user_id = ?
            ORDER BY created_at DESC
        ''', (user_id,))
        
        orders_data = cursor.fetchall()
        logger.info(f"Found {len(orders_data)} orders for user {user_id}")
        
        conn.close()
        
        orders = []
        base_url = BOT_CONFIG['webhook_url'].rstrip('/')
        
        for order in orders_data:
            orders.append({
                'id': order[0],  # activation_id
                'phone_number': order[1],
                'service': order[2],
                'country': order[3],
                'price': order[4],  # حذف فرمت کردن اعداد از اینجا
                'status': order[5],
                'date': order[6],
                'details_url': f"{BOT_CONFIG['website_url']}/number_details/{order[0]}"
            })
        
        # اضافه کردن لاگ برای رندر
        logger.info(f"Rendering template with {len(orders)} orders")
        
        # بررسی وجود تمپلیت
        try:
            return render_template('user_orders.html', orders=orders)
        except Exception as template_error:
            logger.error(f"Template error: {template_error}")
            return "خطا در بارگذاری قالب صفحه", 500
        
    except Exception as e:
        logger.error(f"Error in user_orders: {str(e)}")
        return f"خطای سیستمی: {str(e)}", 500

@bot.callback_query_handler(func=lambda call: call.data == "add_funds")
def handle_add_funds(call):
    user_id = call.from_user.id
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        types.InlineKeyboardButton(get_text(user_id, 'payment.online'), callback_data="zarinpal_payment"),
        types.InlineKeyboardButton(get_text(user_id, 'payment.card_to_card'), callback_data="card_payment"),
        types.InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="back_to_main")
    )
    
    bot.edit_message_text(
        get_text(user_id, 'payment.select_method'),
        call.message.chat.id,
        call.message.message_id,
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: call.data == "zarinpal_payment")
def handle_zarinpal_payment(call):
    user_id = call.from_user.id
    msg = bot.edit_message_text(
        get_text(user_id, 'payment.enter_amount'),
        call.message.chat.id,
        call.message.message_id
    )
    bot.register_next_step_handler(msg, process_zarinpal_amount)

def process_zarinpal_amount(message):
    try:
        user_id = message.from_user.id
        amount = int(message.text)
        if amount < 5000:
            bot.reply_to(message, get_text(user_id, 'payment.min_amount'))
            return
            
        # درخواست به API زرین‌پال
        data = {
            "merchant_id": PAYMENT_CONFIG['zarinpal_merchant'],
            "amount": amount * 10,  # تبدیل به ریال
            "description": f"شارژ حساب کاربر {message.from_user.id}",
            "callback_url": f"{PAYMENT_CONFIG['callback_url']}/{message.from_user.id}/{amount}",  # این مسیر درست است چون از config می‌خواند
            "metadata": {
                "mobile": message.from_user.username or str(message.from_user.id),
                "email": "",
                "order_id": f"charge_{message.from_user.id}_{int(time.time())}"
            }
        }
        
        # تعیین آدرس API بر اساس حالت sandbox
        if PAYMENT_CONFIG['sandbox_mode']:
            request_url = "https://sandbox.zarinpal.com/pg/v4/payment/request.json"
        else:
            request_url = "https://payment.zarinpal.com/pg/v4/payment/request.json"
            
        response = requests.post(
            request_url,
            json=data,
            headers={'accept': 'application/json', 'content-type': 'application/json'}
        )
        
        result = response.json()
        
        if result['data']['code'] == 100:
            # ساخت لینک پرداخت بر اساس حالت sandbox
            if PAYMENT_CONFIG['sandbox_mode']:
                payment_url = f"https://sandbox.zarinpal.com/pg/StartPay/{result['data']['authority']}"
            else:
                payment_url = f"https://payment.zarinpal.com/pg/StartPay/{result['data']['authority']}"
                
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(
                types.InlineKeyboardButton(get_text(user_id, 'payment.payment_button'), url=payment_url),
                types.InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="add_funds")
            )
            bot.reply_to(
                message,
                get_text(user_id, 'payment.payment_link', amount=amount),
                reply_markup=keyboard
            )
        else:
            bot.reply_to(message, get_text(user_id, 'payment.payment_error'))
            
    except ValueError:
        bot.reply_to(message, get_text(message.from_user.id, 'payment.invalid_amount'))

@app.route('/verify/<user_id>/<amount>')
def verify_payment(user_id, amount):
    try:
        logging.info(f"Payment verification started for user {user_id}, amount {amount}")
        authority = request.args.get('Authority')
        status = request.args.get('Status')
        
        if status != 'OK':
            return render_template('payment_result.html', success=False, message="پرداخت توسط کاربر لغو شد")
        
        # تایید پرداخت با زرین‌پال
        data = {
            "merchant_id": PAYMENT_CONFIG['zarinpal_merchant'],
            "amount": int(amount) * 10,  # تبدیل به ریال
            "authority": authority
        }
        
        verify_url = "https://sandbox.zarinpal.com/pg/v4/payment/verify.json" if PAYMENT_CONFIG['sandbox_mode'] else "https://payment.zarinpal.com/pg/v4/payment/verify.json"
        
        response = requests.post(
            verify_url,
            json=data,
            headers={'accept': 'application/json', 'content-type': 'application/json'}
        )
        
        result = response.json()
        logging.info(f"Zarinpal verification response: {result}")
        
        if result['data']['code'] in [100, 101]:
            # افزایش موجودی کاربر
            new_balance = add_balance(int(user_id), int(amount))
            
            if new_balance is not None:
                # ثبت تراکنش
                conn = sqlite3.connect(DB_CONFIG['users_db'])
                cursor = conn.cursor()
                
                cursor.execute('''CREATE TABLE IF NOT EXISTS transactions
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     user_id INTEGER,
                     amount INTEGER,
                     type TEXT,
                     description TEXT,
                     ref_id TEXT,
                     timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
                
                cursor.execute('''
                    INSERT INTO transactions (user_id, amount, type, description, ref_id)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    int(user_id),
                    int(amount),
                    'deposit',
                    'شارژ حساب از طریق درگاه زرین‌پال',
                    result['data']['ref_id']
                ))
                
                conn.commit()
                conn.close()
                
                # ارسال پیام به کاربر
                success_message = f"""✅ پرداخت شما با موفقیت انجام شد

💰 مبلغ: {int(amount):,} تومان
🔢 کد پیگیری: {result['data']['ref_id']}
💎 موجودی فعلی: {new_balance:,} تومان"""

                try:
                    bot.send_message(int(user_id), success_message)
                except Exception as e:
                    logging.error(f"Error sending message to user: {e}")
                
                return render_template(
                    'payment_result.html',
                    success=True,
                    amount=f"{int(amount):,}",
                    ref_id=result['data']['ref_id'],
                    balance=f"{new_balance:,}"
                )
            else:
                logging.error("Failed to update balance")
                return render_template(
                    'payment_result.html',
                    success=False,
                    message="خطا در بروزرسانی موجودی"
                )
        else:
            return render_template(
                'payment_result.html',
                success=False,
                message=f"خطا در تایید پرداخت: {result['data'].get('message', 'خطای نامشخص')}"
            )
            
    except Exception as e:
        logging.error(f"Payment verification error: {e}", exc_info=True)
        return render_template(
            'payment_result.html',
            success=False,
            message="خطا در پردازش پرداخت"
        )

card_payment = CardPayment(bot)

@bot.callback_query_handler(func=lambda call: call.data == "card_payment")
def handle_card_payment(call):
    msg = bot.edit_message_text(
        "💳 لطفاً مبلغ مورد نظر را به تومان وارد کنید:\n"
        "مثال: 50000",
        call.message.chat.id,
        call.message.message_id
    )
    bot.register_next_step_handler(msg, card_payment.handle_new_payment)

@bot.callback_query_handler(func=lambda call: call.data.startswith("copy_"))
def handle_copy(call):
    text = call.data.split("_", 1)[1]
    bot.answer_callback_query(call.id, f"✅ کپی شد:\n{text}", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith("send_receipt_"))
def handle_send_receipt(call):
    payment_id = call.data.split("_")[2]
    msg = bot.edit_message_text(
        "🧾 لطفاً تصویر رسید پرداخت را ارسال کنید:",
        call.message.chat.id,
        call.message.message_id
    )
    bot.register_next_step_handler(msg, card_payment.handle_receipt, payment_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith(("approve_payment_", "reject_payment_")))
def handle_payment_verification(call):
    action, payment_id = call.data.split("_")[0], call.data.split("_")[2]
    card_payment.verify_payment(call, payment_id, action)

@bot.callback_query_handler(func=lambda call: call.data == "check_card_info")
def check_card_info(call):
    if call.from_user.id not in BOT_CONFIG['admin_ids']:
        bot.answer_callback_query(call.id, "⛔️ شما دسترسی ادمین ندارید")
        return
        
    try:
        conn = sqlite3.connect(DB_CONFIG['admin_db'])
        cursor = conn.cursor()
        cursor.execute('SELECT card_number, card_holder FROM card_info LIMIT 1')
        card_info = cursor.fetchone()
        conn.close()
        
        if card_info:
            bot.answer_callback_query(
                call.id,
                f"اطلاعات کارت:\n"
                f"شماره: {card_info[0]}\n"
                f"به نام: {card_info[1]}",
                show_alert=True
            )
        else:
            bot.answer_callback_query(call.id, "❌ اطلاعات کارتی ثبت نشده است", show_alert=True)
            
    except Exception as e:
        logging.error(f"Error checking card info: {e}")
        bot.answer_callback_query(call.id, "❌ خطا در بررسی اطلاعات کارت", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "new_card")
def handle_new_card(call):
    if call.from_user.id not in BOT_CONFIG['admin_ids']:
        bot.answer_callback_query(call.id, "⛔️ شما دسترسی ادمین ندارید")
        return
        
    msg = bot.edit_message_text(
        "💳 لطفاً شماره کارت را وارد کنید:\n"
        "مثال: 6037-9974-1234-5678",
        call.message.chat.id,
        call.message.message_id
    )
    bot.register_next_step_handler(msg, process_card_number)

def process_card_number(message):
    if message.from_user.id not in BOT_CONFIG['admin_ids']:
        return
        
    # حذف خط تیره و فاصله از شماره کارت
    card_number = message.text.strip().replace('-', '').replace(' ', '')
    
    # بررسی صحت شماره کارت
    if not card_number.isdigit() or len(card_number) != 16:
        msg = bot.reply_to(
            message, 
            "❌ شماره کارت نامعتبر است. لطفاً یک شماره کارت 16 رقمی وارد کنید:\n"
            "مثال: 6037997412345678"
        )
        bot.register_next_step_handler(msg, process_card_number)
        return
        
    try:
        # ذخیره شماره کارت در دیتابیس
        conn = sqlite3.connect(DB_CONFIG['admin_db'])
        cursor = conn.cursor()
        
        # پاک کردن اطلاعات قبلی
        cursor.execute('DELETE FROM card_info')
        
        # افزودن شماره کارت جدید
        cursor.execute('INSERT INTO card_info (card_number) VALUES (?)', (card_number,))
        conn.commit()
        conn.close()
        
        # درخواست نام صاحب کارت
        msg = bot.reply_to(
            message, 
            "✅ شماره کارت ذخیره شد.\n\n"
            "👤 لطفاً نام و نام خانوادگی صاحب کارت را وارد کنید:"
        )
        bot.register_next_step_handler(msg, process_card_holder)
        
    except Exception as e:
        logging.error(f"Error saving card number: {e}")
        bot.reply_to(message, "❌ خطا در ذخیره شماره کارت. لطفاً مجدداً تلاش کنید.")

def process_card_holder(message):
    if message.from_user.id not in BOT_CONFIG['admin_ids']:
        return
        
    card_holder = message.text.strip()
    
    if len(card_holder) < 3:
        msg = bot.reply_to(message, "❌ نام صاحب کارت نامعتبر است. لطفاً مجدداً وارد کنید:")
        bot.register_next_step_handler(msg, process_card_holder)
        return
        
    try:
        conn = sqlite3.connect(DB_CONFIG['admin_db'])
        cursor = conn.cursor()
        cursor.execute('UPDATE card_info SET card_holder = ? WHERE card_holder IS NULL', (card_holder,))
        conn.commit()
        
        # بررسی اطلاعات نهایی
        cursor.execute('SELECT card_number, card_holder FROM card_info LIMIT 1')
        card_info = cursor.fetchone()
        conn.close()
        
        if card_info:
            card_number, card_holder = card_info
            
            # نمایش اطلاعات ذخیره شده
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton("🔙 برگشت به پنل مدیریت", callback_data="admin_panel"))
            
            bot.reply_to(
                message,
                f"✅ اطلاعات کارت با موفقیت ذخیره شد:\n\n"
                f"💳 شماره کارت: <code>{card_number}</code>\n"
                f"👤 صاحب کارت: <code>{card_holder}</code>",
                reply_markup=keyboard,
                parse_mode='HTML'
            )
        else:
            bot.reply_to(message, "❌ خطا در ذخیره اطلاعات کارت. لطفاً مجدداً تلاش کنید.")
            
    except Exception as e:
        logging.error(f"Error saving card holder: {e}")
        bot.reply_to(message, "❌ خطا در ذخیره نام صاحب کارت. لطفاً مجدداً تلاش کنید.")

# ── Admin Authentication Decorator for Test Endpoints ──────────
def _require_admin(f):
    """Decorator to protect test/debug endpoints with admin authentication."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        # Check X-Admin-Token header (enterprise-grade)
        admin_token = request.headers.get('X-Admin-Token', '')
        admin_id_str = request.args.get('admin_id', '')
        
        # Accept either valid admin token or admin_id in query
        if admin_token == BOT_CONFIG['token']:
            return f(*args, **kwargs)
        if admin_id_str.isdigit() and int(admin_id_str) in BOT_CONFIG['admin_ids']:
            return f(*args, **kwargs)
        return jsonify({'success': False, 'message': 'Unauthorized: admin access required'}), 403
    return decorated


@app.route('/test_db_connection')
@_require_admin
def test_db_connection():
    try:
        conn = sqlite3.connect(DB_CONFIG['users_db'])
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        conn.close()
        return jsonify({'success': True, 'message': '✅ اتصال به دیتابیس موفق'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'❌ خطا در اتصال به دیتابیس: {str(e)}'})

@app.route('/test_create_user', methods=['POST'])
@_require_admin
def test_create_user():
    try:
        data = request.get_json()
        user_id = int(data['user_id'])
        
        conn = sqlite3.connect(DB_CONFIG['users_db'])
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0)', (user_id,))
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': f'✅ کاربر {user_id} با موفقیت ایجاد شد'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'❌ خطا در ایجاد کاربر: {str(e)}'})

@app.route('/test_add_balance', methods=['POST'])
@_require_admin
def test_add_balance():
    try:
        data = request.get_json()
        user_id = int(data['user_id'])
        amount = int(data['amount'])
        
        new_balance = add_balance(user_id, amount)
        if new_balance is not None:
            return jsonify({
                'success': True,
                'message': f'✅ موجودی با موفقیت افزایش یافت\n💰 موجودی جدید: {new_balance:,} تومان'
            })
        else:
            return jsonify({'success': False, 'message': '❌ خطا در افزایش موجودی'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'❌ خطا: {str(e)}'})

@app.route('/test_transaction', methods=['POST'])
@_require_admin
def test_transaction():
    try:
        data = request.get_json()
        user_id = int(data['user_id'])
        amount = int(data['amount'])
        
        # اول موجودی را افزایش می‌دهیم
        new_balance = add_balance(user_id, amount)
        if new_balance is None:
            return jsonify({
                'success': False,
                'message': '❌ خطا در افزایش موجودی'
            })

        # سپس تراکنش را ثبت می‌کنیم
        conn = sqlite3.connect(DB_CONFIG['users_db'])
        cursor = conn.cursor()
        
        cursor.execute('''CREATE TABLE IF NOT EXISTS transactions
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
             user_id INTEGER,
             amount INTEGER,
             type TEXT,
             description TEXT,
             ref_id TEXT,
             timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
             FOREIGN KEY (user_id) REFERENCES users(user_id))''')
        
        ref_id = f'TEST{int(time.time())}'
        cursor.execute('''
            INSERT INTO transactions (user_id, amount, type, description, ref_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, amount, 'deposit', 'تراکنش تست', ref_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'✅ تراکنش با موفقیت ثبت شد\n'
                      f'💰 مبلغ: {amount:,} تومان\n'
                      f'💎 موجودی جدید: {new_balance:,} تومان'
        })
        
    except sqlite3.Error as e:
        logging.error(f"Database error in test_transaction: {e}")
        return jsonify({
            'success': False,
            'message': f'❌ خطای دیتابیس: {str(e)}'
        })
    except Exception as e:
        logging.error(f"Error in test_transaction: {e}")
        return jsonify({
            'success': False,
            'message': f'❌ خطا: {str(e)}'
        })

@app.route('/test_check_balance', methods=['POST'])
@_require_admin
def test_check_balance():
    try:
        data = request.get_json()
        user_id = int(data['user_id'])
        balance = get_user_balance(user_id)
        
        return jsonify({
            'success': True,
            'message': f'💰 موجودی فعلی: {balance:,} تومان'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'❌ خطا: {str(e)}'})

@app.route('/test_payment')
@_require_admin
def test_payment_page():
    return render_template('test_payment.html')

@app.route('/recreate_transactions_table')
@_require_admin
def recreate_transactions_table():
    try:
        if setup_users_database():
            return jsonify({
                'success': True,
                'message': '✅ جدول تراکنش‌ها با موفقیت بازسازی شد'
            })
        else:
            return jsonify({
                'success': False,
                'message': '❌ خطا در بازسازی جدول تراکنش‌ها'
            })
    except Exception as e:
        logging.error(f"Error in recreate_transactions_table: {e}")
        return jsonify({
            'success': False,
            'message': f'❌ خطا: {str(e)}'
        })

# ایجاد نمونه از BackupManager
backup_manager = BackupManager(backup_interval=5)

@app.route('/test_backup')
@_require_admin
def test_backup_page():
    return render_template('test_backup.html')

@app.route('/create_backup')
@_require_admin
def create_backup():
    try:
        if backup_manager.create_backup():
            return jsonify({
                'success': True,
                'message': '✅ پشتیبان با موفقیت ایجاد شد'
            })
        return jsonify({
            'success': False,
            'message': '❌ خطا در ایجاد پشتیبان'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'❌ خطا: {str(e)}'
        })

@app.route('/restore_backup')
@_require_admin
def restore_backup():
    try:
        if backup_manager.restore_backup():
            return jsonify({
                'success': True,
                'message': '✅ بازیابی پشتیبان با موفقیت انجام شد'
            })
        return jsonify({
            'success': False,
            'message': '❌ خطا در بازیابی پشتیبان'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'❌ خطا: {str(e)}'
        })

@app.route('/backup_content')
@_require_admin
def backup_content():
    try:
        with open('data/users_backup.json', 'r', encoding='utf-8') as f:
            content = json.load(f)
        return jsonify({
            'success': True,
            'content': content
        })
    except FileNotFoundError:
        return jsonify({
            'success': False,
            'message': '❌ فایل پشتیبان یافت نشد'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'❌ خطا: {str(e)}'
        })

@app.route('/backup_status')
@_require_admin
def backup_status():
    return jsonify({
        'success': True,
        'message': f'✅ سرویس پشتیبان‌گیری فعال است\n'
                  f'⏱ فاصله زمانی: {backup_manager.backup_interval} ثانیه'
    })

def initialize_bot():
    """تابع راه‌اندازی اولیه ربات"""
    try:
        # بازیابی موجودی کاربران از فایل پشتیبان
        if backup_manager.restore_backup():
            logging.info("✅ موجودی کاربران با موفقیت بازیابی شد")
        else:
            logging.warning("⚠️ فایل پشتیبان یافت نشد یا مشکلی در بازیابی وجود دارد")
        
        # شروع سرویس پشتیبان‌گیری خودکار
        backup_manager.start()
        logging.info("✅ سرویس پشتیبان‌گیری خودکار فعال شد")
        
        return True
    except Exception as e:
        logging.error(f"❌ خطا در راه‌اندازی اولیه ربات: {e}")
        return False

@app.route('/check_database')
@_require_admin
def check_database():
    try:
        conn = sqlite3.connect(DB_CONFIG['users_db'])
        cursor = conn.cursor()
        
        # بررسی تعداد کاربران و مجموع موجودی
        cursor.execute('SELECT COUNT(*), SUM(balance) FROM users')
        users_count, total_balance = cursor.fetchone()
        
        # بررسی 5 کاربر اخیر - بدون استفاده از join_date
        cursor.execute('SELECT user_id, balance FROM users ORDER BY user_id DESC LIMIT 5')
        recent_users = cursor.fetchall()
        
        conn.close()
        
        return jsonify({
            'success': True,
            'stats': {
                'total_users': users_count or 0,
                'total_balance': total_balance or 0,
                'recent_users': [
                    {'user_id': uid, 'balance': bal}
                    for uid, bal in recent_users
                ]
            }
        })
    except Exception as e:
        logging.error(f"Error in check_database: {e}")
        return jsonify({
            'success': False,
            'message': f'❌ خطا در بررسی دیتابیس: {str(e)}'
        })

@app.route('/test_purchase')
@_require_admin
def test_purchase_page():
    return render_template('test_purchase.html')

@app.route('/test_get_services')
@_require_admin
def test_get_services():
    try:
        # استفاده از تابع واقعی ربات
        services = get_available_services()
        
        if not services:
            return jsonify({
                'success': False,
                'message': 'هیچ سرویسی یافت نشد'
            })

        logging.info(f"Available services: {services}")
        
        return jsonify({
            'success': True,
            'services': services
        })
    except Exception as e:
        logging.error(f"Error in test_get_services: {e}")
        return jsonify({
            'success': False,
            'message': f'خطا در دریافت سرویس‌ها: {str(e)}'
        })

@app.route('/test_get_countries/<service>')
@_require_admin
def test_get_countries(service):
    try:
        # استفاده از تابع واقعی ربات
        countries = get_countries_for_service(service)
        
        if not countries:
            return jsonify({
                'success': False,
                'message': 'هیچ کشوری برای این سرویس یافت نشد'
            })

        logging.info(f"Available countries for {service}: {countries}")
        
        return jsonify({
            'success': True,
            'countries': countries
        })
    except Exception as e:
        logging.error(f"Error in test_get_countries: {e}")
        return jsonify({
            'success': False,
            'message': f'خطا در دریافت لیست کشورها: {str(e)}'
        })

@app.route('/test_get_number', methods=['POST'])
@_require_admin
def test_get_number():
    try:
        data = request.get_json()
        service = data['service']
        country = data['country']
        
        # استفاده از توابع واقعی ربات
        products = get_products(country)
        if not products:
            return jsonify({
                'success': False,
                'message': 'شماره‌ای برای این سرویس و کشور یافت نشد'
            })

        # دریافت قیمت
        price = get_prices(products[0])
        if not price:
            return jsonify({
                'success': False,
                'message': 'خطا در دریافت قیمت'
            })

        return jsonify({
            'success': True,
            'number': products[0],  # شماره موجود
            'price': price,
            'service': service,
            'country': country
        })
    except Exception as e:
        logging.error(f"Error in test_get_number: {e}")
        return jsonify({
            'success': False,
            'message': f'خطا در دریافت شماره: {str(e)}'
        })

@app.route('/test_purchase_number', methods=['POST'])
@_require_admin
def test_purchase_number():
    try:
        data = request.get_json()
        service = data['service']
        country = data['country']
        number = data['number']
        
        # بررسی موجودی کاربر (برای تست از یک کاربر ثابت استفاده می‌کنیم)
        test_user_id = 1457637832  # می‌توانید این را تغییر دهید
        user_balance = get_user_balance(test_user_id)
        price = get_prices(number)

        if user_balance < price:
            return jsonify({
                'success': False,
                'message': 'موجودی کافی نیست'
            })

        # انجام خرید با استفاده از API واقعی
        order_id = f'TEST{int(time.time())}'
        
        # کم کردن موجودی کاربر
        new_balance = add_balance(test_user_id, -price)
        if new_balance is None:
            return jsonify({
                'success': False,
                'message': 'خطا در بروزرسانی موجودی'
            })

        # ذخیره اطلاعات سفارش در دیتابیس
        conn = sqlite3.connect(DB_CONFIG['users_db'])
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO orders 
            (user_id, service, country, phone_number, price, status, order_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (test_user_id, service, country, number, price, 'active', order_id))
        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'order_id': order_id,
            'number': number,
            'price': price,
            'balance': new_balance
        })
        
    except Exception as e:
        logging.error(f"Error in test_purchase_number: {e}")
        return jsonify({
            'success': False,
            'message': f'خطا در خرید شماره: {str(e)}'
        })

# در ابتدای فایل bot.py
def create_required_tables():
    try:
        conn = sqlite3.connect('orders.db')
        cursor = conn.cursor()
        
        # بررسی ستون‌های موجود
        cursor.execute("PRAGMA table_info(orders)")
        columns = cursor.fetchall()
        existing_columns = [column[1] for column in columns]
        
        # اگر جدول وجود نداشت، آن را بساز
        if not existing_columns:
            cursor.execute('''
                CREATE TABLE orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    phone TEXT NOT NULL,
                    service TEXT NOT NULL,
                    country TEXT NOT NULL,
                    operator TEXT NOT NULL,
                    price REAL NOT NULL,
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    created_at TEXT NOT NULL
                )
            ''')
        else:
            # اضافه کردن ستون‌های جدید اگر وجود نداشتند
            if 'phone' not in existing_columns:
                cursor.execute('ALTER TABLE orders ADD COLUMN phone TEXT')
            if 'status' not in existing_columns:
                cursor.execute('ALTER TABLE orders ADD COLUMN status TEXT DEFAULT "PENDING"')
            if 'service' not in existing_columns:
                cursor.execute('ALTER TABLE orders ADD COLUMN service TEXT')
            if 'country' not in existing_columns:
                cursor.execute('ALTER TABLE orders ADD COLUMN country TEXT')
            if 'operator' not in existing_columns:
                cursor.execute('ALTER TABLE orders ADD COLUMN operator TEXT')
            if 'created_at' not in existing_columns:
                cursor.execute('ALTER TABLE orders ADD COLUMN created_at TEXT')
        
        conn.commit()
        conn.close()
        logging.info("جداول با موفقیت بروزرسانی شدند")
        return True
        
    except Exception as e:
        logging.error(f"خطا در ایجاد جداول مورد نیاز: {str(e)}")
        return False

def save_order(order_data):
    try:
        conn = sqlite3.connect('bot.db')
        cursor = conn.cursor()
        
        # اطمینان از وجود جدول orders
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                activation_id INTEGER NOT NULL,
                service TEXT NOT NULL,
                country TEXT NOT NULL,
                operator TEXT NOT NULL,
                phone TEXT NOT NULL,
                price INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # اطمینان از وجود جدول activation_codes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS activation_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                code TEXT NOT NULL,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES orders(id)
            )
        ''')
        
        # درج سفارش جدید
        cursor.execute('''
            INSERT INTO orders (
                user_id, activation_id, service, country, 
                operator, phone, price, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            order_data['user_id'],
            order_data['activation_id'],
            order_data['service'],
            order_data['country'],
            order_data['operator'],
            order_data['phone'],
            order_data['price'],
            order_data['status']
        ))
        
        # دریافت شناسه سفارش ذخیره شده
        order_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        logging.info(f"Order saved successfully: {order_data} with id {order_id}")
        return order_id
        
    except Exception as e:
        logging.error(f"خطا در ذخیره سفارش: {e}")
        if 'conn' in locals():
            conn.close()
        return None

@app.route('/price_calculator')
@_require_admin
def price_calculator():
    try:
        # دریافت نرخ دلار و درصد سود از دیتابیس
        conn = sqlite3.connect('bot.db')
        cursor = conn.cursor()
        
        cursor.execute("SELECT value FROM settings WHERE key='usd_rate'")
        usd_rate = cursor.fetchone()[0]
        
        cursor.execute("SELECT value FROM settings WHERE key='profit_percentage'")
        profit_percentage = cursor.fetchone()[0]
        
        conn.close()
        
        return render_template('price_calculator.html', 
                             usd_rate=usd_rate,
                             profit_percentage=profit_percentage)
    except Exception as e:
        logging.error(f"Error in price_calculator: {e}")
        return "خطا در بارگذاری صفحه"

@app.route('/update_usd_rate')
@_require_admin
def update_usd_rate():
    try:
        api_key = 'free26Ln3Pt7qXlEydjJYJEKDcjEYKuS'  # API key ناواسان
        response = requests.get(f'https://api.navasan.tech/latest/?api_key={api_key}&item=rub')
        data = response.json()
        
        if data.get('rub'):
            new_rate = float(data['rub']['value'])
            
            # ذخیره نرخ جدید در دیتابیس
            conn = sqlite3.connect('bot.db')
            cursor = conn.cursor()
            cursor.execute("UPDATE settings SET value = ? WHERE key = 'usd_rate'", (str(new_rate),))
            conn.commit()
            conn.close()
            
            return jsonify({
                'success': True,
                'rate': new_rate,
                'date': data['rub']['date'],
                'change': data['rub']['change']
            })
        else:
            return jsonify({
                'success': False,
                'error': 'نرخ دلار یافت نشد'
            })
            
    except Exception as e:
        logging.error(f"Error in update_usd_rate: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/get_usd_rate')
@_require_admin
def get_usd_rate():
    try:
        import requests
        
        api_key = 'free26Ln3Pt7qXlEydjJYJEKDcjEYKuS'
        response = requests.get(f'https://api.navasan.tech/latest/?api_key={api_key}&item=rub')
        data = response.json()
        
        if data.get('rub'):
            return jsonify({
                'success': True,
                'rate': float(data['rub']['value']),
                'date': data['rub']['date'],
                'change': data['rub']['change']
            })
        else:
            return jsonify({
                'success': False,
                'error': 'نرخ دلار یافت نشد'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/get_settings')
@_require_admin
def get_settings():
    try:
        conn = sqlite3.connect('admin.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT value FROM settings WHERE key = "current_rate"')
        rate_result = cursor.fetchone()
        current_rate = float(rate_result[0]) if rate_result else 1000
        
        cursor.execute('SELECT value FROM settings WHERE key = "profit_percentage"')
        profit_result = cursor.fetchone()
        profit_percentage = float(profit_result[0]) if profit_result else 20
        
        conn.close()
        
        return jsonify({
            'success': True,
            'current_rate': current_rate,
            'profit_percentage': profit_percentage
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/telegram_prices')
@_require_admin
def telegram_prices():
    return render_template('telegram_prices.html')

@app.route('/api/get_telegram_price/<country>')
@_require_admin
def get_telegram_price(country):
    try:
        country_id = COUNTRY_ID_MAP.get(country, country)
        service_code = SERVICE_CODE_MAP.get('telegram', 'tg')
        
        params = {
            'api_key': HEROSMS_CONFIG['api_key'],
            'action': 'getPrices',
            'country': country_id,
            'service': service_code
        }
        
        response = requests.get(
            HEROSMS_CONFIG['api_url'],
            params=params,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            
            if country_id in data and service_code in data[country_id]:
                operators = data[country_id][service_code]
                
                min_price = float('inf')
                available_count = 0
                
                for operator_data in operators.values():
                    if operator_data['count'] > 0 and operator_data['cost'] < min_price:
                        min_price = operator_data['cost']
                        available_count = operator_data['count']
                
                if min_price != float('inf'):
                    # دریافت نرخ دلار از دیتابیس admin.db
                    conn = sqlite3.connect('admin.db')
                    cursor = conn.cursor()
                    
                    # دریافت نرخ دلار
                    cursor.execute('SELECT value FROM settings WHERE key = "usd_rate"')
                    usd_rate_result = cursor.fetchone()
                    usd_rate = float(usd_rate_result[0]) if usd_rate_result else 0
                    
                    # دریافت درصد سود
                    cursor.execute('SELECT value FROM settings WHERE key = "profit_percentage"')
                    profit_result = cursor.fetchone()
                    profit_percentage = float(profit_result[0]) if profit_result else 0
                    
                    conn.close()
                    
                    if usd_rate == 0:
                        logging.error("نرخ دلار صفر است. لطفاً ابتدا نرخ دلار را تنظیم کنید.")
                        return jsonify({
                            'status': 'خطا',
                            'price_usd': min_price,
                            'price_toman': 0,
                            'available_count': available_count,
                            'error': 'نرخ دلار تنظیم نشده است'
                        })
                    
                    # محاسبه قیمت نهایی
                    final_price_usd = min_price
                    final_price_toman = round(min_price * usd_rate * (1 + profit_percentage/100))
                    
                    logging.info(f"""
                    محاسبه قیمت برای {country}:
                    قیمت پایه (دلار): {min_price}
                    نرخ دلار: {usd_rate}
                    درصد سود: {profit_percentage}%
                    قیمت نهایی (تومان): {final_price_toman}
                    تعداد موجود: {available_count}
                    """)
                    
                    return jsonify({
                        'status': 'موجود',
                        'price_usd': final_price_usd,
                        'price_toman': final_price_toman,
                        'available_count': available_count
                    })
                    
                # ... rest of the code remains the same ...
    except Exception as e:
        logging.error(f"Error in get_telegram_price: {e}")
        return jsonify({
            'success': False,
            'message': f'خطا در دریافت قیمت برای {country}: {str(e)}'
        })

@app.route('/test_api_key')
@_require_admin
def test_api_key():
    try:
        params = {
            'api_key': HEROSMS_CONFIG['api_key'],
            'action': 'getBalance'
        }
        
        response = requests.get(HEROSMS_CONFIG['api_url'], params=params, timeout=10)
        
        if response.status_code == 200 and 'ACCESS_BALANCE' in response.text:
            return jsonify({
                'status': 'success',
                'message': f'کلید API معتبر است - موجودی: {response.text.strip()}'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'خطا در اعتبارسنجی کلید API: {response.text}'
            })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'خطا در تست کلید API: {str(e)}'
        })

# در بخش if __name__ == '__main__':
if __name__ == '__main__':
    try:
        # ایجاد جداول مورد نیاز
        if not create_required_tables():
            logging.error("❌ خطا در ایجاد جداول مورد نیاز")
            exit(1)
            
        # راه‌اندازی دیتابیس و بازیابی موجودی‌ها
        if not setup_database():
            logging.error("❌ خطا در راه‌اندازی دیتابیس")
            exit(1)
            
        # بازیابی اطلاعات از فایل پشتیبان
        backup_file = 'data/users_backup.json'
        if os.path.exists(backup_file):
            with open(backup_file, 'r', encoding='utf-8') as f:
                users_data = json.load(f)
                
            conn = sqlite3.connect(DB_CONFIG['users_db'])
            cursor = conn.cursor()
            
            for user_id, balance in users_data.items():
                cursor.execute('''
                    INSERT OR REPLACE INTO users (user_id, balance)
                    VALUES (?, ?)
                ''', (int(user_id), balance))
            
            conn.commit()
            conn.close()
            logging.info(f"✅ موجودی {len(users_data)} کاربر از فایل پشتیبان بازیابی شد")
        
        # شروع سرویس پشتیبان‌گیری
        backup_manager = BackupManager(backup_interval=5)
        backup_manager.start()
        
        # راه‌اندازی ربات
        bot.remove_webhook()
        bot.set_webhook(url=BOT_CONFIG['webhook_url'])
        
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=False
        )
        
    except Exception as e:
        logging.error(f"Error in main: {e}")
        exit(1)

@bot.callback_query_handler(func=lambda call: call.data == "no_operator")
def handle_no_operator(call):
    bot.answer_callback_query(call.id, get_text(call.from_user.id, 'services.no_operator'))

# تابع کمکی برای فرمت کردن اعداد
@app.template_filter('format_number')
def format_number(value):
    return "{:,}".format(value)
