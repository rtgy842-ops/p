"""
bot/handlers/admin_bot.py — Standalone Admin Bot Handlers (Complete — Arabic)
─────────────────────────────────────────────────
COMPLETELY SEPARATE from Customer Bot.
Requires its OWN Telegram Bot Token (ADMIN_BOT_TOKEN env var).
All operations pass through AdminService + RBAC + Audit.
Security: If ADMIN_BOT_TOKEN is not set, admin bot does NOT start.
"""

import logging

from bot.router import router

logger = logging.getLogger(__name__)
_bot = None


def init(bot_instance):
    global _bot
    _bot = bot_instance
    logger.info("Admin Bot handlers initialized")


# ═══════════════════════════════════════════════════════════════
# /start — Admin Bot Entry
# ═══════════════════════════════════════════════════════════════

@router.command('start')
def admin_start(message):
    from telebot import types
    uid = message.from_user.id
    from services.rbac_service import Permission, rbac
    if not rbac.has_permission(uid, Permission.SETTINGS_VIEW):
        _bot.reply_to(message, "⛔ ليس لديك صلاحية الوصول للوحة الإدارة.")
        return
    role = rbac.get_role(uid)
    text = (
        f"🛡️ **بوت الإدارة — NumGenius Enterprise**\n\n"
        f"الصلاحية: `{role.value.upper()}`\n"
        f"مرحباً بك في لوحة التحكم.\n\n"
        f"استخدم الأزرار أدناه لإدارة المنصة."
    )
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("📊 لوحة التحكم", callback_data="admin:dashboard"),
        types.InlineKeyboardButton("👥 المستخدمين", callback_data="admin:users"),
        types.InlineKeyboardButton("📦 الطلبات", callback_data="admin:orders"),
        types.InlineKeyboardButton("💳 المدفوعات", callback_data="admin:payments"),
        types.InlineKeyboardButton("📊 الإحصائيات", callback_data="admin:stats"),
        types.InlineKeyboardButton("⚙️ الإعدادات", callback_data="admin:settings"),
        types.InlineKeyboardButton("🔍 التدقيق", callback_data="admin:audit"),
        types.InlineKeyboardButton("🏪 الكتالوج", callback_data="admin:catalog"),
        types.InlineKeyboardButton("🔌 المزودين", callback_data="admin:providers"),
        types.InlineKeyboardButton("💱 العملات", callback_data="admin:currencies"),
        types.InlineKeyboardButton("🎫 الاشتراكات", callback_data="admin:subscriptions"),
        types.InlineKeyboardButton("🔗 الإحالات", callback_data="admin:referrals"),
        types.InlineKeyboardButton("📢 broadcast", callback_data="admin:broadcast"),
        types.InlineKeyboardButton("🖥️ لوحة الويب", callback_data="admin:web_panel"),
    )
    _bot.reply_to(message, text, reply_markup=keyboard, parse_mode='Markdown')


# ═══════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════

@router.callback('admin:dashboard')
def admin_dashboard(call):
    from telebot import types

    from services.admin_service import AdminService
    from services.analytics_service import analytics
    admin = AdminService()
    stats = admin.get_stats()
    a = analytics.get_dashboard()
    orders = a.get('orders', {})
    text = (
        f"📊 **لوحة التحكم**\n\n"
        f"👥 المستخدمين: **{stats['total_users']}**\n"
        f"💵 اليوم: **{stats['today_revenue']:,}** T\n"
        f"📦 الطلبات النشطة: **{stats['active_orders']}**\n"
        f"💱 USD: **{stats['usd_rate']:,}** T\n"
        f"📈 الربح: **{stats['profit_percentage']}%**\n"
        f"💰 ربح اليوم: **{stats['today_profit']:,}** T\n\n"
        f"📅 إيرادات الأسبوع: **{stats['week_revenue']:,}** T\n"
        f"📅 إيرادات الشهر: **{stats['month_revenue']:,}** T\n"
        f"✅ نسبة النجاح: {orders.get('success_rate', 0)}%"
    )
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("👥 المستخدمين", callback_data="admin:users"),
        types.InlineKeyboardButton("📦 الطلبات", callback_data="admin:orders"),
        types.InlineKeyboardButton("💳 المدفوعات", callback_data="admin:payments"),
        types.InlineKeyboardButton("📊 الإحصائيات", callback_data="admin:stats"),
        types.InlineKeyboardButton("⚙️ الإعدادات", callback_data="admin:settings"),
        types.InlineKeyboardButton("🔍 التدقيق", callback_data="admin:audit"),
        types.InlineKeyboardButton("🏪 الكتالوج", callback_data="admin:catalog"),
        types.InlineKeyboardButton("🔌 المزودين", callback_data="admin:providers"),
        types.InlineKeyboardButton("💱 العملات", callback_data="admin:currencies"),
        types.InlineKeyboardButton("🎫 الاشتراكات", callback_data="admin:subscriptions"),
        types.InlineKeyboardButton("🔗 الإحالات", callback_data="admin:referrals"),
        types.InlineKeyboardButton("📢 broadcast", callback_data="admin:broadcast"),
        types.InlineKeyboardButton("🖥️ لوحة الويب", callback_data="admin:web_panel"),
    )
    _bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                           reply_markup=keyboard, parse_mode='Markdown')


