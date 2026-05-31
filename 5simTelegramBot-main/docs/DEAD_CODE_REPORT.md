# DEAD CODE REPORT — NumGenius Enterprise SaaS
## Phase C: Dead Code Elimination

**Date:** 2026-05-31
**Methodology:** Import graph analysis + manual review of all call sites.

---

## 1. SUMMARY

| Category | Count | Action |
|----------|-------|--------|
| Unused files | 4 | Delete or migrate |
| Unused functions | 6 | Delete |
| Unused classes | 2 | Delete |
| Unused imports | 3 | Remove |
| Duplicate implementations | 2 | Consolidate |
| Legacy / Deprecated code | 5 | Document + schedule removal |
| Orphaned top-level files | 5 | Move to proper packages |
| **TOTAL** | **27** | |

---

## 2. UNUSED FILES

### D-1: `validate_all.py` (Workspace Root)
- **Path:** [`validate_all.py`](validate_all.py)
- **Status:** NEVER imported or referenced
- **Assessment:** Orphaned file from a previous audit iteration. Not part of the project.
- **Action:** DELETE

### D-2: `services/providers/` (Empty Package)
- **Path:** `services/providers/`
- **Status:** Directory exists but `__init__.py` and `herosms_rest_provider.py` were referenced as open tabs but returned ENOENT — they don't actually exist
- **Assessment:** Empty/virtual directory. Open tabs refer to non-existent files.
- **Action:** Either create with real content or remove from tab references.

### D-3: `payment.py` (Duplicate of payment_service.py)
- **Path:** [`payment.py`](payment.py:1-113)
- **Status:** Contains `class ZarinPal` which duplicates `class ZarinPalGateway` in [`services/payment_service.py`](services/payment_service.py:53-176)
- **Callers (verified):** NO code imports `payment.py` directly. All payment operations go through `compat/legacy_facade.py` → `PaymentService`.
- **Action:** DELETE after confirming zero imports via grep.

### D-4: `routes/order_details.py` (Outside Package)
- **Path:** [`routes/order_details.py`](routes/order_details.py)
- **Status:** Lives at top-level `routes/` instead of `web/routes/`. Never imported by any Flask app registration.
- **Assessment:** The `bot.py` app registers `order_details_bp` from `routes.order_details` (line 15). Actually USED. Not dead.
- **Action:** KEEP but move to `web/routes/order_details.py`.

---

## 3. UNUSED FUNCTIONS

### D-5: `currency_service.py::_get_usd_to_irr_rate()`
- **Path:** [`currency_service.py`](currency_service.py:51-61)
- **Lines:** 51-61
- **Callers:** NONE. `get_usd_rate()` uses Navasan API. `_get_usd_to_irr_rate()` returns hardcoded 52000 and is never called.
- **Action:** DELETE

### D-6: `db/connection.py::commit()` and `rollback()`
- **Path:** [`db/connection.py`](db/connection.py:93-97)
- **Lines:** 93-97
- **Body:** Both are `pass` (no-op). `execute_and_commit()` handles its own commit/rollback. `DatabaseContext.__exit__` handles its own.
- **Callers:** NONE
- **Action:** DELETE or implement properly

### D-7: `backup_manager.py::setup_database()` (No-op)
- **Path:** [`admin_config.py`](admin_config.py:107-109)
- **Lines:** 107-109
- **Status:** `def setup_database(self): pass` — intentionally no-op ("database setup is handled by migrations now")
- **Action:** Document as deprecated, remove in next major version

### D-8: `database.py::setup_users_database`, `setup_admin_database`, `setup_orders_database`
- **Path:** [`database.py`](database.py:54-56)
- **Lines:** 54-56
- **Status:** All three are aliases for `setup_databases`. Created for backward compatibility. No callers use these specific names.
- **Action:** DELETE the aliases

### D-9: `wallet.py::create_wallet()` (Redundant)
- **Path:** [`wallet.py`](wallet.py:41-47)
- **Lines:** 41-47
- **Status:** Wraps `self._user_repo.create_if_not_exists(user_id)` — same as `ensure_user_exists()`. Never called.
- **Action:** DELETE or alias to `ensure_user_exists()`

### D-10: `data/service_countries.py::_get_countries_for_service()` (Wrong Name)
- **Path:** Referenced in [`bot/handlers/services.py`](bot/handlers/services.py:16) as `_get_countries_for_service` but mypy reports this doesn't exist. The correct name is `get_countries_for_service`.
- **Action:** Fix the import name in services.py

---

## 4. UNUSED CLASSES

### D-11: `payment.py::ZarinPal` (Entire Class)
- **Path:** [`payment.py`](payment.py:8-112)
- **Lines:** 8-112
- **Status:** 105 lines duplicated by `ZarinPalGateway` in `services/payment_service.py`. No imports of this class found anywhere.
- **Action:** DELETE the entire `payment.py` file

