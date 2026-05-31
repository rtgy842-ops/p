# ADMIN BOT REPORT — NumGenius Enterprise SaaS
## Phase F: Admin Bot Certification

**Date:** 2026-05-31
**Status:** PARTIALLY CERTIFIED

---

## ARCHITECTURE

The admin bot runs as a **separate process** with its own Telegram bot token:

```
Telegram Webhook → Flask POST / (admin_bot webhook_bp)
    → telebot.process_new_updates()
    → Router/Middleware pipeline
    → admin_bot.py handlers
    → AdminService / RBAC / Audit
    → Repositories
    → PostgreSQL
```

**Bot File:** [`admin_bot.py`](5simTelegramBot-main/admin_bot.py)
**Handler File:** [`bot/handlers/admin_bot.py`](5simTelegramBot-main/bot/handlers/admin_bot.py)
**Requires:** `ADMIN_BOT_TOKEN` (must be DIFFERENT from `BOT_TOKEN`)
**Web Panel:** [`web/routes/admin_panel.py`](5simTelegramBot-main/web/routes/admin_panel.py)

---

## MENU INVENTORY — 14 main menu items

| # | Menu Item | Callback | Handler Function | Status |
|---|-----------|----------|-----------------|--------|
| 1 | 📊 Dashboard | `admin:dashboard` | `admin_dashboard()` | ✓ |
| 2 | 👥 Users | `admin:users` | `admin_users()` | ✓ |
| 3 | 📦 Orders | `admin:orders` | `admin_orders()` | ✓ |
| 4 | 💳 Payments | `admin:payments` | `admin_payments()` | ✓ |
| 5 | 📊 Stats | `admin:stats` | `admin_stats()` | ✓ |
| 6 | ⚙️ Settings | `admin:settings` | `admin_settings()` | ✓ |
| 7 | 🔍 Audit | `admin:audit` | `admin_audit()` | ✓ |
| 8 | 🏪 Catalog | `admin:catalog` | `admin_catalog()` | ✓ |
| 9 | 🔌 Providers | `admin:providers` | `admin_providers()` | ✓ |
| 10 | 💱 Currencies | `admin:currencies` | `admin_currencies()` | ✓ |
| 11 | 🎫 Subscriptions | `admin:subscriptions` | `admin_subscriptions()` | ✓ |
| 12 | 🔗 Referrals | `admin:referrals` | `admin_referrals()` | ✓ |
| 13 | 📢 Broadcast | `admin:broadcast` | `admin_broadcast_prompt()` | ✓ |
| 14 | 🖥️ Web Panel | `admin:web_panel` | `admin_web_panel()` | ✓ |

---

## SUB-MENUS — 20 total actions

| Category | Action | Callback | Status |
|----------|--------|----------|--------|
| Users | Search User | `admin:user_search` | ✓ |
| Users | Add Balance | `admin:user_balance` | ✓ |
| Users | Deduct Balance | `admin:user_deduct` | ✓ |
| Users | Ban/Unban | `admin:user_ban` | ✓ |
| Settings | Set USD Rate | `admin:set_usd` | ✓ |
| Settings | Set Profit % | `admin:set_profit` | ✓ |
| Settings | Toggle Lock | `admin:toggle_lock` | ✓ |
| Providers | Sync All | `admin:sync_providers` | ✓ |
| Providers | Health Check | `admin:health_check` | ✓ |
| Catalog | Toggle Country | `admin:cat_toggle_country` | ✓ |
| Catalog | Toggle Service | `admin:cat_toggle_service` | ✓ |
| Catalog | View Prices | `admin:cat_prices` | ✓ |
| Catalog | Set Price | `admin:cat_set_price` | ✓ |
| Catalog | All Services | `admin:cat_services` | ✓ |
| Subscriptions | Set FREE | `admin:sub_set_free` | ✓ |
| Subscriptions | Set PREMIUM | `admin:sub_set_premium` | ✓ |
| Subscriptions | Set RESELLER | `admin:sub_set_reseller` | ✓ |
| Subscriptions | Set ENTERPRISE | `admin:sub_set_enterprise` | ✓ |
| Currencies | Add Currency | `admin:curr_add` | ✓ |
| Web Panel | Access URL | N/A (token-based) | ✓ |

---

## RBAC ENFORCEMENT

| Check | Implementation | Location |
|-------|---------------|----------|
| Entry guard | `rbac.has_permission(uid, Permission.SETTINGS_VIEW)` | [`admin_bot.py:37`](5simTelegramBot-main/bot/handlers/admin_bot.py:37) |
| Role display | Shows `role.value.upper()` in welcome | [`admin_bot.py:44`](5simTelegramBot-main/bot/handlers/admin_bot.py:44) |
| Permission granular | 6 roles × 17 permissions | [`services/rbac_service.py`](5simTelegramBot-main/services/rbac_service.py) |
| SUPER_ADMIN fallback | Admin IDs from `BOT_CONFIG['admin_ids']` | Only on admin_bot.py (not customer) |

