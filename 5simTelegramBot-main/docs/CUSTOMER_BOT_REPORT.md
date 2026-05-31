# CUSTOMER BOT REPORT — NumGenius Enterprise SaaS
## Phase E: Customer Bot Certification

**Date:** 2026-05-31
**Status:** PARTIALLY CERTIFIED

---

## ARCHITECTURE

The customer bot architecture is:

```
Telegram Webhook → Flask POST / (webhook_bp)
    → telebot.process_new_updates()
    → Router/Middleware pipeline
    → Handlers (purchase.py, payment.py, referrals.py, subscriptions.py, etc.)
    → compat/legacy_facade.py
    → Services (WalletService, SMSService, OrderService, PaymentService)
    → Repositories (UserRepository, TransactionRepository, OrderRepository)
    → PostgreSQL
```

**Bot File:** [`bot.py`](5simTelegramBot-main/bot.py)

---

## HANDLER INVENTORY

| Feature | Route/Callback | Handler File | Status |
|---------|---------------|-------------|--------|
| /start | bot.message_handler | [`bot/handlers/start.py`](5simTelegramBot-main/bot/handlers/start.py) | ✓ Implemented |
| /language | bot.message_handler | [`bot/handlers/language.py`](5simTelegramBot-main/bot/handlers/language.py) | ✓ Implemented |
| language selection | `setlang_*` callback | [`bot/handlers/language.py`](5simTelegramBot-main/bot/handlers/language.py) | ✓ Implemented |
| main menu | `back_to_main` callback | [`bot/handlers/purchase.py`](5simTelegramBot-main/bot/handlers/purchase.py) | ✓ Implemented |
| balance check | `check_balance` callback | [`bot/handlers/purchase.py`](5simTelegramBot-main/bot/handlers/purchase.py) | ✓ Implemented |
| add funds menu | `add_funds` callback | [`bot/handlers/payment.py`](5simTelegramBot-main/bot/handlers/payment.py) | ✓ Implemented |
| zarinpal payment | `zarinpal_payment` callback | [`bot/handlers/payment.py`](5simTelegramBot-main/bot/handlers/payment.py) | ✓ Implemented |
| card payment | `card_payment` callback | [`bot/handlers/payment.py`](5simTelegramBot-main/bot/handlers/payment.py) | ✓ Implemented |
| send receipt | `send_receipt_*` callback | [`bot/handlers/payment.py`](5simTelegramBot-main/bot/handlers/payment.py) | ✓ Implemented |
| payment verify | `/verify/<uid>/<amt>` route | [`bot.py:38`](5simTelegramBot-main/bot.py:38) | ✓ Implemented |
| buy number | `buy_number` callback | [`bot/handlers/purchase.py`](5simTelegramBot-main/bot/handlers/purchase.py) | ✓ Implemented |
| service selection | `service_*` callback | [`bot/handlers/services.py`](5simTelegramBot-main/bot/handlers/services.py) | ✓ Implemented |
| country selection | `country_*` callback | [`bot/handlers/services.py`](5simTelegramBot-main/bot/handlers/services.py) | ✓ Implemented |
| confirm purchase | `buy_number_*` callback | [`bot/handlers/purchase.py`](5simTelegramBot-main/bot/handlers/purchase.py) | ✓ Implemented |
| get SMS code | `get_code_*` callback | [`bot/handlers/purchase.py`](5simTelegramBot-main/bot/handlers/purchase.py) | ✓ Implemented |
| cancel order | `cancel_order_*` callback | [`bot/handlers/purchase.py`](5simTelegramBot-main/bot/handlers/purchase.py) | ✓ Implemented |
| my orders | `my_orders` callback | [`bot/handlers/purchase.py`](5simTelegramBot-main/bot/handlers/purchase.py) | ✓ Implemented |
| order details | `/number_details/<id>` route | [`routes/order_details.py`](5simTelegramBot-main/routes/order_details.py) | ✓ Implemented |
| web orders | `/orders/<uid>` route | [`web/routes/orders.py`](5simTelegramBot-main/web/routes/orders.py) | ✓ Implemented |
| referrals | `referrals` callback | [`bot/handlers/referrals.py`](5simTelegramBot-main/bot/handlers/referrals.py) | ✓ Implemented |
| referrals list | `referrals_list` callback | [`bot/handlers/referrals.py`](5simTelegramBot-main/bot/handlers/referrals.py) | ✓ Implemented |
| subscriptions | `subscriptions` callback | [`bot/handlers/subscriptions.py`](5simTelegramBot-main/bot/handlers/subscriptions.py) | ✓ Implemented |
| subscription plans | `subs_plans` callback | [`bot/handlers/subscriptions.py`](5simTelegramBot-main/bot/handlers/subscriptions.py) | ✓ Implemented |
| membership check | `check_membership` callback | [`bot/handlers/membership.py`](5simTelegramBot-main/bot/handlers/membership.py) | ✓ Implemented |
| help menu | `help` callback | [`bot/handlers/purchase.py`](5simTelegramBot-main/bot/handlers/purchase.py) | ✓ Implemented |
| help sub-items | `help_*` callbacks | [`bot/handlers/purchase.py`](5simTelegramBot-main/bot/handlers/purchase.py) | ✓ Implemented |
| admin panel | `admin_panel` callback | [`bot/handlers/admin/dashboard.py`](5simTelegramBot-main/bot/handlers/admin/dashboard.py) | ✓ Implemented |

