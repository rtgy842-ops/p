# PAYMENT CERTIFICATION REPORT — NumGenius Enterprise SaaS
## Phase H: Payment Lifecycle Certification

**Date:** 2026-05-31
**Methodology:** Static code flow analysis of ALL payment paths
**Status:** STATIC AUDIT

---

## 1. PAYMENT GATEWAYS

| Gateway | Class | File | Status |
|---------|-------|------|--------|
| ZarinPal | `ZarinPalGateway(BasePaymentGateway)` | [`services/payment_service.py:53`](services/payment_service.py:53) | ✅ Active |
| Card-to-Card | `CardToCardGateway(BasePaymentGateway)` | [`services/payment_service.py:183`](services/payment_service.py:183) | ✅ Active |

---

## 2. ZARINPAL PAYMENT LIFECYCLE

### 2.1 Initiation
```
User: "Add Funds" → "Online Payment" → Enter amount
  → handle_zarinpal_payment() [bot/handlers/payment.py:36]
    → _generate_payment_state() [bot.py:49] → CSRF state token
    → payment_create_zarinpal() [compat/legacy_facade.py:128]
      → PaymentService.initiate_payment(ZARINPAL, user_id, amount)
        → ZarinPalGateway.create_payment()
          → POST to ZarinPal API (request.json)
          → Returns (success, payment_url, authority)
    → Send payment URL to user
```

**Status:** ✅ Correct
**Issue:** State token generated but not appended to callback URL (see 2.2).

### 2.2 Callback (Verification)
```
User completes payment → ZarinPal redirects to /verify/<uid>/<amount>
  → verify_payment() [bot.py:60]
    → Check Status=OK
    → CSRF: _payment_states.pop(state, None) ← state='' (EMPTY!)
    → PaymentService.verify_and_credit(ZARINPAL, authority, uid, amt)
      → IDEMPOTENCY CHECK 1: SELECT 1 FROM transactions WHERE ref_id=authority
      → ZarinPalGateway.verify_payment(authority, amount)
      → IDEMPOTENCY CHECK 2 (in-txn): SELECT ... FOR UPDATE
      → Lock user row (SELECT ... FOR UPDATE)
      → UPDATE users SET balance = balance + amount
      → INSERT INTO transactions
```

**Status:** ⚠️ FAIL at CSRF layer. The state token is generated but never reaches the callback.

**Root cause:** In [`bot/handlers/payment.py:56-66`](bot/handlers/payment.py:56-66):
```python
state_token = _generate_payment_state(user_id, amount)
# ... creates payment ...
payment_url_with_state = payment_url  # ← STATE NOT APPENDED
```
The ZarinPal callback URL is set in `ZarinPalGateway.create_payment()` (line 80):
```python
"callback_url": f"{self.callback_base}?user_id={user_id}&amount={amount}"
#                                                          ^^ NO state= parameter
```
When ZarinPal redirects to `/verify/<uid>/<amount>`, the query parameters are `Authority` and `Status` from ZarinPal, but NO `state` parameter from our system.

```python
# bot.py:67
state = request.args.get('state', '')  # ALWAYS '' (empty string)
stored = _payment_states.pop(state, None)  # _payment_states.pop('', None) = None
if stored is None:
    return "Invalid or expired session"  # ← EVERY PAYMENT FAILS CSRF
```

### 2.3 Idempotency (Double Callback Protection)
```
verify_and_credit():
  1. Pre-txn: SELECT 1 FROM transactions WHERE ref_id = authority AND type='deposit'
     → If exists: Return success (already processed)
  2. Verify with ZarinPal
  3. In-txn: SELECT 1 FROM transactions WHERE ref_id = authority FOR UPDATE
     → If exists: Return success (race condition winner already processed)
  4. Lock user row, credit balance, insert transaction
```

**Status:** ✅ CORRECT — Belt-and-suspenders idempotency.

