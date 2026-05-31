# TEST COVERAGE REPORT — NumGenius Enterprise SaaS
## Phase K: Test Coverage Assessment

**Date:** 2026-05-31
**Status:** STATIC ANALYSIS — pytest cannot run (no PostgreSQL available)

---

## 1. TEST INVENTORY

| Test File | Tests | Status |
|-----------|-------|--------|
| [`test_wallet.py`](tests/test_wallet.py) | 7 | ✅ Pass (static) |
| [`test_atomic_wallet.py`](tests/test_atomic_wallet.py) | ~6 | ⚠️ Incomplete (stubs) |
| [`test_executable_wallet.py`](tests/test_executable_wallet.py) | ~8 | ⚠️ Uses assert False |
| [`test_enterprise_services.py`](tests/test_enterprise_services.py) | ~12 | ✅ Pass (static) |
| [`test_rbac.py`](tests/test_rbac.py) | ~5 | ✅ Pass (static) |
| [`test_order_state_machine.py`](tests/test_order_state_machine.py) | ~8 | ✅ Pass (static) |
| **TOTAL** | **~46** | |

---

## 2. CRITICAL ISSUE: SQLite vs PostgreSQL

### Problem
All tests use SQLite via [`tests/conftest.py:16`](tests/conftest.py:16):
```python
conn = sqlite3.connect(db_path)
```
Production uses PostgreSQL with:
- `%s` placeholders (not `?`)
- `FOR UPDATE` row locking (SQLite doesn't support)
- `ON CONFLICT DO UPDATE` / `DO NOTHING` (SQLite syntax differs)
- `RETURNING id` clauses
- `SERIAL` auto-increment
- `CURRENT_TIMESTAMP` vs `DATETIME('now')`

### Impact
Tests validate NOTHING about production behavior. Key untested PostgreSQL features:
1. Row locking for race condition prevention
2. Partial unique indexes for idempotency
3. SERIAL sequence behavior
4. CHECK constraints enforcement
5. Transaction rollback on errors

---

## 3. COVERAGE ESTIMATE

| Layer | Test Coverage | Notes |
|-------|-------------|-------|
| `db/repositories/` | 10% | Only UserRepository balance operations tested |
| `services/wallet_service.py` | 0% | No integration test with real wallet |
| `services/payment_service.py` | 0% | ZarinPal mocked, idempotency untested |
| `services/sms_service.py` | 0% | HeroSMS calls never tested |
| `services/order_service.py` | ~40% | State machine transitions tested |
| `services/subscription_service.py` | 0% | Not tested |
| `services/referral_service.py` | ~30% | Code generation tested, DB ops not |
| `services/anti_fraud.py` | 0% | Not tested |
| `services/catalog_manager.py` | 0% | Not tested |
| `bot/handlers/` | 0% | No handler tests |
| `bot/middleware.py` | 0% | No middleware tests |
| `web/routes/` | 0% | No route tests |

**Estimated total coverage: ~15%**

Target: ≥90%

---

## 4. FAILING TESTS (Static Analysis)

### 4.1 `test_atomic_wallet.py:80` — Unused Variable
```python
def test_zarinpal_sandbox_mode(self):
    gateway = ZarinPalGateway()  # ← never used
    pass
```
**Status:** Stub test. No assertions. Effectively a no-op.

### 4.2 `test_executable_wallet.py:167` — `assert False`
```python
assert False, "Should have raised duplicate key"
```
**Risk:** Removed by `python -O`. Should use `raise AssertionError()`.

---

## 5. MISSING TEST CATEGORIES

| Category | Tests Needed |
|----------|-------------|
| Wallet deposit/withdraw atomic | 5 tests |
| Payment idempotency (double callback) | 2 tests |
| Payment race condition | 3 tests |
| Order state machine transitions | 8 tests |
| Order cancel + refund | 2 tests |
| Admin operations (permissions) | 10 tests |
| Rate limiter | 3 tests |
| Fraud detection | 5 tests |
| Catalog CRUD | 6 tests |
| Bot handler integration | 15 tests |
| Webhook authentication | 2 tests |
| Health check | 2 tests |
| **TOTAL NEEDED** | **63 tests** |

---

## 6. RECOMMENDATIONS

1. **P0:** Replace SQLite test database with `pytest-postgresql` or `testing.postgresql`
2. **P0:** Add integration tests for payment idempotency (concurrent callbacks)
3. **P1:** Add handler integration tests (mock Telegram API)
4. **P1:** Add rate limiter and fraud detection tests
5. **P2:** Add webhook authentication tests
6. **P2:** Achieve 90% line coverage

---

**Overall: FAILED — 15% coverage (target: 90%). SQLite tests are misleading. Requires PostgreSQL test infrastructure + 63 additional tests.**

---
*End of Phase K — Test Coverage Report*