# ═══════════════════════════════════════════════════════════════
# USERS
# ═══════════════════════════════════════════════════════════════

@router.callback('admin:users')
def admin_users(call):
    from telebot import types

    from services.subscription_service import subscriptions
    from services.user_service import UserService
    user_svc = UserService()
    recent = user_svc.list_recent(20)
    total = user_svc.get_stats()['total_users']
    lines = [f"👥 **إدارة المستخدمين** ({total} إجمالي)\n"]
    for u in recent[:12]:
        uid = u.user_id if hasattr(u, 'user_id') else u[0]
        bal = u.balance if hasattr(u, 'balance') else (u[1] if len(u) > 1 else 0)
        tier = subscriptions.get_tier(uid)
        lines.append(f"• `{uid}` — {bal:,} T [{tier.value}]")
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("🔍 بحث عن مستخدم", callback_data="admin:user_search"),
        types.InlineKeyboardButton("➕ إضافة رصيد", callback_data="admin:user_balance"),
        types.InlineKeyboardButton("➖ خصم رصيد", callback_data="admin:user_deduct"),
        types.InlineKeyboardButton("🚫 حظر/إلغاء", callback_data="admin:user_ban"),
        types.InlineKeyboardButton("🎫 تعيين اشتراك", callback_data="admin:subscriptions"),
        types.InlineKeyboardButton("◀️ لوحة التحكم", callback_data="admin:dashboard"),
    )
    _bot.edit_message_text('\n'.join(lines), call.message.chat.id,
                           call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')


@router.callback('admin:user_search')
def admin_user_search_prompt(call):
    msg = _bot.edit_message_text(
        "🔍 أرسل معرف المستخدم للبحث:",
        call.message.chat.id, call.message.message_id
    )
    _bot.register_next_step_handler(msg, _process_user_search)


def _process_user_search(message):
    from telebot import types

    from services.user_service import UserService
    try:
        uid = int(message.text.strip())
        user_svc = UserService()
        user = user_svc.get_user(uid)
        if user:
            text = (
                f"👤 **تم العثور على المستخدم**\n\n"
                f"المعرف: `{user.user_id}`\n"
                f"الرصيد: {user.balance:,} T\n"
                f"اللغة: {user.language}\n"
                f"الحظر: {'🚫 محظور' if user.is_blocked else '✅ نشط'}\n"
                f"تاريخ الانضمام: {user.join_date}"
            )
            keyboard = types.InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                types.InlineKeyboardButton("➕ إضافة رصيد", callback_data=f"admin:balance_add_{uid}"),
                types.InlineKeyboardButton("➖ خصم رصيد", callback_data=f"admin:balance_deduct_{uid}"),
                types.InlineKeyboardButton("🚫 تبديل الحظر", callback_data=f"admin:toggle_ban_{uid}"),
                types.InlineKeyboardButton("◀️ رجوع", callback_data="admin:users"),
            )
            _bot.reply_to(message, text, reply_markup=keyboard, parse_mode='Markdown')
        else:
            _bot.reply_to(message, "❌ المستخدم غير موجود.")
    except ValueError:
        _bot.reply_to(message, "❌ معرف مستخدم غير صالح. أرسل رقماً.")


@router.callback('admin:user_balance')
def admin_user_balance_prompt(call):
    msg = _bot.edit_message_text(
        "➕ أرسل معرف المستخدم والمبلغ (الصيغة: `ID AMOUNT`):\nمثال: `123456789 50000`",
        call.message.chat.id, call.message.message_id
    )
    _bot.register_next_step_handler(msg, _process_add_balance)


MAX_BALANCE_CHANGE = 100_000_000  # 100M Toman cap for admin balance operations

