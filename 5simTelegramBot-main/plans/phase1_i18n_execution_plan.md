# Phase 1: i18n Completion — Detailed Execution Plan

## Strategy: Convert all hardcoded strings to `get_text()` calls, file by file.

---

## Batch 1: Critical User-Facing Handlers (bot.py)

### 1.1 `back_to_main_menu()` — Line 553-559
**Current:**
```python
bot.edit_message_text(
    "👋 به منوی اصلی بازگشتید.\nلطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
    call.message.chat.id,
    call.message.message_id,
    reply_markup=inline_main_keyboard(call.from_user.id)
)
```
**Fix:** Replace with `get_text(user_id, 'welcome_back')` — KEY ALREADY EXISTS in all 3 JSON files.

---

### 1.2 `handle_service_selection()` — Lines 562-629
Hardcoded strings at lines: 568, 619, 622, 629
- Line 568: `"❌ خطا در دریافت اطلاعات محصولات"` → `services.error_fetch` (key needs to be added)
- Line 619: `"🔙 برگشت به سرویس‌ها"` → `navigation.back_to_services` (EXISTS)
- Line 622: `f"🌍 لطفاً کشور مورد نظر خود را برای سرویس {service} انتخاب کنید:"` → `countries.select` (EXISTS, needs `service=service`)
- Line 629: `"❌ خطایی رخ داد. لطفاً دوباره تلاش کنید."` → `errors.general` (EXISTS)

---

### 1.3 `handle_country_selection()` — Lines 790-937
Mostly already uses get_text(). Just one gap:
- Line 806-807: Uses `country_name` from operator_config which returns Persian names like "قبرس 🇨🇾". These should be fetched via i18n keys like `countries.cyprus`.

**Note:** `operator_config.py` stores `country_name` as hardcoded Persian text with emoji flags in its default data. This is a data concern, not a code concern — the operator settings DB has Persian names hardcoded. This needs a mapping approach.

---

### 1.4 `handle_buy_number()` — Lines 2200-2425
**Massive block of hardcoded strings.** Key sections:
- Line 2276: `"⚠️ موجودی شما کافی نیست"` 
- Line 2279: `"💰 افزایش موجودی"`
- Line 2280: `"🔙 برگشت"`
- Lines 2283-2293: Full insufficient balance message
- Line 2298: `f"⏳ در حال خرید شماره {service} از {country_name}... لطفاً صبر کنید."`
- Lines 2346-2359: Full success message
- Lines 2364-2368: Error saving order message
- Lines 2379-2388: Buy error message
- Lines 2391-2399: Operator unavailable message
- Lines 2402-2408: Service/country unavailable message
- Lines 2412-2417: Price fetch error message

**All have corresponding keys** in `purchase.*` section of locale files.

---

### 1.5 `handle_get_code()` — Lines 2427-2497
- Lines 2459-2460: `"مشاهده جزئیات سفارش"` and `"🔙 برگشت به منوی اصلی"`
- Lines 2462-2468: Full code received message
- Line 2491: `"⏳ کد هنوز دریافت نشده است. لطفاً کمی صبر کنید."`
- Line 2493: `"❌ خطا در بررسی وضعیت سفارش"`

**All have corresponding keys** in `order.*` section.

---

### 1.6 `handle_cancel_order()` — Lines 2566-2641
- Lines 2574-2575: `"⏳ در حال لغو سفارش... لطفاً صبر کنید."`
- Lines 2602-2639: Full cancel success/error messages with keyboard buttons

---

### 1.7 `handle_my_orders()` — Lines 2824-2848
- Lines 2833: `"🌐 مشاهده سفارش‌ها در وب"`
- Lines 2836: `"🔙 برگشت به منو"`
- Lines 2840-2841: Full message

---

## Batch 2: Payment Handlers (bot.py)

### 2.1 `handle_add_funds()` — Lines 2911-2925
- Lines 2915-2917: Payment method buttons — keys `payment_methods.zarinpal` and `payment_methods.card_to_card` needed
- Line 2921: `"💰 لطفاً روش پرداخت را انتخاب کنید:"` → `payment.select_method` (EXISTS)

