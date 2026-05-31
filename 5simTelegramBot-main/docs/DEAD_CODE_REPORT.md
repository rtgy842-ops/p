# DEAD CODE REPORT — NumGenius Enterprise SaaS
## Phase C: Dead Code Elimination

**Date:** 2026-05-31

---

## EXECUTIVE SUMMARY

| Category | Count |
|----------|-------|
| Dead/unused files | 8 |
| Dead functions/methods | 5 |
| Dead imports (ruff: F401) | 24 |
| Unused local variables (ruff: F841) | 3 |
| Duplicate implementations | 3 |
| Legacy code to remove | 4 |

---

## DEAD FILES — Recommended Removal

### DF1 — `bot/handlers/menu.py` — No-op stub file
**Path:** [`bot/handlers/menu.py`](5simTelegramBot-main/bot/handlers/menu.py)  
**Status:** Dead — docstring states *"This file exists only for backward compatibility"*  
**Content:** Only stores `_bot` global in `init()`. No handlers registered. All menu functionality lives in `purchase.py`.  
**Action:** **REMOVE** — delete file and remove `from bot.handlers import menu` and `menu.init(bot)` from [`bot.py`](5simTelegramBot-main/bot.py:27-28).

---

### DF2 — `bot_utils.py` — Legacy send_message function
**Path:** [`bot_utils.py`](5simTelegramBot-main/bot_utils.py)  
**Status:** Dead — provides `send_message_to_bot()` using raw Telegram HTTP API. No caller exists. `bot/client.py` (`TelegramClient`) is the canonical message sender. Ruff confirms `import bot_utils` in `bot.py:5` but its functions are never called.  
**Action:** **REMOVE** — delete file and remove `import bot_utils` from `bot.py:5`.

---

### DF3 — `payment.py` — Legacy ZarinPal (duplicated in PaymentService)
**Path:** [`payment.py`](5simTelegramBot-main/payment.py)  
**Status:** Dead — `ZarinPal` class duplicated in `services/payment_service.py:ZarinPalGateway`. The `compat/legacy_facade.py` routes all payment operations through `PaymentService`, not this file. No import of `payment.py` exists in any active code path.  
**Action:** **REMOVE** or **DEPRECATE** — mark with `@deprecated` and `raise DeprecationWarning` on import.

---

### DF4 — `currency_service.py` — Legacy currency (duplicated by CurrencyEngine)
**Path:** [`currency_service.py`](5simTelegramBot-main/currency_service.py)  
**Status:** Dead — `CurrencyService` duplicated by `services/currency_engine.py:CurrencyEngine`. The legacy version has a hardcoded `52000` fallback rate. No caller exists in active code paths (bot.py doesn't import it; i18n.py doesn't use it).  
**Action:** **REMOVE** — the `CurrencyEngine` in `services/currency_engine.py` is the canonical implementation.

---

### DF5 — `wallet.py` — Legacy Wallet (duplicated by WalletService)
**Path:** [`wallet.py`](5simTelegramBot-main/wallet.py)  
**Status:** Dead — `Wallet` class duplicated by `services/wallet_service.py:WalletService`. The legacy version uses `UserRepository` directly without atomic `FOR UPDATE` locking. No active caller exists — `compat/legacy_facade.py` uses `WalletService`, not `Wallet`.  
**Action:** **REMOVE** — all callers have been migrated to `WalletService`.

---

