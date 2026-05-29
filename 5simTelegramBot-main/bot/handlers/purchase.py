"""
bot/handlers/purchase.py — Purchase + Service Selection Handlers
─────────────────────────────────────────────────
All handlers registered via Router.
"""

import logging
from bot.router import router
from i18n import get_text
from config import BOT_CONFIG

logger = logging.getLogger(__name__)
_bot = None

def init(bot_instance):
    global _bot; _bot = bot_instance


# ── buy_number_ (with parameters) MUST come before buy_number ──
@router.callback('buy_number_')
def handle_buy_number_with_params(call):
    from telebot import types
    from compat.legacy_facade import get_balance, deduct_balance, sms_buy_number, order_save
    from data.service_countries import get_countries_for_service, get_country_name as _get_country_name
    from operator_config import OperatorConfig

    try:
        user_id = call.from_user.id
        balance = get_balance(user_id)
        parts = call.data.split('_')
        service = parts[2]; country = parts[3]; operator = parts[4]

        country_name = _get_country_name(service, country)
        if not country_name:
            country_name = get_text(user_id, f'countries.{country}')

        from compat.legacy_facade import sms_get_prices
        price_data = sms_get_prices(service)
        price_toman = 50000
        if price_data:
            from db.repositories.settings_repository import SettingsRepository
            repo = SettingsRepository()
            usd_rate = float(repo.get('usd_rate') or 0)
            profit = float(repo.get('profit_percentage') or 30)
            if country in price_data and service in price_data[country]:
                ops = price_data[country][service]
                if operator in ops and ops[operator]['count'] > 0:
                    price_toman = round(ops[operator]['cost'] * usd_rate * (1 + profit/100))

        if balance < price_toman:
            deficit = price_toman - balance
            keyboard = types.InlineKeyboardMarkup(row_width=1)
            keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'main_menu.add_funds'), callback_data="add_funds"))
            keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_services'), callback_data="back_to_services"))
            _bot.edit_message_text(get_text(user_id, 'purchase.insufficient_balance', balance=balance, price=price_toman, deficit=deficit),
                                   call.message.chat.id, call.message.message_id, reply_markup=keyboard)
            return

        _bot.edit_message_text(get_text(user_id, 'purchase.buying', service=service, country=country_name),
                               call.message.chat.id, call.message.message_id)

        result = sms_buy_number(country, operator, service)
        if result and isinstance(result, dict) and result.get('success') and 'data' in result:
            order_data = result['data']
            deduct_balance(user_id, price_toman, f'Buy {service} in {country}')

            order_info = {
                'user_id': user_id, 'activation_id': order_data['order_id'],
                'service': service, 'country': country, 'operator': operator,
                'phone': order_data['phone'], 'price': price_toman,
                'status': order_data.get('status', 'PENDING').lower()
            }
            order_id = order_save(order_info)

            if order_id:
                details_url = f"{BOT_CONFIG['website_url']}/number_details/{order_id}"
                keyboard = types.InlineKeyboardMarkup(row_width=1)
                keyboard.add(
                    types.InlineKeyboardButton(get_text(user_id, 'purchase.get_code'), callback_data=f"get_code_{order_data['order_id']}"),
                    types.InlineKeyboardButton(get_text(user_id, 'purchase.cancel_order'), callback_data=f"cancel_order_{order_data['order_id']}"),
                    types.InlineKeyboardButton(get_text(user_id, 'purchase.view_details_web'), url=details_url),
                    types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_services'), callback_data="back_to_services"))
                _bot.edit_message_text(
                    get_text(user_id, 'purchase.success', service=service, country=country_name,
                             phone=order_data['phone'], operator=operator, price=price_toman),
                    call.message.chat.id, call.message.message_id, reply_markup=keyboard)
            else:
                _bot.edit_message_text(get_text(user_id, 'purchase.save_error'),
                                       call.message.chat.id, call.message.message_id)
        else:
            error_msg = (result or {}).get('error', 'Unknown error') if isinstance(result, dict) else 'Unknown error'
            _bot.edit_message_text(get_text(user_id, 'purchase.buy_error', error=error_msg),
                                   call.message.chat.id, call.message.message_id)
    except Exception as e:
        logger.error(f"Error in buy_number_: {e}", exc_info=True)
        _bot.answer_callback_query(call.id, get_text(call.from_user.id, 'errors.general_short'))


# ── buy_number (main menu entry) ──────────────────────────
@router.callback('buy_number')
def handle_buy_number_entry(call):
    from bot.keyboards.main_keyboard import services_keyboard
    _bot.edit_message_text(
        get_text(call.from_user.id, 'services.select'),
        call.message.chat.id, call.message.message_id,
        reply_markup=services_keyboard(call.from_user.id))


# ── check_balance ─────────────────────────────────────────
@router.callback('check_balance')
def handle_check_balance(call):
    from telebot import types
    from compat.legacy_facade import get_balance
    user_id = call.from_user.id
    balance = get_balance(user_id)
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        types.InlineKeyboardButton(get_text(user_id, 'main_menu.add_funds'), callback_data="add_funds"),
        types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_main'), callback_data="back_to_main"))
    _bot.edit_message_text(get_text(user_id, 'wallet.title', balance=balance),
                           call.message.chat.id, call.message.message_id,
                           reply_markup=keyboard, parse_mode='Markdown')


# ── my_orders ─────────────────────────────────────────────
@router.callback('my_orders')
def handle_my_orders(call):
    from telebot import types
    user_id = call.from_user.id
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(
        get_text(user_id, 'order.view_orders_web'),
        url=f"{BOT_CONFIG['website_url']}/orders/{user_id}"))
    keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_main'), callback_data="back_to_main"))
    _bot.edit_message_text(get_text(user_id, 'order.my_orders_title'),
                           call.message.chat.id, call.message.message_id, reply_markup=keyboard)