def _process_add_balance(message):
    from services.admin_service import AdminService
    parts = message.text.strip().split()
    if len(parts) != 2:
        _bot.reply_to(message, "❌ الصيغة: ID AMOUNT\nمثال: 123456789 50000")
        return
    try:
        uid = int(parts[0])
        amount = int(parts[1])
        if amount <= 0 or amount > MAX_BALANCE_CHANGE:
            _bot.reply_to(message, f"❌ المبلغ يجب أن يكون بين 1-{MAX_BALANCE_CHANGE:,} تومان")
            return
        admin = AdminService()
        result = admin.add_balance(uid, amount, message.from_user.id)
        if result is not None:
            _bot.reply_to(message, f"✅ تمت إضافة {amount:,} T للمستخدم {uid}\nالرصيد الجديد: {result:,} T")
        else:
            _bot.reply_to(message, "❌ فشلت إضافة الرصيد.")
    except ValueError:
        _bot.reply_to(message, "❌ أرقام غير صالحة.")


@router.callback('admin:user_deduct')
def admin_user_deduct_prompt(call):
    msg = _bot.edit_message_text(
        "➖ أرسل معرف المستخدم والمبلغ (الصيغة: `ID AMOUNT`):",
        call.message.chat.id, call.message.message_id
    )
    _bot.register_next_step_handler(msg, _process_deduct_balance)


def _process_deduct_balance(message):
    from services.admin_service import AdminService
    parts = message.text.strip().split()
    if len(parts) != 2:
        _bot.reply_to(message, "❌ الصيغة: ID AMOUNT")
        return
    try:
        uid = int(parts[0])
        amount = int(parts[1])
        if amount <= 0 or amount > MAX_BALANCE_CHANGE:
            _bot.reply_to(message, f"❌ المبلغ يجب أن يكون بين 1-{MAX_BALANCE_CHANGE:,} تومان")
            return
        admin = AdminService()
        result = admin.reduce_balance(uid, amount, message.from_user.id)
        if result is not None:
            _bot.reply_to(message, f"✅ تم خصم {amount:,} T من المستخدم {uid}\nالرصيد الجديد: {result:,} T")
        else:
            _bot.reply_to(message, "❌ فشل الخصم (رصيد غير كاف؟).")
    except ValueError:
        _bot.reply_to(message, "❌ أرقام غير صالحة.")


@router.callback('admin:user_ban')
def admin_user_ban_prompt(call):
    msg = _bot.edit_message_text(
        "🚫 أرسل معرف المستخدم لتبديل الحظر:",
        call.message.chat.id, call.message.message_id
    )
    _bot.register_next_step_handler(msg, _process_toggle_ban)


def _process_toggle_ban(message):
    from services.admin_service import AdminService
    from services.user_service import UserService
    try:
        uid = int(message.text.strip())
        user_svc = UserService()
        user = user_svc.get_user(uid)
        if not user:
            _bot.reply_to(message, "❌ المستخدم غير موجود.")
            return
        admin = AdminService()
        new_status = not user.is_blocked
        admin.set_blocked(uid, new_status, message.from_user.id)
        status_text = "🚫 محظور" if new_status else "✅ نشط"
        _bot.reply_to(message, f"✅ المستخدم {uid} الآن: {status_text}")
    except ValueError:
        _bot.reply_to(message, "❌ معرف مستخدم غير صالح.")


# ═══════════════════════════════════════════════════════════════
# ORDERS
# ═══════════════════════════════════════════════════════════════

@router.callback('admin:orders')
def admin_orders(call):
    from telebot import types

    from db.context import db_context
    with db_context('default', transactional=False) as db:
        rows = db.fetchall(
            "SELECT id, user_id, service, country, phone, price, status, created_at "
            "FROM orders ORDER BY created_at DESC LIMIT 20"
        )
    lines = ["📦 **أحدث الطلبات**\n"]
    for r in rows:
        lines.append(f"• #{r[0]} | {r[2]}/{r[3]} | {r[6]} | {r[4]}T")
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("📊 إحصائيات الطلبات", callback_data="admin:stats"),
        types.InlineKeyboardButton("◀️ لوحة التحكم", callback_data="admin:dashboard"),
    )
    _bot.edit_message_text('\n'.join(lines), call.message.chat.id,
                           call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')


# ═══════════════════════════════════════════════════════════════
# PAYMENTS
# ═══════════════════════════════════════════════════════════════

@router.callback('admin:payments')
def admin_payments(call):
    from telebot import types

    from db.context import db_context
    with db_context('default', transactional=False) as db:
        rows = db.fetchall(
            "SELECT payment_id, user_id, amount, status, created_at "
            "FROM card_payments ORDER BY created_at DESC LIMIT 20"
        )
    lines = ["💳 **المدفوعات البطاقية**\n"]
    for r in rows:
        status = r[3]
        icon = '✅' if status == 'approved' else ('❌' if status == 'rejected' else '⏳')
        lines.append(f"{icon} {r[0][:10]}... | {r[1]} | {r[2]}T | {status}")
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("◀️ لوحة التحكم", callback_data="admin:dashboard"))
    _bot.edit_message_text('\n'.join(lines), call.message.chat.id,
                           call.message.message_id, reply_markup=keyboard)