### DF6 — `bot/handlers/help.py` — Duplicate handler registration
**Path:** [`bot/handlers/help.py`](5simTelegramBot-main/bot/handlers/help.py)  
**Status:** Dead — registers `help`, `help_buy_number`, `help_charge`, etc. via `bot.callback_query_handler()`. These same callbacks are ALSO registered in `bot/handlers/purchase.py:157-204` via `router.callback()`. After the router fix (exact-match first), the router-based handlers take precedence.  
**Action:** **REMOVE** the `register_help_handlers` function and its call from `bot.py:27` (which doesn't even import `help` module — it imports `services`, not `help`). Wait — `bot.py` doesn't import `help.py` at all, so it's **already dead**. Delete the file.

---

### DF7 — `bot/handlers/admin/` directory (5 unused files)
**Paths:**
- [`bot/handlers/admin/broadcast.py`](5simTelegramBot-main/bot/handlers/admin/broadcast.py)
- [`bot/handlers/admin/channels.py`](5simTelegramBot-main/bot/handlers/admin/channels.py)
- [`bot/handlers/admin/operators.py`](5simTelegramBot-main/bot/handlers/admin/operators.py)
- [`bot/handlers/admin/settings.py`](5simTelegramBot-main/bot/handlers/admin/settings.py)
- [`bot/handlers/admin/transactions.py`](5simTelegramBot-main/bot/handlers/admin/transactions.py)

**Status:** Dead — These files exist but are never imported by `admin_bot.py` or `bot/handlers/admin_bot.py`. Only `dashboard.py` and `users.py` from `admin/` are in active use. All admin functionality has been consolidated in `bot/handlers/admin_bot.py` (the standalone admin bot handler).  
**Action:** **REMOVE** — these are legacy modular admin handlers that were superseded by the monolithic `admin_bot.py` handler.

---

### DF8 — `services/api_key_service.py` — In-memory only, unused
**Path:** [`services/api_key_service.py`](5simTelegramBot-main/services/api_key_service.py)  
**Status:** Dead — `APIKeyService` stores keys in a Python dict (no persistence). No code in the project calls `api_keys.create_key()`, `validate_key()`, or `revoke_key()`.  
**Action:** **KEEP AS PLACEHOLDER** — document as "planned feature, not yet wired in" or remove and re-add when implemented with DB persistence.

---

## DEAD FUNCTIONS / METHODS

### DFUNC1 — `currency_service.py:_get_usd_to_irr_rate()`
**File:** [`currency_service.py:49-58`](5simTelegramBot-main/currency_service.py:49)  
**Status:** Dead — returns hardcoded `52000`. Never called internally or externally.  
**Action:** Removed with file DF4.

### DFUNC2 — `wallet_ledger.py:WALLET_LEDGER_DDL` constant
**File:** [`services/wallet_ledger.py:149-164`](5simTelegramBot-main/services/wallet_ledger.py:149)  
**Status:** Dead — DDL string defined but never used. Table is created via `db/schema.py` or Alembic.  
**Action:** Remove the `WALLET_LEDGER_DDL` constant.

### DFUNC3 — `OrderService.mark_waiting_sms()` dead code block
**File:** [`services/order_service.py:130-132`](5simTelegramBot-main/services/order_service.py:130)  
**Status:** Dead — sets `order.status = OrderStatus.CREATED` when it's already CREATED, then tries a transition not in `STATE_TRANSITIONS` map. Will raise ValueError.  
**Action:** Remove lines 130-132.

### DFUNC4 — `bot/handlers/purchase.py:_show_help_answer()` — duplicated in `help.py`
**File:** [`bot/handlers/purchase.py:199-204`](5simTelegramBot-main/bot/handlers/purchase.py:199)  
**Status:** Works but duplicated — same logic in dead `help.py`. After removing `help.py`, this becomes the sole implementation.  
**Action:** Keep — it's the active one.

### DFUNC5 — `admin_config.py:setup_database()` — no-op stub
**File:** [`admin_config.py:106-108`](5simTelegramBot-main/admin_config.py:106)  
**Status:** Dead — method body is `pass`. Docstring says "No-op: database setup is handled by migrations."  
**Action:** Remove method or mark with `@deprecated`.

---

## DEAD IMPORTS (Ruff F401 — 24 instances)

### Files with unused imports after auto-fix:
| File | Unused Import |
|------|---------------|
| `admin_bot.py:5` | `from flask import request` |
| `bot.py:5` | `time`, `json`, `threading` |
| `bot.py:10` | `get_text`, `get_user_language`, `set_user_language`, `get_all_languages` |
| `bot.py:8` | `telebot.types` |
| `alembic/env.py:35` | `db.schema.ALL_TABLES` |
| `alembic/versions/001_initial_schema.py:11` | `sqlalchemy` |
| `backup_manager.py:13` | `datetime.datetime` |
| `db/migrations.py` | `ALL_TABLES`, `DEFAULT_SETTINGS` (after refactor) |
| `tests/conftest.py` | (previously had unused) |
| `tests/test_atomic_wallet.py:11-18` | `threading`, `time`, `MagicMock`, `WalletLedger`, `PaymentGateway`, `PaymentResultDTO` |
| `tests/test_enterprise_services.py:7,304` | `pytest`, `ast` |
| `tests/test_executable_wallet.py:154-155` | `PaymentService`, `PaymentGateway` |
| `tests/test_order_state_machine.py:8` | `pytest` |
| `tests/test_wallet.py:8-12` | `pytest`, `sqlite3`, `TransactionRepository`, `db_context` |
| `web/routes/admin_api.py:8` | `os` |
| `web/routes/admin_panel.py:137` | `psycopg2` |

**Action:** Remove all unused imports. Ruff `--fix` handles most; manual removal for remaining.

---

## UNUSED LOCAL VARIABLES (Ruff F841)

| File | Variable | Line |
|------|----------|------|
| `tasks/__init__.py` | `repo` | 147 |
| `tests/test_atomic_wallet.py` | `gateway` | 83 |
| `tests/test_enterprise_services.py` | (after import fix) | — |

**Action:** Remove unused variable assignments.

---

## DUPLICATE IMPLEMENTATIONS

### DUP1 — ZarinPal payment (×2)
- **Active:** [`services/payment_service.py:51-174`](5simTelegramBot-main/services/payment_service.py:51) — `ZarinPalGateway`
- **Dead:** [`payment.py:5-109`](5simTelegramBot-main/payment.py:5) — `ZarinPal` (file DF3)
- **Resolution:** Remove `payment.py`

### DUP2 — Wallet operations (×2)
- **Active:** [`services/wallet_service.py`](5simTelegramBot-main/services/wallet_service.py) — `WalletService` with `SELECT FOR UPDATE`
- **Dead:** [`wallet.py`](5simTelegramBot-main/wallet.py) — `Wallet` without row locking
- **Resolution:** Remove `wallet.py` (file DF5)

### DUP3 — Help menu handlers (×2)
- **Active:** [`bot/handlers/purchase.py:157-204`](5simTelegramBot-main/bot/handlers/purchase.py:157) — router-based
- **Dead:** [`bot/handlers/help.py:17-67`](5simTelegramBot-main/bot/handlers/help.py:17) — direct bot registration
- **Resolution:** Remove `help.py` (file DF6)

---

## LEGACY CODE TO REMOVE

### LG1 — `db/migrations.py` — Custom migration system
**File:** [`db/migrations.py`](5simTelegramBot-main/db/migrations.py)  
**Status:** Legacy — duplicates Alembic's functionality. The project has BOTH `db/migrations.py` (custom) AND Alembic migrations (standard).  
**Recommendation:** After verifying Alembic handles all schema creation, remove `db/migrations.py` and update `bot.py:67`, `admin_bot.py:44` to use `alembic upgrade head` instead of `MigrationManager().migrate()`.

### LG2 — `admin_config.py` — Legacy admin config
**File:** [`admin_config.py`](5simTelegramBot-main/admin_config.py)  
**Status:** Partially legacy — delegates to `SettingsRepository` but maintains backward-compat API. Most functionality duplicated in `AdminService`.  
**Recommendation:** Migrate remaining callers to `AdminService` and remove.

### LG3 — `operator_config.py` — Legacy operator config
**File:** [`operator_config.py`](5simTelegramBot-main/operator_config.py)  
**Status:** Partially legacy — delegates to `SettingsRepository` but provides `OperatorConfig` wrapper that duplicates `AdminService` operator methods.  
**Recommendation:** Migrate callers and remove.

### LG4 — `database.py` — Legacy database init
**File:** [`database.py`](5simTelegramBot-main/database.py)  
**Status:** Active but redundant — `setup_databases()` runs DDL via `db/schema.py`. Equivalent to running Alembic migrations. The function aliases `setup_users_database = setup_admin_database = setup_orders_database = setup_databases` are misleading (they all call the same function).  
**Recommendation:** Consolidate to Alembic-only schema management. Remove the aliases.

---

## ACTION PLAN

| Priority | Item | Action |
|----------|------|--------|
| 1 | DF1 — `menu.py` | Delete file + update bot.py import |
| 2 | DF2 — `bot_utils.py` | Delete file + update bot.py import |
| 3 | DF3 — `payment.py` | Delete file |
| 4 | DF4 — `currency_service.py` | Delete file |
| 5 | DF5 — `wallet.py` | Delete file |
| 6 | DF6 — `help.py` | Delete file |
| 7 | DF7 — 5 admin handler files | Delete files |
| 8 | DFUNC2 — WALLET_LEDGER_DDL | Remove constant |
| 9 | DFUNC3 — mark_waiting_sms dead block | Remove lines 130-132 |
| 10 | F401 — 24 unused imports | Remove imports |
| 11 | LG1 — `db/migrations.py` | Schedule for removal after Alembic verification |
| 12 | LG2-LG4 — Legacy config files | Migrate and remove |

**Total files to delete:** 10  
**Lines of dead code to remove:** ~800  
**Duplicate implementations resolved:** 3