# ── help ──────────────────────────────────────────────────
@router.callback('help')
def handle_help(call):
    from telebot import types
    user_id = call.from_user.id
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton(get_text(user_id, 'help.buy_number'), callback_data="help_buy_number"),
        types.InlineKeyboardButton(get_text(user_id, 'help.charge'), callback_data="help_charge"),
        types.InlineKeyboardButton(get_text(user_id, 'help.get_code'), callback_data="help_get_code"),
        types.InlineKeyboardButton(get_text(user_id, 'help.payment_methods'), callback_data="help_payment"),
        types.InlineKeyboardButton(get_text(user_id, 'help.delivery_time'), callback_data="help_delivery"),
        types.InlineKeyboardButton(get_text(user_id, 'help.cancel_order'), callback_data="help_cancel"),
        types.InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="back_to_main"))
    _bot.edit_message_text(get_text(user_id, 'help.title'),
                           call.message.chat.id, call.message.message_id, reply_markup=keyboard)

# ── help sub-menu callbacks ───────────────────────────────
for _cb in ['help_buy_number', 'help_charge', 'help_get_code', 'help_payment', 'help_delivery', 'help_cancel']:
    _answer_map = {
        'help_buy_number': 'help.buy_number_answer', 'help_charge': 'help.charge_answer',
        'help_get_code': 'help.get_code_answer', 'help_payment': 'help.payment_methods_answer',
        'help_delivery': 'help.delivery_time_answer', 'help_cancel': 'help.cancel_order_answer',
    }
    def _make_help_handler(cb):
        @router.callback(cb)
        def _handler(call, key=_answer_map[cb]):
            from telebot import types
            uid = call.from_user.id
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton(get_text(uid, 'navigation.back_to_help'), callback_data="help"))
            _bot.edit_message_text(get_text(uid, key), call.message.chat.id, call.message.message_id, reply_markup=kb)
        return _handler
    _make_help_handler(_cb)


# ── Navigation + Operator ─────────────────────────────────
@router.callback('back_to_services')
def back_to_services(call):
    from bot.keyboards.main_keyboard import services_keyboard
    _bot.edit_message_text(get_text(call.from_user.id, 'services.select'),
                           call.message.chat.id, call.message.message_id,
                           reply_markup=services_keyboard(call.from_user.id))

@router.callback('no_operator')
def handle_no_operator(call):
    _bot.answer_callback_query(call.id, get_text(call.from_user.id, 'services.no_operator'))


# ── get_code_ ─────────────────────────────────────────────
@router.callback('get_code_')
def handle_get_code(call):
    from compat.legacy_facade import sms_check_status, order_update_status, order_save_code
    try:
        user_id = call.from_user.id
        order_id = call.data.split('_')[2]
        check = sms_check_status(int(order_id))
        status = check.get('status', 'ERROR')
        if status == 'RECEIVED':
            code_text = check.get('code', '')
            order_update_status(int(order_id), 'RECEIVED')
            order_save_code(int(order_id), code_text)
            from telebot import types
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton('🌐 ' + get_text(user_id, 'purchase.view_details'),
                                               url=f"{BOT_CONFIG['website_url']}/number_details/{order_id}"))
            kb.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_main'), callback_data="back_to_main"))
            _bot.edit_message_text(f"✅ Code: <b>{code_text}</b>", call.message.chat.id,
                                   call.message.message_id, reply_markup=kb, parse_mode='HTML')
        elif status == 'WAITING':
            _bot.answer_callback_query(call.id, get_text(user_id, 'order.code_not_received'))
        else:
            _bot.answer_callback_query(call.id, '⏳ ' + status)
    except Exception as e:
        logger.error(f"Error in get_code: {e}")
        _bot.answer_callback_query(call.id, get_text(call.from_user.id, 'errors.general_short'))


# ── cancel_order_ ─────────────────────────────────────────
@router.callback('cancel_order_')
def handle_cancel_order(call):
    from compat.legacy_facade import sms_cancel_number, order_cancel, get_balance
    from telebot import types
    try:
        user_id = call.from_user.id
        order_id = int(call.data.split('_')[2])
        _bot.edit_message_text(get_text(user_id, 'order.cancelling'), call.message.chat.id, call.message.message_id)
        cancel_result = sms_cancel_number(order_id)
        if cancel_result.get('success'):
            oc = order_cancel(order_id)
            if oc.get('success'):
                bal = get_balance(user_id)
                kb = types.InlineKeyboardMarkup()
                kb.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_menu'), callback_data="buy_number"))
                _bot.edit_message_text(get_text(user_id, 'order.cancelled_simple', refund='OK') + f"\n💰 Balance: {bal:,} T",
                                       call.message.chat.id, call.message.message_id, reply_markup=kb)
            else:
                _bot.edit_message_text(get_text(user_id, 'order.cancelled_warning', warning=oc.get('error', '')),
                                       call.message.chat.id, call.message.message_id)
        else:
            _bot.edit_message_text(get_text(user_id, 'order.cancel_error'),
                                   call.message.chat.id, call.message.message_id)
    except Exception as e:
        logger.error(f"Error in cancel_order: {e}")
        _bot.edit_message_text(get_text(call.from_user.id, 'errors.general'),
                               call.message.chat.id, call.message.message_id)