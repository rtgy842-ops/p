"""
i18n.py — Translation Service for 5sim/HeroSMS Telegram Bot
Supports: Persian (fa) | English (en) | Arabic (ar)
"""
import json
import os
import sqlite3
import logging
from config import DB_CONFIG

logger = logging.getLogger(__name__)

# ── Locale file paths ──────────────────────────────────────────
LOCALES_DIR = os.path.join(os.path.dirname(__file__), 'locales')
SUPPORTED_LANGUAGES = ['fa', 'en', 'ar']
DEFAULT_LANGUAGE = 'fa'

# ── Load all locale JSONs at module import ─────────────────────
_translations: dict[str, dict] = {}

def _load_locales() -> None:
    """بارگذاری تمام فایل‌های JSON ترجمه"""
    global _translations
    for lang in SUPPORTED_LANGUAGES:
        path = os.path.join(LOCALES_DIR, f'{lang}.json')
        try:
            with open(path, 'r', encoding='utf-8') as f:
                _translations[lang] = json.load(f)
            logger.info(f"✅ Locale loaded: {lang} ({path})")
        except FileNotFoundError:
            logger.warning(f"⚠️ Locale file not found: {path}")
            _translations[lang] = {}
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON in {path}: {e}")
            _translations[lang] = {}

_load_locales()


def get_user_language(user_id: int) -> str:
    """
    دریافت زبان ذخیره شده کاربر از دیتابیس.
    برمی‌گرداند: 'fa', 'en', یا 'ar'
    """
    try:
        conn = sqlite3.connect(DB_CONFIG['users_db'])
        cursor = conn.cursor()
        cursor.execute('SELECT language FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0] and result[0] in SUPPORTED_LANGUAGES:
            return result[0]
        return DEFAULT_LANGUAGE
    except sqlite3.OperationalError:
        # جدول users یا ستون language هنوز وجود ندارد
        return DEFAULT_LANGUAGE
    except Exception as e:
        logger.error(f"Error getting user language for {user_id}: {e}")
        return DEFAULT_LANGUAGE


def set_user_language(user_id: int, language: str) -> bool:
    """
    ذخیره زبان کاربر در دیتابیس.
    برمی‌گرداند: True اگر موفق بود
    """
    if language not in SUPPORTED_LANGUAGES:
        logger.warning(f"Unsupported language: {language}")
        return False
    
    try:
        conn = sqlite3.connect(DB_CONFIG['users_db'])
        cursor = conn.cursor()
        
        # اطمینان از وجود کاربر
        cursor.execute(
            'INSERT OR IGNORE INTO users (user_id, balance, language) VALUES (?, 0, ?)',
            (user_id, language)
        )
        # بروزرسانی زبان
        cursor.execute(
            'UPDATE users SET language = ? WHERE user_id = ?',
            (language, user_id)
        )
        
        conn.commit()
        conn.close()
        logger.info(f"User {user_id} language set to: {language}")
        return True
    except Exception as e:
        logger.error(f"Error setting language for user {user_id}: {e}")
        return False


def get_text(user_id: int, key: str, **kwargs) -> str:
    """
    دریافت متن ترجمه شده برای کاربر.
    
    Args:
        user_id: شناسه عددی کاربر تلگرام
        key: کلید ترجمه با dot-notation (مثال: "main_menu.buy_number")
        **kwargs: پارامترهای جایگزین برای format string
    
    Returns:
        متن ترجمه شده
    
    Example:
        get_text(123456, "wallet.title", balance=50000)
        # → "💰 *کیف پول شما*\n\nموجودی: `50,000 تومان`\n\n💡 حداقل شارژ: 20,000 تومان"
    """
    language = get_user_language(user_id)
    
    # navigation through nested dict with dot-notation
    translation = _translations.get(language, _translations.get(DEFAULT_LANGUAGE, {}))
    
    try:
        keys = key.split('.')
        value = translation
        for k in keys:
            value = value[k]
    except (KeyError, TypeError):
        # fallback to Persian
        try:
            fallback = _translations.get(DEFAULT_LANGUAGE, {})
            value = fallback
            for k in keys:
                value = value[k]
        except (KeyError, TypeError):
            logger.warning(f"Translation key not found: '{key}' for lang '{language}'")
            return f"⚠️ {key}"
    
    if not isinstance(value, str):
        logger.warning(f"Translation key '{key}' is not a string: {type(value)}")
        return f"⚠️ {key}"
    
    # Apply format args if provided
    if kwargs:
        try:
            return value.format(**kwargs)
        except KeyError as e:
            logger.warning(f"Missing format key {e} in translation '{key}'")
            return value
        except Exception as e:
            logger.warning(f"Format error in translation '{key}': {e}")
            return value
    
    return value


def get_all_languages() -> list[dict]:
    """برمی‌گرداند لیست زبان‌های پشتیبانی شده با جزئیات"""
    lang_names = {
        'fa': '🇮🇷 فارسی',
        'en': '🇬🇧 English',
        'ar': '🇸🇦 العربية'
    }
    return [
        {'code': code, 'name': lang_names.get(code, code)}
        for code in SUPPORTED_LANGUAGES
    ]


def is_rtl(user_id: int) -> bool:
    """آیا زبان کاربر راست‌به‌چپ است؟"""
    lang = get_user_language(user_id)
    return lang in ('fa', 'ar')


def reload_locales() -> None:
    """بارگذاری مجدد فایل‌های ترجمه (برای دیباگ)"""
    _load_locales()
    logger.info("All locales reloaded")