# ═══════════════════════════════════════════════════════════════
# STATS
# ═══════════════════════════════════════════════════════════════

@router.callback('admin:stats')
def admin_stats(call):
    from telebot import types

    from services.analytics_service import analytics
    a = analytics.get_dashboard()
    revenue = a.get('revenue', {})
    orders = a.get('orders', {})
    users = a.get('users', {})
    text = (
        f"📊 **التحليلات**\n\n"
        f"👥 المستخدمين: {users.get('total_users', 0)} ({users.get('new_this_week', 0)} جديد/أسبوع)\n"
        f"👤 نشط (7 أيام): {a.get('active_users_7d', 0)}\n\n"
        f"📦 الطلبات: {orders.get('total', 0)} إجمالي\n"
        f"✅ نسبة النجاح: {orders.get('success_rate', 0)}%\n"
        f"❌ نسبة الإلغاء: {orders.get('cancel_rate', 0)}%\n\n"
        f"💵 الإيرادات: {revenue.get('today', {}).get('revenue', 0):,} T (اليوم)\n"
        f"📅 الأسبوع: {revenue.get('week', {}).get('revenue', 0):,} T\n"
        f"📅 الشهر: {revenue.get('month', {}).get('revenue', 0):,} T"
    )
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("◀️ لوحة التحكم", callback_data="admin:dashboard"))
    _bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                           reply_markup=keyboard, parse_mode='Markdown')


# ═══════════════════════════════════════════════════════════════
# SETTINGS
# ═══════════════════════════════════════════════════════════════

@router.callback('admin:settings')
def admin_settings(call):
    from telebot import types

    from services.admin_service import AdminService
    admin = AdminService()
    usd_rate = admin.get_usd_rate()
    profit = admin.get_profit_percentage()
    lock = admin.get_lock_status()
    channels = admin.get_required_channels()
    text = (
        f"⚙️ **الإعدادات**\n\n"
        f"💱 سعر الدولار: **{usd_rate:,}** T\n"
        f"📈 نسبة الربح: **{profit}%**\n"
        f"🔒 قفل القنوات: **{'ON' if lock else 'OFF'}**\n"
        f"📢 القنوات الإلزامية: **{len(channels)}**\n\n"
        f"_اضغط أدناه للتعديل:_"
    )
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("💱 تعيين سعر الدولار", callback_data="admin:set_usd"),
        types.InlineKeyboardButton("📈 تعيين الربح %", callback_data="admin:set_profit"),
        types.InlineKeyboardButton("🔒 تبديل القفل", callback_data="admin:toggle_lock"),
        types.InlineKeyboardButton("📢 القنوات", callback_data="admin:channels"),
        types.InlineKeyboardButton("💳 معلومات البطاقة", callback_data="admin:card_info"),
        types.InlineKeyboardButton("◀️ لوحة التحكم", callback_data="admin:dashboard"),
    )
    _bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                           reply_markup=keyboard, parse_mode='Markdown')


@router.callback('admin:set_usd')
def admin_set_usd_prompt(call):
    msg = _bot.edit_message_text("💱 أرسل سعر الدولار الجديد للتومان:", call.message.chat.id, call.message.message_id)
    _bot.register_next_step_handler(msg, _process_set_usd)


def _process_set_usd(message):
    from services.admin_service import AdminService
    try:
        rate = float(message.text.strip())
        admin = AdminService()
        admin.set_usd_rate(rate, message.from_user.id)
        _bot.reply_to(message, f"✅ تم تحديث سعر الدولار إلى {rate:,} تومان")
    except ValueError:
        _bot.reply_to(message, "❌ رقم غير صالح.")


@router.callback('admin:set_profit')
def admin_set_profit_prompt(call):
    msg = _bot.edit_message_text("📈 أرسل نسبة الربح الجديدة (0-1000):", call.message.chat.id, call.message.message_id)
    _bot.register_next_step_handler(msg, _process_set_profit)


def _process_set_profit(message):
    from services.admin_service import AdminService
    try:
        pct = float(message.text.strip())
        if pct < 0 or pct > 1000:
            _bot.reply_to(message, "❌ بين 0 و 1000")
            return
        admin = AdminService()
        admin.set_profit_percentage(pct, message.from_user.id)
        _bot.reply_to(message, f"✅ تم تعيين الربح إلى {pct}%")
    except ValueError:
        _bot.reply_to(message, "❌ رقم غير صالح.")


