"""
data/service_countries.py — Single Source of Truth
─────────────────────────────────────────────────
Centralized mapping of services → countries → operators.
Import from here instead of duplicating across bot.py, operator_config.py, etc.

Usage:
    from data.service_countries import SERVICE_COUNTRIES, get_countries_for_service

This eliminates 7 duplicate copies of the same data across the codebase.
"""

# ── Complete service → country → operator mapping ──────────────
# Format: { 'service_code': [(country_code, country_i18n_key, default_operator), ...] }

SERVICE_COUNTRIES: dict[str, list[tuple[str, str, str]]] = {
    'telegram': [
        ('cyprus',    'قبرص 🇨🇾',             'virtual4'),
        ('paraguay',  'پاراگوئه 🇵🇾',         'virtual4'),
        ('maldives',  'مالدیو 🇲🇻',            'virtual4'),
        ('suriname',  'سورینام 🇸🇷',          'virtual4'),
        ('slovenia',  'اسلوونی 🇸🇮',           'virtual4'),
        ('canada',    'کانادا 🇨🇦',             'virtual8'),
    ],
    'whatsapp': [
        ('georgia',             'گرجستان 🇬🇪',             'virtual4'),
        ('cameroon',            'کامرون 🇨🇲',               'virtual4'),
        ('laos',                'لائوس 🇱🇦',                 'virtual4'),
        ('benin',               'بنین 🇧🇯',                  'virtual4'),
        ('dominican_republic',  'جمهوری دومینیکن 🇩🇴',     'virtual4'),
    ],
    'instagram': [
        ('poland',       'لهستان 🇵🇱',        'virtual53'),
        ('philippines',  'فیلیپین 🇵🇭',       'virtual38'),
        ('netherlands',  'هلند 🇳🇱',           'virtual52'),
        ('estonia',      'استونی 🇪🇪',         'virtual38'),
        ('vietnam',      'ویتنام 🇻🇳',         'virtual4'),
    ],
    'google': [
        ('cambodia',     'کامبوج 🇰🇭',        'virtual4'),
        ('philippines',  'فیلیپین 🇵🇭',       'virtual58'),
        ('indonesia',    'اندونزی 🇮🇩',        'virtual4'),
        ('ethiopia',     'اتیوپی 🇪🇹',          'virtual4'),
        ('russia',       'روسیه 🇷🇺',           'mts'),
    ],
}

# ── Service display names (i18n keys) ──────────────────────────
SERVICE_DISPLAY_KEYS: dict[str, str] = {
    'telegram':  'telegram',
    'whatsapp':  'whatsapp',
    'instagram': 'instagram',
    'google':    'google',
}

# ── All supported services (ordered) ───────────────────────────
ALL_SERVICES: list[str] = ['telegram', 'whatsapp', 'instagram', 'google']


def get_countries_for_service(service: str) -> list[str]:
    """Return list of country_codes for a given service."""
    entry = SERVICE_COUNTRIES.get(service, [])
    return [country[0] for country in entry]


def get_default_operator(service: str, country: str) -> str | None:
    """Return the default operator for a service+country pair."""
    entry = SERVICE_COUNTRIES.get(service, [])
    for c_code, _c_name, operator in entry:
        if c_code == country:
            return operator
    return None


def get_country_name(service: str, country: str) -> str | None:
    """Return the display name for a service+country pair."""
    entry = SERVICE_COUNTRIES.get(service, [])
    for c_code, c_name, _operator in entry:
        if c_code == country:
            return c_name
    return None


def get_all_service_countries() -> list[tuple[str, str, str, str]]:
    """
    Return flat list of (service, country_code, country_name, operator) tuples.
    Useful for database seeding and admin settings display.
    """
    result = []
    for svc, countries in SERVICE_COUNTRIES.items():
        for c_code, c_name, operator in countries:
            result.append((svc, c_code, c_name, operator))
    return result
