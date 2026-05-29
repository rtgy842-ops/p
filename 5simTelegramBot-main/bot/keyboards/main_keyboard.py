"""
bot/keyboards/main_keyboard.py — Main Menu Keyboard
─────────────────────────────────────────────────
Centralized keyboard builders imported by handlers.
"""

from telebot import types
from i18n import get_text


def main_menu_keyboard(user_id: int) -> types.InlineKeyboardMarkup:
    """Build the main inline menu keyboard (Enterprise — NEW design)."""
    keyboard = types.InlineKeyboardMarkup(row_width=2)

    keyboard.add(
        types.InlineKeyboardButton(get_text(user_id, 'main_menu.buy_number'), callback_data='buy_number'),
        types.InlineKeyboardButton(get_text(user_id, 'main_menu.balance'), callback_data='check_balance'),
        types.InlineKeyboardButton(get_text(user_id, 'main_menu.my_orders'), callback_data='my_orders'),
        types.InlineKeyboardButton(get_text(user_id, 'main_menu.help'), callback_data='help'),
        types.InlineKeyboardButton(get_text(user_id, 'main_menu.add_funds'), callback_data='add_funds'),
        types.InlineKeyboardButton('🌐 ' + get_text(user_id, 'language.select_title'), callback_data='language_menu')
    )

    # Admin button (admin_ids check done in handler, not here)
    from config import BOT_CONFIG
    if user_id in BOT_CONFIG['admin_ids']:
        keyboard.add(types.InlineKeyboardButton(
            get_text(user_id, 'main_menu.admin_panel'), callback_data='admin_panel'
        ))

    return keyboard


def services_keyboard(user_id: int) -> types.InlineKeyboardMarkup:
    """Build the services selection keyboard."""
    keyboard = types.InlineKeyboardMarkup(row_width=2)

    main_services = [
        ('telegram', 'telegram'),
        ('whatsapp', 'whatsapp'),
        ('instagram', 'instagram'),
        ('google', 'google')
    ]

    for i in range(0, len(main_services), 2):
        buttons = []
        for j in range(2):
            if i + j < len(main_services):
                service_id, service_key = main_services[i + j]
                name = get_text(user_id, f'services.{service_key}')
                buttons.append(types.InlineKeyboardButton(name, callback_data=f'service_{service_id}'))
        keyboard.row(*buttons)

    keyboard.add(types.InlineKeyboardButton(
        get_text(user_id, 'navigation.back_to_main'), callback_data="back_to_main"
    ))

    return keyboard


def countries_keyboard(user_id: int, service: str, countries: list[str]) -> types.InlineKeyboardMarkup:
    """Build the country selection keyboard for a service."""
    keyboard = types.InlineKeyboardMarkup(row_width=2)

    for i in range(0, len(countries), 2):
        buttons = []
        for j in range(2):
            if i + j < len(countries):
                country_code = countries[i + j]
                country_name = get_text(user_id, f'countries.{country_code}')
                buttons.append(types.InlineKeyboardButton(
                    country_name, callback_data=f'country_{service}_{country_code}'
                ))
        keyboard.row(*buttons)

    keyboard.add(types.InlineKeyboardButton(
        get_text(user_id, 'navigation.back_to_services'), callback_data="back_to_services"
    ))

    return keyboard


def back_to_main_button(user_id: int) -> types.InlineKeyboardButton:
    """Standard 'back to main menu' button."""
    return types.InlineKeyboardButton(
        get_text(user_id, 'navigation.back_to_main'),
        callback_data="back_to_main"
    )