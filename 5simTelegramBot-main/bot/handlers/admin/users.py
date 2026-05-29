"""
bot/handlers/admin/users.py — Admin User Management (Enterprise)
─────────────────────────────────────────────────
Uses UserRepository — no direct sqlite3.
"""

import logging
from bot.router import router
from i18n import get_text
from config import BOT_CONFIG
from compat.legacy_facade import get_balance as compat_get_balance
from telebot import types

logger = logging.getLogger(__name__)
_bot = None


def init(bot_instance):
    global _bot
    _bot = bot_instance


def _get_repo():
    from db.repositories.user_repository import UserRepository
    return UserRepository()


@router.callback('manage_users')
def handle_manage_users(call):
    user_id = call.from_user.id
    if user_id not in BOT_CONFIG['admin_ids']:
        _bot.answer_callback_query(call.id, get_text(user_id, 'errors.no_access_section'))
        return
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton(get_text(user_id, 'admin.users_list_title')[:20], callback_data="users_list"),
        types.InlineKeyboardButton(get_text(user_id, 'admin.user_search'), callback_data="search_user"),
        types.InlineKeyboardButton(get_text(user_id, 'admin.broadcast'), callback_data="broadcast_message"),
        types.InlineKeyboardButton(get_text(user_id, 'admin.group_discount'), callback_data="group_discount"))
    keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back'), callback_data="admin_panel"))
    _bot.edit_message_text(get_text(user_id, 'admin.users_section_title'), call.message.chat.id,
                           call.message.message_id, reply_markup=keyboard)


@router.callback('users_list')
def handle_users_list(call):
    user_id = call.from_user.id
    if user_id not in BOT_CONFIG['admin_ids']:
        _bot.answer_callback_query(call.id, get_text(user_id, 'errors.no_access_section'))
        return
    users = _get_repo().list_recent(10)
    if not users:
        text = get_text(user_id, 'admin.users_list_empty')
    else:
        text = get_text(user_id, 'admin.users_list_title')
        for u in users:
            uid = u['user_id'] if isinstance(u, dict) else u[0]
            bal = u['balance'] if isinstance(u, dict) else u[1]
            text += f"🆔 ID: {uid}\n💰 {get_text(user_id, 'common.toman')}: {bal:,}\n➖➖➖➖➖➖➖➖\n"
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton(get_text(user_id, 'user_menu.prev_page'), callback_data="users_prev_page"),
        types.InlineKeyboardButton(get_text(user_id, 'user_menu.next_page'), callback_data="users_next_page"))
    keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_users'), callback_data="manage_users"))
    _bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)


@router.callback('search_user')
def handle_search_user(call):
    user_id = call.from_user.id
    if user_id not in BOT_CONFIG['admin_ids']:
        return
    msg = _bot.edit_message_text(get_text(user_id, 'admin.search_user_prompt'), call.message.chat.id,
                                  call.message.message_id)
    _bot.register_next_step_handler(msg, process_user_search)


def process_user_search(message):
    user_id = message.from_user.id
    if user_id not in BOT_CONFIG['admin_ids']:
        return
    search_term = message.text.strip()
    if not search_term.isdigit():
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton(get_text(user_id, 'navigation.search_again'), callback_data="search_user"),
            types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_users'), callback_data="manage_users"))
        _bot.reply_to(message, get_text(user_id, 'admin.search_user_invalid'), reply_markup=keyboard)
        return
    target_id = int(search_term)
    user = _get_repo().find_by_id(target_id)
    if user:
        uid = user['user_id'] if isinstance(user, dict) else user[0]
        bal = user['balance'] if isinstance(user, dict) else user[1]
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            types.InlineKeyboardButton(get_text(user_id, 'admin.modify_balance'),
                                        callback_data=f"modify_balance_{uid}"),
            types.InlineKeyboardButton(get_text(user_id, 'admin.send_message'),
                                        callback_data=f"send_message_{uid}"))
        keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_users'),
                                                 callback_data="manage_users"))
        _bot.reply_to(message, get_text(user_id, 'admin.search_user_found', user_id=uid, balance=bal),
                      reply_markup=keyboard)
    else:
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton(get_text(user_id, 'navigation.search_again'), callback_data="search_user"),
            types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_users'), callback_data="manage_users"))
        _bot.reply_to(message, get_text(user_id, 'admin.search_user_not_found'), reply_markup=keyboard)


@router.callback('modify_balance_')
def handle_modify_balance(call):
    user_id = call.from_user.id
    if user_id not in BOT_CONFIG['admin_ids']:
        return
    target_id = call.data.split('_')[2]
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton(get_text(user_id, 'admin.add_balance_btn'),
                                    callback_data=f"add_balance_{target_id}"),
        types.InlineKeyboardButton(get_text(user_id, 'admin.reduce_balance_btn'),
                                    callback_data=f"reduce_balance_{target_id}"))
    keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_search'), callback_data="search_user"))
    _bot.edit_message_text(get_text(user_id, 'admin.select_balance_action'), call.message.chat.id,
                           call.message.message_id, reply_markup=keyboard)


@router.callback('add_balance_')
def handle_add_balance(call):
    parts = call.data.split('_')
    target_id = parts[2]
    user_id = call.from_user.id
    msg = _bot.edit_message_text(get_text(user_id, 'admin.enter_amount_prompt'), call.message.chat.id,
                                  call.message.message_id)
    _bot.register_next_step_handler(msg, process_balance_change, "add", target_id)


@router.callback('reduce_balance_')
def handle_reduce_balance(call):
    parts = call.data.split('_')
    target_id = parts[2]
    user_id = call.from_user.id
    msg = _bot.edit_message_text(get_text(user_id, 'admin.enter_amount_prompt'), call.message.chat.id,
                                  call.message.message_id)
    _bot.register_next_step_handler(msg, process_balance_change, "reduce", target_id)


def process_balance_change(message, action, target_id):
    admin_id = message.from_user.id
    from compat.legacy_facade import admin_add_balance, admin_deduct_balance
    try:
        amount = int(message.text.strip().replace(',', ''))
        if amount <= 0:
            raise ValueError
        if action == "add":
            new_balance = admin_add_balance(int(target_id), amount, admin_id)
        else:
            current = compat_get_balance(int(target_id))
            if current < amount:
                _bot.reply_to(message, get_text(admin_id, 'admin.insufficient_balance_admin'))
                return
            new_balance = admin_deduct_balance(int(target_id), amount, admin_id)
        if new_balance is None:
            _bot.reply_to(message, get_text(admin_id, 'errors.general_short'))
            return
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(get_text(admin_id, 'navigation.back_to_search'),
                                                 callback_data="search_user"))
        action_text = get_text(admin_id, 'admin.balance_added') if action == 'add' else get_text(admin_id,
                                                                                                   'admin.balance_reduced')
        _bot.reply_to(message,
                      get_text(admin_id, 'admin.balance_admin_confirm', action=action_text, balance=new_balance),
                      reply_markup=keyboard)
    except ValueError:
        _bot.reply_to(message, get_text(admin_id, 'admin.amount_must_be_positive'))
    except Exception as e:
        logger.error(f"Balance change error: {e}")
        _bot.reply_to(message, get_text(message.from_user.id, 'errors.general_short'))
