"""
bot/handlers/purchase.py — Purchase Flow Handlers
──────────────────────────────────────────────────
service_selection → country_selection → buy_number → get_code → cancel_order
All use compat layer (WalletService, SMSService, OrderService ready).
"""

import logging
from bot.router import router
from i18n import get_text
from config import BOT_CONFIG

logger = logging.getLogger(__name__)

_bot = None


def init(bot_instance):
    global _bot
    _bot = bot_instance


@router.callback('back_to_services')
def back_to_services(call):
    from bot.handlers.services import services_keyboard_wrapper
    _bot.edit_message_text(
        get_text(call.from_user.id, 'services.select'),
        call.message.chat.id,
        call.message.message_id,
        reply_markup=services_keyboard_wrapper(call.from_user.id)
    )


@router.callback('no_operator')
def handle_no_operator(call):
    _bot.answer_callback_query(call.id, get_text(call.from_user.id, 'services.no_operator'))


@router.callback('buy_number_')
def handle_buy_number(call):
    """Comprehensive purchase flow via compat layer."""
    from telebot import types
    from compat.legacy_facade import (
        get_balance as compat_get_balance,
        deduct_balance as compat_deduct_balance,
        sms_buy_number as compat_sms_buy_number,
        order_save as compat_order_save,
    )
    from data.service_countries import get_countries_for_service, get_country_name as _get_country_name
    from operator_config import OperatorConfig

    try:
        user_id = call.from_user.id
        balance = compat_get_balance(user_id)

        parts = call.data.split('_')
        service = parts[2]
        country = parts[3]
        operator = parts[4]

        op_config = OperatorConfig()
        config_operator, country_name = op_config.get_operator_info(service, country)
        if not country_name:
            country_name = get_text(user_id, f'countries.{country}')

        # Get price from compat layer
        from config import COUNTRY_ID_MAP, SERVICE_CODE_MAP, HEROSMS_CONFIG
        import requests

        country_id = COUNTRY_ID_MAP.get(country, country)
        service_code = SERVICE_CODE_MAP.get(service, service)
        params = {'api_key': HEROSMS_CONFIG['api_key'], 'action': 'getPrices', 'country': country_id, 'service': service_code}
        response = requests.get(HEROSMS_CONFIG['api_url'], params=params, timeout=10)

        if response.status_code != 200:
            _bot.answer_callback_query(call.id, get_text(user_id, 'purchase.price_fetch_error'))
            return

        data = response.json()
        if country_id not in data or service_code not in data[country_id]:
            _bot.answer_callback_query(call.id, get_text(user_id, 'purchase.service_country_unavailable'))
            return

        operators_data = data[country_id][service_code]
        if operator not in operators_data or operators_data[operator]['count'] <= 0:
            _bot.edit_message_text(
                get_text(user_id, 'purchase.operator_unavailable', operator=operator, country=country_name, service=service),
                call.message.chat.id, call.message.message_id,
                reply_markup=types.InlineKeyboardMarkup().add(
                    types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_services'), callback_data="back_to_services"))
            )
            return

        price_usd = operators_data[operator]['cost']

        # Get USD rate + profit
        import sqlite3
        conn = sqlite3.connect('admin.db')
        cursor = conn.cursor()
        cursor.execute('SELECT value FROM settings WHERE key = "usd_rate"')
        usd_rate = float(cursor.fetchone()[0]) if cursor.fetchone() else 0
        cursor.execute('SELECT value FROM settings WHERE key = "profit_percentage"')
        profit_pct = float(cursor.fetchone()[0]) if cursor.fetchone() else 0
        conn.close()

        price_toman = round(price_usd * usd_rate * (1 + profit_pct / 100))

        if balance < price_toman:
            keyboard = types.InlineKeyboardMarkup(row_width=1)
            keyboard.add(
                types.InlineKeyboardButton(get_text(user_id, 'main_menu.add_funds'), callback_data="add_funds"),
                types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_services'), callback_data="back_to_services")
            )
            deficit = price_toman - balance
            _bot.edit_message_text(
                get_text(user_id, 'purchase.insufficient_balance', balance=balance, price=price_toman, deficit=deficit),
                call.message.chat.id, call.message.message_id, reply_markup=keyboard
            )
            return

        # Buy the number
        _bot.edit_message_text(
            get_text(user_id, 'purchase.buying', service=service, country=country_name),
            call.message.chat.id, call.message.message_id
        )

        result = compat_sms_buy_number(country, operator, service)

        if result and result.get('success') and 'data' in result:
            order_data = result['data']
            activation_id = order_data['order_id']
            phone_number = order_data['phone']

            # Deduct balance via compat
            compat_deduct_balance(user_id, price_toman, description=f'خرید شماره {service} در {country}')

            # Save order via compat
            order_info = {
                'user_id': user_id, 'activation_id': activation_id, 'service': service,
                'country': country, 'operator': operator, 'phone': phone_number,
                'price': price_toman, 'status': 'PENDING'
            }
            local_id = compat_order_save(order_info)

            if local_id:
                details_url = f"{BOT_CONFIG['website_url']}/number_details/{local_id}"
                keyboard = types.InlineKeyboardMarkup(row_width=1)
                keyboard.add(
                    types.InlineKeyboardButton(get_text(user_id, 'purchase.get_code'), callback_data=f"get_code_{activation_id}"),
                    types.InlineKeyboardButton(get_text(user_id, 'purchase.cancel_order'), callback_data=f"cancel_order_{activation_id}"),
                    types.InlineKeyboardButton(get_text(user_id, 'purchase.view_details_web'), url=details_url),
                    types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_services'), callback_data="back_to_services")
                )
                _bot.edit_message_text(
                    get_text(user_id, 'purchase.success', service=service, country=country_name,
                             phone=phone_number, operator=operator, price=price_toman),
                    call.message.chat.id, call.message.message_id, reply_markup=keyboard
                )
            else:
                _bot.edit_message_text(get_text(user_id, 'purchase.save_error'), call.message.chat.id, call.message.message_id)
        else:
            error_msg = result.get('error', 'Unknown') if isinstance(result, dict) else str(result)
            _bot.edit_message_text(get_text(user_id, 'purchase.buy_error', error=error_msg),
                                   call.message.chat.id, call.message.message_id)

    except Exception as e:
        logger.error(f"Error in handle_buy_number: {e}", exc_info=True)
        _bot.answer_callback_query(call.id, get_text(call.from_user.id, 'errors.general_short'))


@router.callback('get_code_')
def handle_get_code(call):
    from telebot import types
    from compat.legacy_facade import (
        sms_check_status as compat_sms_check_status,
        order_update_status as compat_order_update_status,
        order_save_code as compat_order_save_code,
    )

    try:
        user_id = call.from_user.id
        order_id = call.data.split('_')[2]

        result = compat_sms_check_status(int(order_id))
        status = result.get('status', 'ERROR')

        if status == 'RECEIVED':
            code_text = result.get('code', '')
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'purchase.view_details'),
                          url=f"{BOT_CONFIG['website_url']}/number_details/{order_id}"))
            keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_main'), callback_data="back_to_main"))

            compat_order_update_status(int(order_id), 'RECEIVED')
            compat_order_save_code(int(order_id), code_text)

            _bot.edit_message_text(
                f"✅ {get_text(user_id, 'order.code_received', phone='', code=code_text, time='')}\n\n📱 کد: <b>{code_text}</b>",
                call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode='HTML'
            )
        elif status == 'WAITING':
            _bot.answer_callback_query(call.id, get_text(user_id, 'order.code_not_received'))
        elif status == 'CANCELLED':
            _bot.answer_callback_query(call.id, get_text(user_id, 'order.cancelled_simple', refund=''))
        else:
            _bot.answer_callback_query(call.id, get_text(user_id, 'order.code_not_received'))

    except Exception as e:
        logger.error(f"Error in get_code: {e}")
        _bot.answer_callback_query(call.id, get_text(call.from_user.id, 'errors.general'))