### 2.2 `handle_zarinpal_payment()` / `process_zarinpal_amount()` — Lines 2927-2993
- Full function needs i18n

### 2.3 `verify_payment()` — Lines 2995-3094
- Flask route, no user_id context for `get_text()` — needs special handling

### 2.4 Card payment handlers — Lines 3096-3254
- `handle_card_payment()`, `handle_send_receipt()`, `check_card_info()`, `handle_new_card()`, `process_card_number()`, `process_card_holder()`

---

## Batch 3: Operator Settings & Admin (bot.py)

### 3.1 `handle_operator_settings()` — Lines 2678-2719
- Hardcoded service/country display names (lines 2688-2696)

### 3.2 `handle_change_operator()` — Lines 2721-2747
- Hardcoded service names in keyboard buttons

### 3.3 `handle_select_service()` — Lines 2749-2786
- Hardcoded country names

### 3.4 `process_operator_change()` — Lines 2803-2821
- Success/error messages

---

## Batch 4: New i18n Keys Required

Keys that exist in locale JSONs but are not yet wired up (or need to be added):

### Already in JSON files (just need wiring):
All `purchase.*`, `order.*`, `payment.*`, `operators.*`, `errors.*`, `navigation.*` keys are already in all 3 JSON files.

### Keys that need to be ADDED to all 3 JSON files:
| Key | en value |
|-----|----------|
| `payment_methods.zarinpal` | "💳 Online Payment (ZarinPal)" |
| `payment_methods.card_to_card` | "💳 Card to Card" |
| `services.error_fetch` | "❌ Error fetching service information" |

---

## Batch 5: Code Cleanup

### 5.1 Remove duplicate functions in bot.py
[`bot.py`](bot.py:105-128) and [`bot.py`](bot.py:130-156) have local `get_user_balance()` and `add_balance()` that duplicate [`database.py`](database.py:114-154). Remove these duplicates from bot.py and import from database.py instead (already imported on line 14).

---

## Execution Order

| Seq | File | Lines | Action | Confidence |
|-----|------|-------|--------|------------|
| 1 | `bot.py` | 553-559 | Fix `back_to_main_menu()` | 🟢 Trivial |
| 2 | `bot.py` | 562-629 | Fix `handle_service_selection()` | 🟢 Easy |
| 3 | `bot.py` | 2200-2425 | Fix `handle_buy_number()` | 🟡 Large block |
| 4 | `bot.py` | 2427-2497 | Fix `handle_get_code()` | 🟢 Medium |
| 5 | `bot.py` | 2566-2641 | Fix `handle_cancel_order()` | 🟢 Medium |
| 6 | `bot.py` | 2824-2848 | Fix `handle_my_orders()` | 🟢 Small |
| 7 | `bot.py` | 2911-2925 | Fix `handle_add_funds()` | 🟢 Small |
| 8 | `bot.py` | 2927-2993 | Fix payment amount handlers | 🟡 Medium |
| 9 | `bot.py` | 3096-3254 | Fix card payment handlers | 🟡 Medium |
| 10 | `bot.py` | 2678-2821 | Fix operator settings handlers | 🟡 Medium |
| 11 | `bot.py` | 105-156 | Remove duplicate balance functions | 🟢 Safe |
| 12 | `locales/*.json` | — | Add 3 missing keys | 🟢 Trivial |

---

## What Does NOT Change

These are NOT touched to ensure stability:
- ❌ **NO database schema changes** (language column already exists)
- ❌ **NO wallet/payment logic changes** (`wallet.py`, `payment.py`, `card_payment.py` only have i18n imports already)
- ❌ **NO API endpoint changes** (5sim API calls remain as-is for Phase 1)
- ❌ **NO config changes**
- ❌ **NO backup system changes**
- ❌ **NO operator_config logic changes** (only some display strings may be routed through i18n)
