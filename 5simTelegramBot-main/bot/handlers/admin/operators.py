"""
bot/handlers/admin/operators.py — Admin Operator Settings
"""

import logging

from telebot import types

from bot.router import router
from config import BOT_CONFIG
from data.service_countries import ALL_SERVICES, SERVICE_COUNTRIES
from i18n import get_text
from operator_config import OperatorConfig

logger = logging.getLogger(__name__)
_bot = None
_operator_config = OperatorConfig()

def init(bot_instance):
    global _bot; _bot = bot_instance

@router.callback('operator_settings')
def handle_operator_settings(call):
    user_id = call.from_user.id
    if user_id not in BOT_CONFIG['admin_ids']: _bot.answer_callback_query(call.id, get_text(user_id, 'errors.no_access')); return
    settings = _operator_config.get_all_settings()
    text = get_text(user_id, 'operators.settings_title')
    for svc_key in ALL_SERVICES:
        svc_name = get_text(user_id, f'operators.service_{svc_key}')
        text += f"🔹 {svc_name}:\n"
        from data.service_countries import get_countries_for_service as _gcf
        for country_code in _gcf(svc_key):
            country_name = get_text(user_id, f'countries.{country_code}')
            operator = next((s[2] for s in settings if s[0] == svc_key and s[1] == country_code), get_text(user_id, 'operators.not_set'))
            text += f"  • {country_name}: {operator}\n"
        text += "\n"
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'operators.change_settings'), callback_data="change_operator"), types.InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="admin_panel"))
    _bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)

@router.callback('change_operator')
def handle_change_operator(call):
    user_id = call.from_user.id
    if user_id not in BOT_CONFIG['admin_ids']: _bot.answer_callback_query(call.id, get_text(user_id, 'errors.no_access')); return
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'operators.service_telegram'), callback_data="select_service_telegram"), types.InlineKeyboardButton(get_text(user_id, 'operators.service_whatsapp'), callback_data="select_service_whatsapp"), types.InlineKeyboardButton(get_text(user_id, 'operators.service_instagram'), callback_data="select_service_instagram"), types.InlineKeyboardButton(get_text(user_id, 'operators.service_google'), callback_data="select_service_google"), types.InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="operator_settings"))
    _bot.edit_message_text(get_text(user_id, 'operators.select_service'), call.message.chat.id, call.message.message_id, reply_markup=keyboard)

@router.callback('select_service_')
def handle_select_service(call):
    user_id = call.from_user.id
    if user_id not in BOT_CONFIG['admin_ids']: _bot.answer_callback_query(call.id, get_text(user_id, 'errors.no_access')); return
    service = call.data.split('_')[2]
    if service not in SERVICE_COUNTRIES: _bot.answer_callback_query(call.id, get_text(user_id, 'operators.invalid_service')); return
    from data.service_countries import get_countries_for_service as _gcf
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    for country_code in _gcf(service): keyboard.add(types.InlineKeyboardButton(get_text(user_id, f'countries.{country_code}'), callback_data=f"select_country_{service}_{country_code}"))
    keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="change_operator"))
    _bot.edit_message_text(get_text(user_id, 'operators.select_country', service=service), call.message.chat.id, call.message.message_id, reply_markup=keyboard)

@router.callback('select_country_')
def handle_select_country(call):
    user_id = call.from_user.id; parts = call.data.split('_')
    service, country = parts[2], parts[3]
    msg = _bot.edit_message_text(get_text(user_id, 'operators.enter_operator'), call.message.chat.id, call.message.message_id)
    _bot.register_next_step_handler(msg, process_operator_change, service, country)

def process_operator_change(message, service, country):
    user_id = message.from_user.id; operator = message.text.strip().lower()
    if _operator_config.set_operator(service, country, operator):
        keyboard = types.InlineKeyboardMarkup(); keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_settings'), callback_data="operator_settings"))
        _bot.reply_to(message, get_text(user_id, 'operators.operator_changed', service=service, country=country, operator=operator), reply_markup=keyboard)
    else: _bot.reply_to(message, get_text(user_id, 'operators.operator_change_error'))
