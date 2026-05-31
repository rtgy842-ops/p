# CUSTOMER BOT CERTIFICATION REPORT — NumGenius Enterprise SaaS
## Phase E: Customer Bot Certification

**Date:** 2026-05-31
**Methodology:** Static code analysis of all customer-facing handlers and routes
**Status:** STATIC AUDIT (No live Telegram bot token available)

---

## 1. HANDLER INVENTORY

| Flow | Handler | File | Registered? | Covered? |
|------|---------|------|------------|----------|
| /start (welcome) | `handle_start` | [`bot/handlers/start.py`](bot/handlers/start.py:23) | ✅ | ✅ Static |
| Language selection | `handle_language` | [`bot/handlers/language.py`](bot/handlers/language.py) | ✅ | ✅ Static |
| Main menu | `main_menu_keyboard` | [`bot/keyboards/main_keyboard.py`](bot/keyboards/main_keyboard.py) | ✅ | ✅ Static |
| Profile / Balance | `handle_check_balance` | [`bot/handlers/purchase.py`](bot/handlers/purchase.py:130) | ✅ | ✅ Static |
| Add funds | `handle_add_funds` | [`bot/handlers/payment.py`](bot/handlers/payment.py:23) | ✅ | ✅ Static |
| ZarinPal payment | `handle_zarinpal_payment` | [`bot/handlers/payment.py`](bot/handlers/payment.py:36) | ✅ | ✅ Static |
| Card-to-card payment | `handle_card_payment` | [`bot/handlers/payment.py`](bot/handlers/payment.py:79) | ✅ | ✅ Static |
| Receipt upload | `handle_send_receipt` | [`bot/handlers/payment.py`](bot/handlers/payment.py:93) | ✅ | ✅ Static |
| Payment callback (/verify) | `verify_payment` | [`bot.py`](bot.py:60) | ✅ | ✅ Static |
| Buy number | `handle_buy_number_entry` | [`bot/handlers/purchase.py`](bot/handlers/purchase.py:120) | ✅ | ✅ Static |
| Buy with params | `handle_buy_number_with_params` | [`bot/handlers/purchase.py`](bot/handlers/purchase.py:21) | ✅ | ✅ Static |
| Get SMS code | `handle_get_code` | [`bot/handlers/purchase.py`](bot/handlers/purchase.py:225) | ✅ | ✅ Static |
| Cancel order | `handle_cancel_order` | [`bot/handlers/purchase.py`](bot/handlers/purchase.py:254) | ✅ | ✅ Static |
| My orders | `handle_my_orders` | [`bot/handlers/purchase.py`](bot/handlers/purchase.py:147) | ✅ | ✅ Static |
| Help | `handle_help` | [`bot/handlers/purchase.py`](bot/handlers/purchase.py:161) | ✅ | ✅ Static |
| Referrals | `handle_referrals` | [`bot/handlers/referrals.py`](bot/handlers/referrals.py) | ✅ | ✅ Static |
| Subscriptions | Subscription handlers | [`bot/handlers/subscriptions.py`](bot/handlers/subscriptions.py) | ✅ | ✅ Static |
| Channel membership | `check_membership` | [`bot/handlers/membership.py`](bot/handlers/membership.py:23) | ✅ | ✅ Static |
| Services list | `back_to_services` | [`bot/handlers/purchase.py`](bot/handlers/purchase.py:212) | ✅ | ✅ Static |
| Copy card number | `handle_copy` | [`bot/handlers/payment.py`](bot/handlers/payment.py:87) | ✅ | ✅ Static |

---

## 2. USER FLOW CERTIFICATION

### 2.1 Registration & Onboarding
- **Flow:** User sends `/start` → `handle_start` → `_user_service.get_or_create()` → shows welcome + language selection
- **Status:** ✅ CODE CORRECT
- **Issues:** None

### 2.2 Language Selection
- **Flow:** User selects language → `i18n.set_user_language()` → `UserRepository.set_language()`
- **Status:** ✅ CODE CORRECT
- **Issues:** None. Falls back to `fa` (Persian) if language not found.

### 2.3 Wallet / Balance Check
- **Flow:** "Check Balance" button → `handle_check_balance` → `get_balance()` → `WalletService.get_balance()`
- **Status:** ✅ CODE CORRECT
- **Issues:** Uses `compat.legacy_facade.get_balance()` instead of `WalletService` directly. Minor indirection.