**Total: 27 user flows implemented**

---

## USER FLOW VERIFICATION (Code Analysis)

### Flow 1: `/start` → Profile
- `handle_start(message)` creates user via `UserService.get_or_create()`
- Shows welcome text with `main_menu_keyboard`
- Middleware pipeline ensures user exists and language is set
- **Status:** PASS

### Flow 2: Language Selection
- `/language` command shows language options
- `setlang_<code>` callback persists language to DB
- `get_text()` uses stored language preference
- **Status:** PASS

### Flow 3: Balance Check
- `check_balance` callback → `WalletService.get_balance()` (static)
- Displays balance with add_funds button
- **Status:** PASS (but uses mixed static/instance pattern — see C4)

### Flow 4: Deposit via ZarinPal
- `zarinpal_payment` → user enters amount
- `process_zarinpal_amount()` → `PaymentService.initiate_payment(gateway=ZARINPAL, ...)`
- Returns payment URL → user redirected to ZarinPal
- Callback `/verify/<uid>/<amount>?Authority=...&Status=OK`
- `PaymentService.verify_and_credit()` → idempotent + atomic
- **Status:** PASS

### Flow 5: Deposit via Card-to-Card
- `card_payment` → `CardPayment.handle_new_payment()`
- Shows card info → user sends receipt photo
- Admin approves → `PaymentService.approve_card_payment()`
- **Status:** PASS

### Flow 6: Purchase Number
- `buy_number` → `services_keyboard(user_id)`
- `service_*` → `_get_countries_for_service()` from SSOT
- `country_*` → `SMSService.get_price_info()` shows price
- `buy_number_<svc>_<country>_<op>` → atomic purchase:
  1. Calculate price
  2. Check balance
  3. Call SMS provider (before DB mutation)
  4. Atomic DB: lock row + deduct + create order
  5. If order save fails, auto-refund
- **Status:** PASS (atomic design verified)

### Flow 7: Receive SMS
- `get_code_<activation_id>` → `SMSService.check_sms()`
- Parses `STATUS_OK:CODE` or `STATUS_WAIT_CODE`
- Saves code to DB via `order_save_code()`
- **Status:** PASS

### Flow 8: Cancel Order
- `cancel_order_<activation_id>` → `SMSService.cancel_number()`
- On success: `compat.order_cancel()` → refunds balance
- **Status:** PASS

### Flow 9: My Orders
- Redirects to web page at `/orders/<user_id>`
- Web route renders `user_orders.html`
- **Status:** PASS

### Flow 10: Referrals
- Shows referral code, invite link, stats
- `copy_ref_<code>` shows code for copying
- `referrals_list` shows referred users
- **Status:** PASS

### Flow 11: Subscriptions
- Shows current tier, limits, discount
- `subs_plans` shows all tiers
- **Status:** PASS

### Flow 12: Help/Support
- Help menu with 6 FAQ topics
- Each shows translated answer
- **Status:** PASS

### Flow 13: Channel Membership Check
- `check_membership` verifies user joined required channels
- Shows join links for unsubscribed channels
- **Status:** PASS

---

## MIDDLEWARE PIPELINE

| Middleware | Order | Function |
|-----------|-------|----------|
| Logging | 1 | Logs user_id + callback data |
| Auth | 2 | Blocks if user is_blocked |
| Language | 3 | Ensures user DB record exists |

**Status:** PASS — correct ordering, robust error handling

---

## I18N SUPPORT

- 3 locale files: [`locales/en.json`](5simTelegramBot-main/locales/en.json), [`ar.json`](5simTelegramBot-main/locales/ar.json), [`fa.json`](5simTelegramBot-main/locales/fa.json)
- Default language: `fa` (Farsi)
- RTL support flag in `_meta.direction`
- Fallback to default language if key not found in user's language
- **Status:** PASS

---

## ISSUES FOUND

| # | Issue | Severity | File |
|---|-------|----------|------|
| CE1 | 🟡 Handler duplication — help menu in both `purchase.py` and `help.py` | HIGH | purchase.py:157, help.py:17 |
| CE2 | 🟡 `WalletService.get_balance()` called as static but `WalletService()` as instance | HIGH | purchase.py:52,79 |
| CE3 | 🟡 Duplicate `services.py` handlers also registered as direct bot handlers | MEDIUM | services.py:31-147 |
| CE4 | 🟢 Hardcoded price fallback `50000` in purchase handler | LOW | purchase.py:40 |
| CE5 | 🟢 No CSRF protection on `/verify` payment callback route | CRITICAL | bot.py:38 |

---

## OVERALL VERDICT

**PARTIALLY CERTIFIED** — 5 issues (1 CRITICAL, 2 HIGH, 1 MEDIUM, 1 LOW).

The customer bot implements 27 user flows across 13 feature areas. All flows are properly wired with atomic database operations, middleware protection, and i18n support. The critical issue is missing CSRF/token verification on the payment callback endpoint, plus handler duplication between `help.py` and `purchase.py`.

**Blocking for certification:** Fix CE5 (CSRF on /verify route) and CE1 (duplicate handlers).