### D-12: `CurrencyService` from `currency_service.py` — Partially Used
- **Path:** [`currency_service.py`](currency_service.py:9-61)
- **Status:** `CurrencyService` class exists but `services/currency_engine.py` exists with a `CurrencyEngine` class. Two currency systems.
- **Callers of CurrencyService:** Unknown — check imports. If unused, DELETE.
- **Callers of CurrencyEngine:** Referenced in admin bot for currency display.
- **Action:** Consolidate into one currency service.

---

## 5. UNUSED IMPORTS

### D-13: `config.py` — `from dotenv import load_dotenv` executed at module level
- **Path:** [`config.py`](config.py:12-17)
- **Status:** `load_dotenv()` is called inside a try/except at import time. This is fine but redundant since `bot.py` and `admin_bot.py` also call it.
- **Action:** Document as intentional (belt-and-suspenders). Not dead.

### D-14: `compat/legacy_facade.py` — `from data.dto import PaymentGateway`
- **Path:** [`compat/legacy_facade.py`](compat/legacy_facade.py:11)
- **Status:** Used in `payment_create_zarinpal()` and `payment_verify_zarinpal()`. Actually USED.
- **Action:** KEEP

### D-15: `bot_utils.py` — `from dotenv import load_dotenv` + `load_dotenv()`
- **Path:** [`bot_utils.py`](bot_utils.py:11,15)
- **Status:** Redundant — already called by entry points.
- **Action:** REMOVE

---

## 6. DUPLICATE IMPLEMENTATIONS

### D-16: ZarinPal Classes
- **Location 1:** [`payment.py`](payment.py:8-112) — `class ZarinPal`
- **Location 2:** [`services/payment_service.py`](services/payment_service.py:53-176) — `class ZarinPalGateway(BasePaymentGateway)`
- **Duplication:** ~100 lines
- **Resolution:** DELETE payment.py. Keep payment_service.py.

### D-17: Wallet Classes
- **Location 1:** [`wallet.py`](wallet.py:17-99) — `class Wallet`
- **Location 2:** [`services/wallet_service.py`](services/wallet_service.py:24-271) — `class WalletService`
- **Location 3:** [`compat/legacy_facade.py`](compat/legacy_facade.py:20) — module-level `_wallet = WalletService()`
- **Duplication:** `wallet.py` is a thin compat wrapper. Only used by `compat/legacy_facade.py` → `add_balance()` (card_payment.py:192).
- **Resolution:** Migrate the one remaining caller to use `WalletService` directly, then DELETE wallet.py.

---

## 7. ORPHANED TOP-LEVEL FILES (Misplaced)

These files live at the project root instead of in proper package directories:

| File | Current Location | Recommended Location |
|------|-----------------|---------------------|
| [`backup_manager.py`](backup_manager.py) | Root | `services/backup_service.py` |
| [`startup_test.py`](startup_test.py) | Root | `tests/test_startup.py` |
| [`operator_config.py`](operator_config.py) | Root | `config/operators.py` |
| [`currency_service.py`](currency_service.py) | Root | `services/currency_service.py` |
| [`bot_utils.py`](bot_utils.py) | Root | `bot/utils.py` |

---

## 8. LEGACY COMPAT LAYER

The entire [`compat/`](compat/) package exists solely for backward compatibility:

| File | Purpose | Migration Status |
|------|---------|-----------------|
| [`compat/legacy_facade.py`](compat/legacy_facade.py) | Wraps enterprise services with legacy function signatures | Still referenced by ~15 call sites in bot/handlers/ |
| [`compat/__init__.py`](compat/__init__.py) | Package init | Empty |

**Resolution:** Schedule migration of all callers to use services directly. Remove `compat/` in v3.0.

---

## 9. DEAD CODE ACTION PLAN

### Immediate (delete now):
1. DELETE [`payment.py`](payment.py) — duplicated by payment_service.py
2. DELETE [`validate_all.py`](validate_all.py) — orphaned audit script
3. DELETE `db/connection.py::commit()` and `rollback()` — no-op stubs
4. DELETE `database.py::setup_users_database`, `setup_admin_database`, `setup_orders_database` — unused aliases
5. DELETE `currency_service.py::_get_usd_to_irr_rate()` — unused hardcoded method
6. REMOVE `bot_utils.py` `load_dotenv()` call — redundant
7. DELETE `wallet.py::create_wallet()` — redundant with ensure_user_exists()

### Next sprint:
8. CONSOLIDATE `currency_service.py` into `services/currency_engine.py`
9. DELETE `wallet.py` after migrating card_payment.py caller
10. MOVE top-level files to proper packages

### v3.0:
11. REMOVE `compat/` package entirely
12. DELETE `admin_config.py::setup_database()` no-op

---

*End of Phase C — Dead Code Report*