@router.callback('cancel_order_')
def handle_cancel_order(call):
    from telebot import types
    from compat.legacy_facade import (
        sms_cancel_number as compat_sms_cancel_number,
        order_cancel as compat_order_cancel,
        get_balance as compat_get_balance,
    )

    try:
        user_id = call.from_user.id
        order_id = int(call.data.split('_')[2])

        _bot.edit_message_text(get_text(user_id, 'order.cancelling'), call.message.chat.id, call.message.message_id)

        cancel_result = compat_sms_cancel_number(order_id)
        if cancel_result.get('success'):
            compat_order_cancel(order_id)
            balance = compat_get_balance(user_id)
            success_msg = get_text(user_id, 'order.cancelled', balance=balance, refund=0)
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_menu'), callback_data="buy_number"))
            _bot.edit_message_text(success_msg, call.message.chat.id, call.message.message_id, reply_markup=keyboard)
        else:
            _bot.edit_message_text(get_text(user_id, 'order.cancel_error'), call.message.chat.id, call.message.message_id)

    except Exception as e:
        logger.error(f"Error in cancel_order: {e}", exc_info=True)
        _bot.edit_message_text(get_text(call.from_user.id, 'order.cancel_error'),
                               call.message.chat.id, call.message.message_id)


@router.callback('my_orders')
def handle_my_orders(call):
    from telebot import types
    user_id = call.from_user.id
    orders_url = f"{BOT_CONFIG['webhook_url'].rstrip('/')}/orders/{user_id}"
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'order.view_orders_web'), url=orders_url))
    keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_menu'), callback_data="back_to_main"))
    _bot.edit_message_text(get_text(user_id, 'order.my_orders_title'), call.message.chat.id, call.message.message_id, reply_markup=keyboard)