### 2.4 Deposit — ZarinPal
- **Flow:** "Add Funds" → "Online Payment" → Enter amount → ZarinPal request → Payment URL → User pays → Callback `/verify` → `PaymentService.verify_and_credit()`
- **Status:** ⚠️ PARTIALLY BROKEN (See Payment Report S-8: CSRF state token not appended to callback URL)
- **Issue:** The CSRF protection generates a state token but doesn't include it in the ZarinPal callback URL. All payment callbacks will fail CSRF check.

### 2.5 Deposit — Card-to-Card
- **Flow:** "Add Funds" → "Card Payment" → Enter amount → View card info → Send receipt → Admin approval → Balance credited
- **Status:** ✅ CODE CORRECT
- **Issues:** Uses `compat/legacy_facade.add_balance()` which delegates to `WalletService.deposit()`. Correct atomic path.

### 2.6 Purchase Virtual Number
- **Flow:** "Buy Number" → Select service → Select country → Select operator → `handle_buy_number_with_params()` → Calls HeroSMS → Deducts balance atomic → Creates order
- **Status:** ✅ CODE CORRECT (with qualifiers)
- **Strengths:** Atomic balance deduction + order creation in one transaction
- **Issues:** Hardcoded fallback `price_toman = 50000` if catalog pricing fails (MEDIUM risk)

### 2.7 Receive SMS Code
- **Flow:** "Get Code" → `handle_get_code` → `sms_check_status()` → Parse response → Show code
- **Status:** ✅ CODE CORRECT

### 2.8 Cancel Order
- **Flow:** "Cancel Order" → `handle_cancel_order` → `sms_cancel_number()` → `order_cancel()` → `refund_balance()`
- **Status:** ✅ CODE CORRECT
- **Issues:** Cancellation calls `sms_cancel_number()` first, then `order_cancel()`. If SMS cancel succeeds but DB cancel fails, user loses money with no refund. Should be wrapped in a compensating transaction.

### 2.9 Order History
- **Flow:** "My Orders" → Web URL to `/orders/{user_id}` → Flask route renders `user_orders.html`
- **Status:** ✅ CODE CORRECT

### 2.10 Help System
- **Flow:** "Help" → Sub-menu: Buy, Charge, Get Code, Payment, Delivery, Cancel
- **Status:** ✅ CODE CORRECT — 6 sub-help handlers registered

### 2.11 Referrals
- **Flow:** Referral menu → Show code → Show stats → Share link
- **Status:** ✅ CODE CORRECT — Uses `ReferralService` with DB-backed codes

### 2.12 Subscriptions
- **Flow:** View current tier → View features → (Admin sets tier)
- **Status:** ✅ CODE CORRECT — `SubscriptionService.get_tier()` reads from DB

---

## 3. MIDDLEWARE CHAIN

```
Request → logging_middleware → auth_middleware → language_middleware → Handler
```

| Middleware | Purpose | Status |
|-----------|---------|--------|
| logging | Log user + callback data | ✅ |
| auth | Check if user blocked; admins bypass | ✅ |
| language | Ensure user record exists | ✅ |

**Verdict:** ✅ CORRECT — Proper middleware chain with admin bypass.

---

## 4. WEB ROUTES (Customer-Facing)

| Route | Method | Purpose | Status |
|-------|--------|---------|--------|
| `POST /` | POST | Telegram webhook | ✅ |
| `/verify/<user_id>/<amount>` | GET | ZarinPal callback | ⚠️ CSRF broken |
| `/ping` | GET | Health check | ✅ |
| `/health` | GET | Full health | ✅ |
| `/webhook` | POST | Telegram webhook (blueprint) | ✅ |
| `/orders/<user_id>` | GET | User orders page | ✅ |
| `/number_details/<order_id>` | GET | Number details | ✅ |
| `/order_status/<order_id>` | GET | Order status | ✅ |

---

## 5. CUSTOMER BOT VERDICT

| Category | Score |
|----------|-------|
| Handler completeness | 100% — All flows implemented |
| Middleware | ✅ Correct |
| Payment flow | ⚠️ CSRF state token broken |
| Purchase flow | ⚠️ Hardcoded fallback price |
| Cancel flow | ⚠️ Compensating transaction gap |
| Error handling | ✅ error_boundary wraps all handlers |
| Web routes | ✅ All registered |

**Overall: PARTIALLY_CERTIFIED — 2 blocking issues (CSRF, compensating transaction)**

---

*End of Phase E — Customer Bot Report*
