"""
i18n.py — Internationalization (Enterprise Refactored)
─────────────────────────────────────────────────
Multi-language support (fa, en, ar).
Uses SettingsRepository for user language persistence.
No direct sqlite3 connections.
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

# Load translation files
_LOCALES = {}
_locale_dir = os.path.join(os.path.dirname(__file__), 'locales')

for filename in os.listdir(_locale_dir):
    if filename.endswith('.json'):
        lang_code = filename.replace('.json', '')
        filepath = os.path.join(_locale_dir, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                _LOCALES[lang_code] = json.load(f)
                logger.info(f"Loaded locale: {lang_code}")
        except Exception as e:
            logger.error(f"Failed to load locale {lang_code}: {e}")

DEFAULT_LANGUAGE = 'fa'


def get_all_languages():
    """Return list of available languages."""
    langs = []
    for code, data in _LOCALES.items():
        if '_meta' in data:
            langs.append({
                'code': code,
                'name': data['_meta'].get('language', code),
                'direction': data['_meta'].get('direction', 'ltr'),
            })
    return langs


def get_user_language(user_id):
    """Get user's language preference from database."""
    try:
        from db.repositories.user_repository import UserRepository
        repo = UserRepository()
        lang = repo.get_language(user_id)
        return lang if lang in _LOCALES else DEFAULT_LANGUAGE
    except Exception as e:
        logger.error(f"Error getting user language: {e}")
        return DEFAULT_LANGUAGE


def set_user_language(user_id, lang_code):
    """Set user's language preference."""
    try:
        if lang_code not in _LOCALES:
            logger.warning(f"Invalid language code: {lang_code}")
            return False
        from db.repositories.user_repository import UserRepository
        repo = UserRepository()
        return repo.set_language(user_id, lang_code)
    except Exception as e:
        logger.error(f"Error setting user language: {e}")
        return False


def get_text(user_id, key, **kwargs):
    """
    Get translated text for a key in user's language.
    
    Args:
        user_id: Telegram user ID
        key: Dot-notation key path (e.g., 'main_menu.buy_number')
        **kwargs: Format arguments for the text
    
    Returns:
        Translated and formatted string, or key if not found
    """
    try:
        lang = get_user_language(user_id)
        data = _LOCALES.get(lang, _LOCALES.get(DEFAULT_LANGUAGE, {}))
        keys = key.split('.')
        value = data
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    break
            else:
                value = None
                break

        if value is None:
            # Fallback to default language
            data = _LOCALES.get(DEFAULT_LANGUAGE, {})
            value = data
            for k in keys:
                if isinstance(value, dict):
                    value = value.get(k)
                    if value is None:
                        break
                else:
                    value = None
                    break

        if value is None:
            return f"[{key}]"

        if kwargs and isinstance(value, str):
            try:
                return value.format(**kwargs)
            except (KeyError, ValueError):
                return value

        return str(value) if not isinstance(value, str) else value

    except Exception as e:
        logger.error(f"Error getting text for key '{key}': {e}")
        return f"[{key}]"