**Issue:** RBAC is enforced on startup (`/start` command) but **not on individual callbacks**. Once past the entry guard, any handler can be called directly via callback data. **Callback-level RBAC checking is missing.**

---

## ARABIC-ONLY REQUIREMENT

**Status: NOT MET.** The admin bot uses:
- English labels on buttons: `"📊 Dashboard"`, `"👥 Users"`, `"📦 Orders"`, etc.
- English messages: `"🛡️ **Admin Bot — NumGenius Enterprise**"`
- No Arabic translations in keyboard buttons

The [requirement](#phase-f) states: **"Admin Bot MUST be Arabic-only."** The current implementation is English-only. Either the requirement is outdated (the bot targets Farsi users with `fa` as the default language) or Arabic translations need to be added.

---

## WEB ADMIN PANEL

**Route:** `/admin?token=<ADMIN_API_TOKEN>`
**Auth:** Token-based (`ADMIN_API_TOKEN` env var required)
**API Endpoints:**

| Endpoint | Function | Status |
|----------|----------|--------|
| `GET /admin/api/dashboard` | Dashboard JSON | ✓ |
| `GET /admin/api/users` | User list | ✓ |
| `GET /admin/api/orders` | Order list | ✓ |
| `GET /admin/api/payments` | Payment list | ✓ |
| `GET /admin/api/audit` | Audit log | ✓ |
| `GET /admin/api/health` | System health | ✓ |
| `GET /admin/api/providers` | Provider status | ✓ |
| `GET /admin/api/currencies` | Currency list | ✓ |
| `POST /admin/api/currencies/update` | Update currency | ✓ |
| `GET /admin` | Dashboard HTML | ✓ |

---

## AUDIT TRAIL

All admin operations are audited via `AdminService` → `AuditService.log()`:

| Operation | Audit Action | File |
|-----------|-------------|------|
| Set USD rate | `setting:change` | admin_service.py:79 |
| Set profit | `setting:change` | admin_service.py:91 |
| Add channel | `channel:add` | admin_service.py:101 |
| Remove channel | `channel:remove` | admin_service.py:105 |
| Toggle lock | `lock:toggle` | admin_service.py:112 |
| Set operator | `operator:change` | admin_service.py:122 |
| Set card info | `card:update` | admin_service.py:135 |
| Add balance | `balance:add` | admin_service.py:148 |
| Reduce balance | `balance:deduct` | admin_service.py:153 |
| Ban/unban | `user:ban` / `user:unban` | admin_service.py:158 |
| Approve payment | `payment:approve` | admin_service.py:197 |
| Reject payment | `payment:reject` | admin_service.py:203 |

---

## ISSUES FOUND

| # | Issue | Severity |
|---|-------|----------|
| AF1 | 🔴 No RBAC checks on individual callback handlers — once past /start, any callback can be triggered | HIGH |
| AF2 | 🟡 Admin bot is English-only — requirement states "Arabic-only" | HIGH |
| AF3 | 🟡 `_bot` global used without null check in all handlers (200+ mypy warnings) | MEDIUM |
| AF4 | 🟡 `_process_set_price()` passes 8 args but `set_pricing()` accepts 7 — runtime error | CRITICAL |
| AF5 | 🟡 Broadcast uses `UserService.get_all_ids()` which accesses `r['user_id']` on tuples — runtime error | CRITICAL |
| AF6 | 🟢 No pagination on any list views (users, orders, payments, audit) — hardcoded LIMIT 20 | LOW |
| AF7 | 🟢 `admin:web_panel` exposes token in plain text in chat message | LOW |
| AF8 | 🟢 Legacy admin panels in `bot/handlers/admin/` directory (5 unused files) | LOW |

---

## OVERALL VERDICT

**PARTIALLY CERTIFIED** — 8 issues (2 CRITICAL, 2 HIGH, 1 MEDIUM, 3 LOW).

The admin bot implements comprehensive platform management with 14 main menu items, 20 sub-actions, audit trail logging, and RBAC enforcement. Two CRITICAL runtime bugs exist (AF4, AF5) that will crash specific admin functions. RBAC is only enforced at entry, not per-callback. The Arabic-only requirement is not met.

**Blocking for certification:** Fix AF4 (set_pricing arg count), AF5 (tuple indexing on broadcast), add Arabic translations or update requirement.