**Database support:** Partial unique index `uq_transactions_ref_id` WHERE ref_id IS NOT NULL (migration 002).

### 2.4 Race Condition Test
```
Scenario: Two identical callbacks arrive simultaneously
  Thread A: Pre-txn check → not found → ZarinPal verify → In-txn check → FOR UPDATE
  Thread B: Pre-txn check → not found → ZarinPal verify → In-txn check → FOR UPDATE (WAITS for A)

  Thread A: In-txn check → not found → Lock row → Credit balance → Insert txn → COMMIT
  Thread B: In-txn check → FOUND → Return success without double-crediting
```

**Status:** ✅ CORRECT — `FOR UPDATE` row locking + unique index prevents double-credit.

---

## 3. CARD-TO-CARD PAYMENT LIFECYCLE

### 3.1 Initiation
```
User: "Add Funds" → "Card Payment" → Enter amount
  → CardPayment.handle_new_payment() [card_payment.py:49]
    → Save payment request → Show card info → Wait for receipt
```

### 3.2 Receipt Upload
```
User sends photo → handle_receipt() [card_payment.py:102]
  → Save file_id to card_payments table
  → Forward to all admin_ids with Approve/Reject buttons
```

### 3.3 Admin Approval
```
Admin clicks "Approve" → verify_payment(action="approve") [card_payment.py:161]
  → Admin ID check
  → Payment status check (must be 'pending')
  → compat_add_balance(user_id, amount) → WalletService.deposit()
  → CardPaymentRepository.approve(payment_id, admin_id)
  → Notify user
```

**Status:** ✅ CORRECT (with qualification — uses compat layer instead of PaymentService directly)

### 3.4 Admin Rejection
```
Admin clicks "Reject" → process_rejection() [card_payment.py:233]
  → Admin ID check
  → Capture reason text
  → CardPaymentRepository.reject(payment_id, reason)
  → Notify user with reason
```

**Status:** ✅ CORRECT

### 3.5 Duplicate Approval Protection
```python
# card_payment.py:178-180
if status != 'pending':
    self.bot.answer_callback_query(call.id, "Invalid data")
    return
```

**Status:** ✅ CORRECT — Rejects non-pending payments.

### 3.6 Alternative Approval Path (PaymentService)
```python
# services/payment_service.py:356-421
PaymentService.approve_card_payment(payment_id, admin_id)
  → In-txn: Check status = 'approved' → idempotent skip
  → UPDATE card_payments SET status='approved'
  → Lock user row → Credit balance → Insert transaction
  → Insert audit_log
```

**Status:** ✅ CORRECT — More comprehensive than the card_payment.py path (includes audit logging). However, this method is NOT called from the bot handlers (they use card_payment.py directly).

---

## 4. REFUND LIFECYCLE

```
User cancels order → order_cancel() [compat/legacy_facade.py:111]
  → sms_cancel_number() → provider cancel
  → order_cancel() → OrderRepository.cancel_by_activation_id()
  → refund_balance() → WalletService.refund()
    → SELECT balance FOR UPDATE → UPDATE balance → INSERT transaction
```

**Status:** ✅ CORRECT — Atomic refund with row locking.

---

## 5. PAYMENT VERDICT

| Component | Status |
|-----------|--------|
| ZarinPal initiation | ✅ |
| ZarinPal callback | ❌ CSRF state broken |
| ZarinPal idempotency | ✅ Double-check + FOR UPDATE |
| ZarinPal race condition | ✅ Protected |
| Card-to-card flow | ✅ |
| Card duplicate approval | ✅ |
| Refund flow | ✅ Atomic with row lock |
| Duplicate callback test | ✅ Static analysis passes |
| Race condition test | ✅ Static analysis passes |

**Overall: PARTIALLY_CERTIFIED — 1 CRITICAL blocking issue (ZarinPal CSRF broken). Payment logic otherwise sound.**

---

*End of Phase H — Payment Report*
