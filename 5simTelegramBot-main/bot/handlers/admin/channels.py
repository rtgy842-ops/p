"""
bot/handlers/admin/channels.py — Admin Channel Management
"""

import logging

from telebot import types

from admin_config import AdminConfig
from bot.router import router
from config import BOT_CONFIG
from i18n import get_text

logger = logging.getLogger(__name__)
_bot = None
_admin_config = AdminConfig()

def init(bot_instance):
    global _bot; _bot = bot_instance

@router.callback('manage_channels')
def handle_manage_channels(call):
    user_id = call.from_user.id
    if user_id not in BOT_CONFIG['admin_ids']: _bot.answer_callback_query(call.id, get_text(user_id, 'errors.no_access_section')); return
    channels = _admin_config.get_required_channels()
    text = get_text(user_id, 'channels.management_title')
    if channels and len(channels) > 0:
        text += get_text(user_id, 'channels.list_title')
        for i, channel in enumerate(channels, 1):
            try:
                chat_info = _bot.get_chat(f"@{channel[0]}")
                text += f"{i}. {chat_info.title}\n🆔 @{channel[0]}\n🔗 {channel[2]}\n➖➖➖➖➖➖➖➖\n"
            except Exception:
                text += f"{i}. @{channel[0]} ({get_text(user_id, 'channels.unreachable')})\n➖➖➖➖➖➖➖➖\n"
    else: text += get_text(user_id, 'channels.no_channels')
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'channels.add_channel'), callback_data="add_channel"), types.InlineKeyboardButton(get_text(user_id, 'channels.remove_channel'), callback_data="remove_channel"))
    keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'channels.check_status'), callback_data="check_channels_status"), types.InlineKeyboardButton(get_text(user_id, 'channels.lock_status'), callback_data="toggle_lock"))
    keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'channels.add_bot'), url="https://t.me/HajNumber_Bot"))
    keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_admin'), callback_data="admin_panel"))
    _bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, disable_web_page_preview=True)

@router.callback('add_channel')
def handle_add_channel(call):
    user_id = call.from_user.id
    msg = _bot.edit_message_text(get_text(user_id, 'channels.add_prompt'), call.message.chat.id, call.message.message_id)
    _bot.register_next_step_handler(msg, process_channel_username)

def process_channel_username(message):
    user_id = message.from_user.id
    if user_id not in BOT_CONFIG['admin_ids']: return
    username = message.text.strip()
    if not username.startswith('@'): _bot.reply_to(message, get_text(user_id, 'channels.invalid_username')); return
    username = username[1:]
    try:
        chat_info = _bot.get_chat(f"@{username}")
        bot_member = _bot.get_chat_member(f"@{username}", _bot.get_me().id)
        if bot_member.status not in ['administrator', 'creator']:
            keyboard = types.InlineKeyboardMarkup(row_width=1)
            keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'channels.add_bot'), url="https://t.me/HajNumber_Bot"), types.InlineKeyboardButton(get_text(user_id, 'navigation.retry'), callback_data="add_channel"), types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_channels'), callback_data="manage_channels"))
            _bot.reply_to(message, get_text(user_id, 'channels.bot_not_admin'), reply_markup=keyboard); return
        try: invite_link = _bot.export_chat_invite_link(f"@{username}")
        except Exception:
            invite_link = f"https://t.me/{username}"
        _admin_config.add_required_channel(username=username, display_name=chat_info.title, invite_link=invite_link)
        keyboard = types.InlineKeyboardMarkup(); keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_channels'), callback_data="manage_channels"))
        _bot.reply_to(message, get_text(user_id, 'channels.channel_added', name=chat_info.title, username=username, link=invite_link), reply_markup=keyboard)
    except Exception:
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.retry'), callback_data="add_channel"), types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_channels'), callback_data="manage_channels"))
        _bot.reply_to(message, get_text(user_id, 'errors.api_error'), reply_markup=keyboard)

@router.callback('remove_channel')
def handle_remove_channel(call):
    user_id = call.from_user.id
    channels = _admin_config.get_required_channels()
    if not channels: _bot.answer_callback_query(call.id, get_text(user_id, 'channels.no_channels_to_remove')); return
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    for channel in channels: keyboard.add(types.InlineKeyboardButton(f"❌ {channel[1]} (@{channel[0]})", callback_data=f"del_channel_{channel[0]}"))
    keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_channels'), callback_data="manage_channels"))
    _bot.edit_message_text(get_text(user_id, 'channels.remove_select'), call.message.chat.id, call.message.message_id, reply_markup=keyboard)

@router.callback('del_channel_')
def handle_delete_channel(call):
    username = call.data.split('_')[2]; _admin_config.remove_required_channel(username)
    _bot.answer_callback_query(call.id, get_text(call.from_user.id, 'channels.channel_removed'))
    handle_manage_channels(call)

@router.callback('check_channels_status')
def handle_check_channels_status(call):
    user_id = call.from_user.id
    channels = _admin_config.get_required_channels()
    if not channels: _bot.answer_callback_query(call.id, get_text(user_id, 'channels.no_channels')); return
    text = get_text(user_id, 'channels.status_title'); all_ok = True
    for channel in channels:
        try:
            bot_member = _bot.get_chat_member(f"@{channel[0]}", _bot.get_me().id); chat_info = _bot.get_chat(f"@{channel[0]}")
            if bot_member.status in ['administrator', 'creator']: text += f"✅ {chat_info.title}\n🆔 @{channel[0]}\n{get_text(user_id, 'channels.status_bot_admin')}\n"
            else: text += f"⚠️ {chat_info.title}\n🆔 @{channel[0]}\n{get_text(user_id, 'channels.status_bot_not_admin')}\n"; all_ok = False
        except Exception:
            text += f"❌ @{channel[0]}\n{get_text(user_id, 'channels.status_error')}\n"; all_ok = False
        text += "➖➖➖➖➖➖➖➖\n"
    text += f"\n{get_text(user_id, 'channels.all_ok') if all_ok else get_text(user_id, 'channels.some_issues')}"
    keyboard = types.InlineKeyboardMarkup(); keyboard.add(types.InlineKeyboardButton(get_text(user_id, 'navigation.back_to_channels'), callback_data="manage_channels"))
    _bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard)

@router.callback('toggle_lock')
def handle_toggle_lock(call):
    user_id = call.from_user.id
    current_status = _admin_config.get_lock_status(); new_status = not current_status
    _admin_config.set_lock_status(new_status)
    status_text = get_text(user_id, 'channels.lock_active') if new_status else get_text(user_id, 'channels.lock_inactive')
    _bot.answer_callback_query(call.id, get_text(user_id, 'channels.lock_toggled', status=status_text))
    handle_manage_channels(call)
