import os
from dotenv import load_dotenv

# Load environment variables from .env file (if exists)
# Falls back gracefully if .env is missing or dotenv is not installed
try:
    load_dotenv()
except Exception:
    pass

# تنظیمات اصلی ربات
BOT_CONFIG = {
    'token': os.getenv('BOT_TOKEN', '8867840427:AAG56v1yGp4XBjL2-vlhHIhPR765NikFhDI'),
    'admin_ids': [int(x.strip()) for x in os.getenv('ADMIN_IDS', '8683874068').split(',')],
    'webhook_url': os.getenv('WEBHOOK_URL', 'https://abunumapp.com'),
    'website_url': os.getenv('WEBSITE_URL', 'https://abunumapp.com')
}

# تنظیمات hero-sms.com (SMS-Activate Protocol)
HEROSMS_CONFIG = {
    'api_key': os.getenv('HEROSMS_API_KEY', 'cb28fe1389Abce0053b2fb3bA48d6b4c'),
    'api_url': os.getenv('HEROSMS_API_URL', 'https://hero-sms.com/stubs/handler_api.php')
}

# نگاشت أسماء الدول إلى معرفات رقمية (SMS-Activate standard)
COUNTRY_ID_MAP = {
    'russia': '0',
    'philippines': '4',
    'indonesia': '6',
    'vietnam': '10',
    'cyprus': '12',
    'canada': '22',
    'poland': '36',
    'netherlands': '48',
    'estonia': '50',
    'slovenia': '52',
    'georgia': '56',
    'cambodia': '58',
    'ethiopia': '68',
    'dominican_republic': '82',
    'paraguay': '86',
    'suriname': '88',
    'maldives': '92',
    'cameroon': '94',
    'laos': '96',
    'benin': '98'
}

# نگاشت أسماء الخدمات إلى رموز SMS-Activate
SERVICE_CODE_MAP = {
    'telegram': 'tg',
    'whatsapp': 'wa',
    'instagram': 'ig',
    'google': 'go'
}

# تنظیمات API نرخ ارز
CURRENCY_CONFIG = {
    'navasan_api_key': os.getenv('NAVASAN_API_KEY', 'free26Ln3Pt7qXlEydjJYJEKDcjEYKuS')
}

# تنظیمات دیتابیس
DB_CONFIG = {
    'users_db': os.getenv('USERS_DB', 'users.db'),
    'admin_db': os.getenv('ADMIN_DB', 'admin.db')
}

# اضافه کردن تنظیمات درگاه پرداخت
PAYMENT_CONFIG = {
    'zarinpal_merchant': os.getenv('ZARINPAL_MERCHANT', '1344b5d4-0048-11e8-94db-005056a205be'),
    'sandbox_mode': os.getenv('ZARINPAL_SANDBOX', 'true').lower() == 'true',
    'callback_url': BOT_CONFIG['webhook_url'] + '/verify'  # آدرس برگشت از درگاه
}