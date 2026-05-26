"""
bot/handlers/services.py — Service & Country Selection Handler
─────────────────────────────────────────────────
Handles: buy_number flow → service list → country list.
THIN handler — delegates to SMSService for prices, uses keyboard builders.

ZERO money operations — only display.
"""

import logging
from telebot import types
from bot.client import telegram_client
from bot.keyboards.main_keyboard import services_keyboard, countries_keyboard
from services.sms_service import SMSService
from services.settings_service import SettingsService
from data.service_countries import SERVICE_COUNTRIES, _get_countries_for_service
from i18n import get_text
from config import COUNTRY_ID_MAP, SERVICE_CODE_MAP

logger = logging.getLogger(__name__)

_sms_service = SMSService()
_settings = SettingsService()


def register_service_handlers(bot):
    """Register service selection handlers with a telebot instance."""

    # ── Buy Number → Show Services ─────────────────────────────

    @bot.callback_query_handler(func=lambda call: call.data == 'buy_number')
    def handle_buy_number(call):
        user_id = call.from_user.id
        telegram_client.edit(
            call.message.chat.id, call.message.message_id,
            get_text(user_id, 'services.select'),
            reply_markup=services_keyboard(user_id)
        )

    # ── Service Selected → Show Countries ──────────────────────

    @bot.callback_query_handler(func=lambda call: call.data.startswith('service_'))
    def handle_service_selection(call):
        user_id = call.from_user.id
        service = call.data.split('_')[1]

        # Get countries from single source of truth
        countries = _get_countries_for_service(service)

        if not countries:
            telegram_client.answer_callback(call, get_text(user_id, 'services.error_fetch'))
            return

        telegram_client.edit(
            call.message.chat.id, call.message.message_id,
            get_text(user_id, 'countries.select', service=service),
            reply_markup=countries_keyboard(user_id, service, countries)
        )

    # ── Country Selected → Show Price + Buy Button ─────────────

    @bot.callback_query_handler(func=lambda call: call.data.startswith('country_'))
    def handle_country_selection(call):
        user_id = call.from_user.id
        parts = call.data.split('_')
        service = parts[1]
        country = parts[2]

        # Get operator info
        from operator_config import OperatorConfig
        op_config = OperatorConfig()
        operator, country_name = op_config.get_operator_info(service, country)

        if not country_name:
            country_name = get_text(user_id, f'countries.{country}')

        if not operator:
            operator = 'virtual4'

        # Get price info via service (cached!)
        price_info = _sms_service.get_price_info(service, country)

        keyboard = types.InlineKeyboardMarkup(row_width=2)

        if price_info and price_info.available_count > 0:
            keyboard.add(types.InlineKeyboardButton(
                get_text(user_id, 'purchase.buy_button', operator=price_info.operator),
                callback_data=f"buy_number_{service}_{country}_{price_info.operator}"
            ))
        else:
            keyboard.add(types.InlineKeyboardButton(
                get_text(user_id, 'purchase.unavailable'),
                callback_data="no_operator"
            ))

        keyboard.add(types.InlineKeyboardButton(
            get_text(user_id, 'navigation.back_to_services'),
            callback_data="back_to_services"
        ))

        # Build message
        message_text = get_text(
            user_id, 'countries.selected',
            country=country_name, service=service
        )

        if price_info:
            price_text = get_text(user_id, 'purchase.price_line',
                price=price_info.price_toman,
                count=price_info.available_count,
                operator=price_info.operator)
            message_text += f"\n\n{price_text}"

        message_text += f"\n\n{get_text(user_id, 'purchase.buy_prompt')}"

        telegram_client.edit(
            call.message.chat.id, call.message.message_id,
            message_text, reply_markup=keyboard
        )

    # ── Back to Services ───────────────────────────────────────

    @bot.callback_query_handler(func=lambda call: call.data == "back_to_services")
    def back_to_services(call):
        telegram_client.edit(
            call.message.chat.id, call.message.message_id,
            get_text(call.from_user.id, 'services.select'),
            reply_markup=services_keyboard(call.from_user.id)
        )

    # ── Back to Main ───────────────────────────────────────────

    @bot.callback_query_handler(func=lambda call: call.data == "back_to_main")
    def back_to_main(call):
        from bot.keyboards.main_keyboard import main_menu_keyboard
        telegram_client.edit(
            call.message.chat.id, call.message.message_id,
            get_text(call.from_user.id, 'welcome_back'),
            reply_markup=main_menu_keyboard(call.from_user.id)
        )

    # ── No Operator Available ──────────────────────────────────

    @bot.callback_query_handler(func=lambda call: call.data == "no_operator")
    def handle_no_operator(call):
        telegram_client.answer_callback(call, get_text(call.from_user.id, 'services.no_operator'))

    logger.info("Registered: service/country selection handlers")