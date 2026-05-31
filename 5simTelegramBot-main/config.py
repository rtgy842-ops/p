"""
config.py — Enterprise Configuration (Security-Hardened)
─────────────────────────────────────────────────
ALL secrets come from environment variables.
NO hardcoded defaults for secrets.
The _require() function validates at RUNTIME (not import time)
so tests and imports don't crash without .env.
"""

import os

from dotenv import load_dotenv

try:
    load_dotenv()
except Exception:
    pass


# ── Environment ───────────────────────────────────────────
APP_ENV = os.getenv('APP_ENV', 'production')
IS_DEVELOPMENT = APP_ENV == 'development'
IS_PRODUCTION = APP_ENV == 'production'


# ── Lazy secret getter (validates at runtime, not import) ──
_missing_secrets: set[str] = set()

def _env(key: str, default: str = '') -> str:
    """Get env var. Logs missing keys, raises only when validate() is called."""
    val = os.getenv(key)
    if not val and not default:
        _missing_secrets.add(key)
    return val or default

def validate_secrets() -> None:
    """Call this at app startup to fail fast on missing secrets."""
    if _missing_secrets:
        missing = ', '.join(sorted(_missing_secrets))
        msg = f"Missing required environment variables: {missing}"
        if IS_PRODUCTION:
            raise RuntimeError(f"{msg}\nSet them in your .env file and restart.")
        print(f"⚠️  WARNING: {msg}", flush=True)


BOT_CONFIG = {
    'token': _env('BOT_TOKEN'),
    'admin_ids': [int(x.strip()) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()],
    'webhook_url': _env('WEBHOOK_URL'),
    'website_url': os.getenv('WEBSITE_URL') or os.getenv('WEBHOOK_URL', ''),
}

HEROSMS_CONFIG = {
    'api_key': _env('HEROSMS_API_KEY'),
    'api_url': os.getenv('HEROSMS_API_URL', 'https://hero-sms.com/stubs/handler_api.php'),
}

CURRENCY_CONFIG = {
    'navasan_api_key': _env('NAVASAN_API_KEY'),
}

PAYMENT_CONFIG = {
    'zarinpal_merchant': _env('ZARINPAL_MERCHANT'),
    'sandbox_mode': os.getenv('ZARINPAL_SANDBOX', 'false').lower() == 'true',
    'callback_url': (os.getenv('WEBHOOK_URL') or '') + '/verify',
}

# ── Database ─────────────────────────────────────────────
DATABASE_URL = _env('DATABASE_URL')
DB_CONFIG = {'users_db': 'default', 'admin_db': 'default'}

# ── Redis / Celery ───────────────────────────────────────
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

# ── Flask / Security ─────────────────────────────────────
FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
FLASK_PORT = int(os.getenv('FLASK_PORT', '5000'))
FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
SECRET_KEY = os.getenv('SECRET_KEY', os.urandom(32).hex())

# ── Admin API ────────────────────────────────────────────
ADMIN_API_TOKEN = os.getenv('ADMIN_API_TOKEN', '')

# ── Logging ──────────────────────────────────────────────
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# ── Backup ───────────────────────────────────────────────
BACKUP_INTERVAL_SECONDS = int(os.getenv('BACKUP_INTERVAL_SECONDS', '300'))
BACKUP_FILE = os.getenv('BACKUP_FILE', 'data/users_backup.json')


# ═══════════════════════════════════════════════════════════
# CODE CONSTANTS (non-sensitive — safe in version control)
# ═══════════════════════════════════════════════════════════

COUNTRY_ID_MAP = {
    'russia': '0',       'philippines': '4',    'indonesia': '6',
    'vietnam': '10',     'cyprus': '12',        'canada': '22',
    'poland': '36',      'netherlands': '48',   'estonia': '50',
    'slovenia': '52',    'georgia': '56',       'cambodia': '58',
    'ethiopia': '68',    'dominican_republic': '82', 'paraguay': '86',
    'suriname': '88',    'maldives': '92',      'cameroon': '94',
    'laos': '96',        'benin': '98',
}

SERVICE_CODE_MAP = {
    'telegram': 'tg', 'whatsapp': 'wa',
    'instagram': 'ig', 'google': 'go',
}