@router.callback('admin:toggle_lock')
def admin_toggle_lock(call):
    from services.admin_service import AdminService
    admin = AdminService()
    current = admin.get_lock_status()
    admin.set_lock_status(not current, call.from_user.id)
    _bot.edit_message_text(
        f"🔒 قفل القنوات الآن: **{'ON' if not current else 'OFF'}**",
        call.message.chat.id, call.message.message_id, parse_mode='Markdown'
    )


# ═══════════════════════════════════════════════════════════════
# PROVIDERS
# ═══════════════════════════════════════════════════════════════

@router.callback('admin:providers')
def admin_providers(call):
    from telebot import types

    from services.provider_registry import provider_registry
    health = provider_registry.get_all_health()
    lines = ["🔌 **حالة المزودين**\n"]
    for h in health:
        icon_map = {'healthy': '✅', 'unknown': '⚠️', 'error': '❌', 'unhealthy': '❌'}
        icon = icon_map.get(h['status'], '❓')
        lines.append(f"{icon} **{h['display_name']}** — {h['status']}")
        if h.get('errors'):
            lines.append(f"   أخطاء: {h['errors']}")
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("🔄 مزامنة الكل", callback_data="admin:sync_providers"),
        types.InlineKeyboardButton("💚 فحص الصحة", callback_data="admin:health_check"),
        types.InlineKeyboardButton("◀️ لوحة التحكم", callback_data="admin:dashboard"),
    )
    _bot.edit_message_text('\n'.join(lines), call.message.chat.id,
                           call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')


@router.callback('admin:sync_providers')
def admin_sync_providers(call):
    from services.provider_sync import provider_sync
    _bot.answer_callback_query(call.id, "🔄 جاري مزامنة جميع المزودين...")
    results = provider_sync.sync_all()
    status = '\n'.join(
        f"• {k}: {'✅ ' + str(v.get('countries',0)) + ' دولة, ' + str(v.get('prices',0)) + ' سعر' if v.get('success') else '❌ ' + str(v.get('error',''))}"
        for k, v in results.items()
    )
    _bot.edit_message_text(f"🔄 **نتائج المزامنة:**\n\n{status}", call.message.chat.id,
                           call.message.message_id, parse_mode='Markdown')


@router.callback('admin:health_check')
def admin_health_check(call):
    from services.provider_registry import provider_registry
    results = provider_registry.health_check_all()
    status = '\n'.join(f"• {k}: {'✅ سليم' if v else '❌ معطل'}" for k, v in results.items())
    _bot.edit_message_text(f"💚 **فحص الصحة:**\n\n{status}", call.message.chat.id,
                           call.message.message_id, parse_mode='Markdown')


# ═══════════════════════════════════════════════════════════════
# AUDIT
# ═══════════════════════════════════════════════════════════════

@router.callback('admin:audit')
def admin_audit(call):
    from telebot import types

    from services.admin_service import AdminService
    admin = AdminService()
    entries = admin.get_audit_log(20)
    lines = ["🔍 **سجل التدقيق**\n"]
    for e in entries[:15]:
        action = e.get('action', '?')[:30]
        target = e.get('target', '?')[:20]
        ts = e.get('created_at', '?')[:19]
        lines.append(f"• `{ts}` | {action} | {target}")
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("◀️ لوحة التحكم", callback_data="admin:dashboard"))
    _bot.edit_message_text('\n'.join(lines), call.message.chat.id,
                           call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')


# ═══════════════════════════════════════════════════════════════
# BROADCAST
# ═══════════════════════════════════════════════════════════════

@router.callback('admin:broadcast')
def admin_broadcast_prompt(call):
    from services.user_service import UserService
    user_svc = UserService()
    total = user_svc.get_stats()['total_users']
    msg = _bot.edit_message_text(
        f"📢 أرسل الرسالة لإرسالها إلى **{total}** مستخدم:",
        call.message.chat.id, call.message.message_id, parse_mode='Markdown'
    )
    _bot.register_next_step_handler(msg, _process_broadcast)


def _process_broadcast(message):
    text = message.text
    from services.user_service import UserService
    user_svc = UserService()
    all_ids = user_svc.get_all_ids()
    _bot.reply_to(message, f"📢 جاري الإرسال إلى {len(all_ids)} مستخدم...")
    sent = 0
    failed = 0
    for uid in all_ids:
        try:
            uid_int = uid if isinstance(uid, int) else (uid[0] if isinstance(uid, (tuple, list)) else int(uid))
            _bot.send_message(uid_int, text)
            sent += 1
        except Exception:
            failed += 1
    _bot.send_message(message.chat.id, f"📢 **اكتمل الإرسال!**\n\n✅ تم الإرسال: {sent}\n❌ فشل: {failed}",
                       parse_mode='Markdown')


# ═══════════════════════════════════════════════════════════════
# CATALOG (Phase 4 — Full CRUD)
# ═══════════════════════════════════════════════════════════════

@router.callback('admin:catalog')
def admin_catalog(call):
    from telebot import types

    from services.catalog_manager import catalog as cat
    stats = cat.get_stats()
    countries = cat.get_active_countries()
    lines = [
        "🏪 **إدارة الكتالوج**\n",
        f"🌍 الدول النشطة: **{len(countries)}**",
        f"📡 الخدمات النشطة: **{stats['active_services']}**",
        f"💲 قواعد الأسعار: **{stats['active_prices']}**",
        f"🔌 المزودين النشطين: **{stats.get('active_providers', 0)}**\n",
        "**الدول النشطة:**"
    ]
    for c in countries[:15]:
        lines.append(f"✅ `{c['code']}` — {c['name']} (الترتيب: {c['order']})")
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("🌍 تفعيل/تعطيل دولة", callback_data="admin:cat_toggle_country"),
        types.InlineKeyboardButton("📡 تفعيل/تعطيل خدمة", callback_data="admin:cat_toggle_service"),
        types.InlineKeyboardButton("💲 عرض الأسعار", callback_data="admin:cat_prices"),
        types.InlineKeyboardButton("📡 كل الخدمات", callback_data="admin:cat_services"),
        types.InlineKeyboardButton("◀️ لوحة التحكم", callback_data="admin:dashboard"),
    )
    _bot.edit_message_text('\n'.join(lines), call.message.chat.id,
                           call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')


@router.callback('admin:cat_toggle_country')
def admin_cat_toggle_country_prompt(call):
    msg = _bot.edit_message_text(
        "🌍 أرسل رمز الدولة للتفعيل/التعطيل:\nمثال: `cyprus`",
        call.message.chat.id, call.message.message_id, parse_mode='Markdown'
    )
    _bot.register_next_step_handler(msg, _process_toggle_country)


def _process_toggle_country(message):
    from services.catalog_manager import catalog as cat
    code = message.text.strip().lower()
    countries = cat.get_all_countries()
    matched = [c for c in countries if c['code'] == code]
    if not matched:
        _bot.reply_to(message, f"❌ الدولة '{code}' غير موجودة في الكتالوج.")
        return
    current = matched[0]['active']
    cat.toggle_country(code, not current)
    status = '✅ مفعلة' if not current else '❌ معطلة'
    _bot.reply_to(message, f"الدولة `{code}` الآن: **{status}**", parse_mode='Markdown')


@router.callback('admin:cat_toggle_service')
def admin_cat_toggle_service_prompt(call):
    msg = _bot.edit_message_text(
        "📡 أرسل رمز الخدمة للتفعيل/التعطيل:\nمثال: `telegram`",
        call.message.chat.id, call.message.message_id, parse_mode='Markdown'
    )
    _bot.register_next_step_handler(msg, _process_toggle_service)


def _process_toggle_service(message):
    from services.catalog_manager import catalog as cat
    code = message.text.strip().lower()
    services = cat.get_all_services()
    matched = [s for s in services if s['code'] == code]
    if not matched:
        _bot.reply_to(message, f"❌ الخدمة '{code}' غير موجودة في الكتالوج.")
        return
    current = matched[0]['active']
    cat.toggle_service(code, not current)
    status = '✅ مفعلة' if not current else '❌ معطلة'
    _bot.reply_to(message, f"الخدمة `{code}` الآن: **{status}**", parse_mode='Markdown')


@router.callback('admin:cat_prices')
def admin_cat_prices(call):
    from telebot import types

    from services.catalog_manager import catalog as cat
    active_prices = cat.get_active_prices()
    lines = ["💲 **قواعد أسعار الكتالوج**\n"]
    if not active_prices:
        lines.append("_لا توجد قواعد أسعار نشطة._")
    else:
        for p in active_prices[:12]:
            lines.append(
                f"• {p.get('country','?')}/{p.get('service','?')} "
                f"→ {p.get('final_price',0):.2f} USD "
                f"(الربح: {p.get('profit_pct',0)}% + {p.get('profit_fixed',0)})"
            )
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("➕ تعيين سعر", callback_data="admin:cat_set_price"),
        types.InlineKeyboardButton("🌍 الدول", callback_data="admin:catalog"),
        types.InlineKeyboardButton("◀️ لوحة التحكم", callback_data="admin:dashboard"),
    )
    _bot.edit_message_text('\n'.join(lines), call.message.chat.id,
                           call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')


@router.callback('admin:cat_set_price')
def admin_cat_set_price_prompt(call):
    msg = _bot.edit_message_text(
        "💲 أرسل قاعدة السعر:\n"
        "الصيغة: `COUNTRY_CODE SERVICE_CODE PROFIT% [FIXED]`\n"
        "مثال: `cyprus telegram 30 0.50`",
        call.message.chat.id, call.message.message_id, parse_mode='Markdown'
    )
    _bot.register_next_step_handler(msg, _process_set_price)


def _process_set_price(message):
    from db.context import db_context
    from services.catalog_manager import catalog as cat
    parts = message.text.strip().split()
    if len(parts) < 3:
        _bot.reply_to(message, "❌ الصيغة: COUNTRY SERVICE PROFIT% [FIXED]")
        return
    try:
        country = parts[0].lower()
        service = parts[1].lower()
        profit_pct = float(parts[2])
        profit_fixed = float(parts[3]) if len(parts) > 3 else 0.0
        with db_context('default', transactional=False) as db:
            row = db.fetchone(
                """SELECT provider_id, price_usd FROM provider_prices
                   WHERE country_code = %s AND service_code = %s
                   AND available_count > 0 ORDER BY price_usd ASC LIMIT 1""",
                (country, service))
            if not row:
                _bot.reply_to(message, f"❌ لا يوجد سعر مزود لـ {country}/{service}")
                return
            provider_id = int(row[0])
            base_price = float(row[1])
            final_price = round(base_price * (1 + profit_pct / 100) + profit_fixed, 4)
        cat.set_pricing(country, service, provider_id, base_price, profit_pct, profit_fixed)
        _bot.reply_to(message,
            f"✅ تم تعيين قاعدة السعر:\n"
            f"• {country}/{service}\n"
            f"• الأساس: {base_price:.4f} USD\n"
            f"• الربح: {profit_pct}% + {profit_fixed}\n"
            f"• النهائي: {final_price:.4f} USD",
            parse_mode='Markdown')
    except ValueError:
        _bot.reply_to(message, "❌ رقم غير صالح. الصيغة: COUNTRY SERVICE PROFIT% [FIXED]")


@router.callback('admin:cat_services')
def admin_cat_services(call):
    from telebot import types

    from services.catalog_manager import catalog as cat
    services = cat.get_all_services()
    lines = ["📡 **خدمات الكتالوج**\n"]
    for s in services:
        icon = '✅' if s['active'] else '❌'
        lines.append(f"{icon} `{s['code']}` — {s['name']} [{s.get('category','other')}]")
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("✅ تفعيل/تعطيل خدمة", callback_data="admin:cat_toggle_service"),
        types.InlineKeyboardButton("🌍 الدول", callback_data="admin:catalog"),
        types.InlineKeyboardButton("◀️ لوحة التحكم", callback_data="admin:dashboard"),
    )
    _bot.edit_message_text('\n'.join(lines), call.message.chat.id,
                           call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')


# ═══════════════════════════════════════════════════════════════
# CURRENCIES
# ═══════════════════════════════════════════════════════════════

@router.callback('admin:currencies')
def admin_currencies(call):
    from telebot import types

    from services.currency_engine import currency_engine
    currencies = currency_engine.get_all_currencies()
    lines = ["💱 **العملات**\n"]
    for c in currencies[:15]:
        icon = '✅' if c['is_active'] else '❌'
        default = '⭐' if c['is_default'] else ''
        lines.append(f"{icon}{default} **{c['code']}** — {c['name']} — 1 USD = {c['rate_to_usd']}")
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("➕ إضافة عملة", callback_data="admin:curr_add"),
        types.InlineKeyboardButton("◀️ لوحة التحكم", callback_data="admin:dashboard"),
    )
    _bot.edit_message_text('\n'.join(lines), call.message.chat.id,
                           call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')


# ═══════════════════════════════════════════════════════════════
# SUBSCRIPTIONS
# ═══════════════════════════════════════════════════════════════

@router.callback('admin:subscriptions')
def admin_subscriptions(call):
    from telebot import types

    from services.subscription_service import subscriptions
    tiers = subscriptions.get_all_tiers()
    lines = ["🎫 **مستويات الاشتراك**\n"]
    for tier_name, limits in tiers.items():
        lines.append(
            f"• **{tier_name.upper()}**: {limits['max_daily']}/يوم, "
            f"خصم {limits['discount_pct']}%, API: {'✅' if limits['api_access'] else '❌'}"
        )
    lines.append("\n_أرسل معرف المستخدم لتغيير المستوى:_")
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("FREE", callback_data="admin:sub_set_free"),
        types.InlineKeyboardButton("PREMIUM", callback_data="admin:sub_set_premium"),
        types.InlineKeyboardButton("RESELLER", callback_data="admin:sub_set_reseller"),
        types.InlineKeyboardButton("ENTERPRISE", callback_data="admin:sub_set_enterprise"),
        types.InlineKeyboardButton("◀️ لوحة التحكم", callback_data="admin:dashboard"),
    )
    _bot.edit_message_text('\n'.join(lines), call.message.chat.id,
                           call.message.message_id, reply_markup=keyboard, parse_mode='Markdown')


