# تنظیمات اصلی ربات
BOT_CONFIG = {
    'token': '7728660088:AAHW7p6ebM1m9Xpi9vTgPQDBaSOgOFPhaPM',
    'admin_ids': [1457637832],  # آیدی عددی ادمین‌ها - عدد را جایگزین کردم
    'webhook_url': 'https://clever-bluejay-charmed.ngrok-free.app',  # آدرس ngrok را اینجا قرار دهید
    'website_url': 'https://clever-bluejay-charmed.ngrok-free.app'  # آدرس سایت شما
}

# تنظیمات hero-sms.com (SMS-Activate Protocol)
HEROSMS_CONFIG = {
    'api_key': 'cb28fe1389Abce0053b2fb3bA48d6b4c',
    'api_url': 'https://hero-sms.com/stubs/handler_api.php'
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
    'navasan_api_key': 'free26Ln3Pt7qXlEydjJYJEKDcjEYKuS'
}

# تنظیمات دیتابیس
DB_CONFIG = {
    'users_db': 'users.db',
    'admin_db': 'admin.db'
}

# اضافه کردن تنظیمات درگاه پرداخت
PAYMENT_CONFIG = {
    'zarinpal_merchant': '1344b5d4-0048-11e8-94db-005056a205be',  # مرچنت کد تست زرین‌پال
    'sandbox_mode': True,  # True برای تست، False برای حالت اصلی
    'callback_url': BOT_CONFIG['webhook_url'] + '/verify'  # آدرس برگشت از درگاه
} 