@router.callback('admin:sub_set_free')
def admin_sub_free_prompt(call):
    _prompt_set_tier(call, 'free')

@router.callback('admin:sub_set_premium')
def admin_sub_premium_prompt(call):
    _prompt_set_tier(call, 'premium')

@router.callback('admin:sub_set_reseller')
def admin_sub_reseller_prompt(call):
    _prompt_set_tier(call, 'reseller')

@router.callback('admin:sub_set_enterprise')
def admin_sub_enterprise_prompt(call):
    _prompt_set_tier(call, 'enterprise')


def _prompt_set_tier(call, tier_name):
    msg = _bot.edit_message_text(
        f"🎫 أرسل معرف المستخدم لتعيين المستوى **{tier_name.upper()}**:",
        call.message.chat.id, call.message.message_id, parse_mode='Markdown'
    )
    _bot.register_next_step_handler(msg, lambda m, t=tier_name: _process_set_tier(m, t))


def _process_set_tier(message, tier_name):
    from services.subscription_service import SubscriptionTier, subscriptions
    try:
        uid = int(message.text.strip())
        tier = SubscriptionTier(tier_name)
        success = subscriptions.set_tier(uid, tier, message.from_user.id)
        if success:
            _bot.reply_to(message, f"✅ تم تعيين مستوى المستخدم {uid} إلى **{tier_name.upper()}**", parse_mode='Markdown')
        else:
            _bot.reply_to(message, "❌ فشل تعيين المستوى (صلاحية غير كافية أو مستخدم غير موجود).")
    except ValueError:
        _bot.reply_to(message, "❌ معرف مستخدم غير صالح.")


# ═══════════════════════════════════════════════════════════════
# REFERRALS
# ═══════════════════════════════════════════════════════════════

@router.callback('admin:referrals')
def admin_referrals(call):
    from telebot import types

    from services.referral_service import referrals
    lines = ["🔗 **نظام الإحالات**\n",
             f"💰 المكافأة: {referrals.REFERRAL_BONUS_AMOUNT:,} T",
             f"📈 العمولة: {referrals.REFERRER_COMMISSION_PCT}%",
             f"👥 الحد الأقصى/مستخدم: {referrals.MAX_REFERRALS_PER_USER}\n",
             "أرسل معرف المستخدم لعرض إحالاته:"]
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("◀️ لوحة التحكم", callback_data="admin:dashboard"))
    _bot.edit_message_text('\n'.join(lines), call.message.chat.id,
                           call.message.message_id, reply_markup=keyboard)


# ═══════════════════════════════════════════════════════════════
# WEB PANEL
# ═══════════════════════════════════════════════════════════════

@router.callback('admin:web_panel')
def admin_web_panel(call):
    import os

    from telebot import types
    token = os.getenv('ADMIN_API_TOKEN', '')
    webhook_url = os.getenv('WEBHOOK_URL', 'http://localhost:5000')
    if not token:
        _bot.answer_callback_query(call.id, "⚠️ ADMIN_API_TOKEN غير معرف. قم بتعيينه في .env", show_alert=True)
        return
    panel_url = f"{webhook_url}/admin?token={token}"
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("🖥️ فتح لوحة الإدارة", url=panel_url),
        types.InlineKeyboardButton("◀️ لوحة التحكم", callback_data="admin:dashboard"),
    )
    _bot.edit_message_text(
        f"🖥️ **لوحة إدارة الويب**\n\n"
        f"اضغط أدناه للوصول للوحة التحكم الكاملة:\n"
        f"🔗 `{panel_url}`",
        call.message.chat.id, call.message.message_id,
        reply_markup=keyboard, parse_mode='Markdown'
    )

# Admin Payment Approval Callbacks (migrated from customer bot)
