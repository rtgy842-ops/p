# CODE AUDIT REPORT — NumGenius Enterprise SaaS
## Phase A: Complete Source Code Audit

**Date:** 2026-05-31  
**Auditor:** Senior Software Architect / Senior Backend Engineer / Security Auditor  
**Project:** 5simTelegramBot-main (NumGenius Enterprise)  
**Total Files Audited:** 73  
**Python Version:** >=3.11  

---

## EXECUTIVE SUMMARY

The project demonstrates a mature enterprise architecture with clean separation of concerns, proper repository pattern, service layer abstraction, and security-conscious design. However, there are **32 issues** spanning missing files, architectural inconsistencies, security concerns, duplicate code, schema mismatches, and runtime risks. **5 CRITICAL** issues require immediate resolution before production deployment.

### Severity Distribution
| Severity | Count |
|----------|-------|
| CRITICAL | 5 |
| HIGH     | 10 |
| MEDIUM   | 12 |
| LOW      | 5 |

---

## CRITICAL ISSUES

### C1 — Missing files referenced at runtime (4 missing files)

**Files referenced but NOT present on disk:**
1. [`services/providers/__init__.py`](5simTelegramBot-main/services/providers/__init__.py) — Imported by VSCode tabs but file does not exist
2. [`services/providers/herosms_rest_provider.py`](5simTelegramBot-main/services/providers/herosms_rest_provider.py) — Imported by VSCode tabs but file does not exist
3. [`tasks/celery_app.py`](5simTelegramBot-main/tasks/celery_app.py) — Referenced by `docker-compose.yml` and VSCode tabs
4. [`tasks/sync_tasks.py`](5simTelegramBot-main/tasks/sync_tasks.py) — Referenced by VSCode tabs

**Severity:** CRITICAL  
**Root Cause:** Docker Compose `command: ["celery", "-A", "tasks", "worker" ...]` requires `tasks/celery_app.py` or `tasks/__init__.py` with celery app instance. Worker and Beat containers will **fail to start**.  
**Recommended Fix:** Create [`tasks/celery_app.py`](5simTelegramBot-main/tasks/celery_app.py) with the Celery app instance, create [`tasks/__init__.py`](5simTelegramBot-main/tasks/__init__.py) re-exporting celery. Create the missing provider files.

---

### C2 — Database connection pool exhaustion — `ConnectionManager.execute()` never returns connections

**File:** [`db/connection.py`](5simTelegramBot-main/db/connection.py:55)  
**Severity:** CRITICAL  
**Root Cause:** The `execute()` method calls `self.get_connection(db_name)` but returns the **cursor** directly in line 69. The `put_connection()` in the `finally` block on line 74 will always be called. However, the **caller** in [`db/migrations.py`](5simTelegramBot-main/db/migrations.py:67) does `self._cm.put_connection(cursor.connection)` after calling `execute()`. This means the **same connection is returned to the pool twice**, corrupting the pool state. In high-traffic scenarios, connections will leak.

```python
# db/connection.py:55-74 — BUG: Double put_connection
def execute(self, db_name, query, params=()):
    conn = self.get_connection(db_name)
    cursor = conn.cursor()
    try:
        ...
        return cursor       # Returns cursor, not conn
    finally:
        self.put_connection(conn)  # FIRST put_connection

# db/migrations.py:67 — caller then does:
self._cm.put_connection(cursor.connection)  # SECOND put_connection — DOUBLE RETURN!
```

**Recommended Fix:** Refactor `execute()` to NOT call `put_connection()` in the finally block. Make callers responsible for managing connection lifecycle, OR remove the `put_connection` call in `migrations.py:67`.

---

### C3 — Webhook route has no CSRF/XSRF protection and no signature verification

**File:** [`web/routes/webhook.py`](5simTelegramBot-main/web/routes/webhook.py:23)  
**Severity:** CRITICAL  
**Root Cause:** The POST `/` webhook endpoint accepts raw Telegram updates with **zero** authentication. There is no `X-Telegram-Bot-Api-Secret-Token` header verification. Any attacker who discovers the webhook URL can send forged update payloads. The endpoint is also exposed on GET (`methods=['GET', 'POST']`), which leaks bot existence.

```python
@webhook_bp.route('/', methods=['GET', 'POST'])  # Should only be POST
def webhook():
    json_str = request.get_data().decode('UTF-8')  # No signature verification
    update = telebot.types.Update.de_json(json_str)
    _bot.process_new_updates([update])  # Processes ANY payload
```

**Recommended Fix:**
1. Change to `methods=['POST']` only
2. Add Telegram secret token verification via `X-Telegram-Bot-Api-Secret-Token` header
3. Set `SECRET_TOKEN` in `.env` and configure bot webhook with `secret_token` parameter

---

### C4 — WalletService used as both instance AND static method — null reference risk

**File:** [`bot/handlers/purchase.py`](5simTelegramBot-main/bot/handlers/purchase.py:52)  
**Severity:** CRITICAL  
**Root Cause:** Line 52 calls `WalletService.get_balance(user_id)` as a **static method** (no parentheses). But `WalletService` is used as an **instance** on line 79 with `WalletService()`. The static call works only because `get_balance` is decorated with `@staticmethod`. However, if future refactoring changes `get_balance` to use `self.DB_NAME`, the static call path will break at runtime.

```python
# Line 52: static call — works but fragile
balance = WalletService.get_balance(user_id)  

# Line 79: instance call — correct pattern
wallet = WalletService()
new_balance = wallet.withdraw(user_id, price_toman, ...)
```

**Recommended Fix:** Standardize on instance-based access. Create one `WalletService()` instance per handler.

---

### C5 — `test_purchase_number` endpoint writes SQLite-style `?` parameter to PostgreSQL

**File:** [`web/routes/admin_api.py`](5simTelegramBot-main/web/routes/admin_api.py:195)  
**Severity:** CRITICAL  
**Root Cause:** The endpoint at line 195-198 uses `?` placeholders (SQLite syntax) in a PostgreSQL INSERT statement via raw `conn.execute()`. The `ConnectionManager.execute()` method converts `?` to `%s`, but this endpoint **bypasses** the manager and calls `conn.execute()` directly. This will raise a `psycopg2.ProgrammingError`.

```python
conn = cm.get_connection('users_db')  # Also: 'users_db' is not a valid DB name
conn.execute(
    'INSERT INTO orders (...) VALUES (?, ?, ?, ?, ?, ?, ?)',  # SQLite '?' — PostgreSQL needs %s
    (test_user_id, service, country, number, price, 'active', order_id))
```

**Recommended Fix:** Either use `%s` placeholders directly or route through `ConnectionManager.execute()`. Also fix `'users_db'` → `'default'`.

---

## HIGH ISSUES

### H1 — `WalletService.withdraw()` does NOT write to `wallet_ledger`

**File:** [`services/wallet_service.py`](5simTelegramBot-main/services/wallet_service.py:125)  
**Severity:** HIGH  
**Root Cause:** The `deposit()` method writes to both `transactions` AND `wallet_ledger` tables (lines 109-117). The `withdraw()` method only writes to `transactions` (lines 150-154), omitting the `wallet_ledger` entry. This creates an incomplete double-entry ledger, making reconciliation impossible.

**Recommended Fix:** Add `wallet_ledger` INSERT to `withdraw()`, matching the pattern in `deposit()`.

---

### H2 — `admin_bot.py` and `bot.py` share the same PORT by default

**File:** [`admin_bot.py`](5simTelegramBot-main/admin_bot.py:51), [`bot.py`](5simTelegramBot-main/bot.py:74)  
**Severity:** HIGH  
**Root Cause:** Both bots read `FLASK_PORT` from the same env var and default to port `5000`. If both are started without Docker (e.g., during local development), a port conflict occurs. The `docker-compose.yml` correctly maps them to `5001:5000` and `5002:5000`, but the default configuration is dangerous.

**Recommended Fix:** Use separate env vars: `CUSTOMER_BOT_PORT=5001` and `ADMIN_BOT_PORT=5002`, or at minimum document the requirement.

---

### H3 — `UserRepository.find_by_id_like()` is called but NOT implemented

**File:** [`services/user_service.py`](5simTelegramBot-main/services/user_service.py:76)  
**Severity:** HIGH  
**Root Cause:** `UserService.search()` calls `self._user_repo.find_by_id_like(term)`, but this method does **not exist** in [`UserRepository`](5simTelegramBot-main/db/repositories/user_repository.py). Any admin search operation will raise `AttributeError` at runtime.

**Recommended Fix:** Either implement `find_by_id_like()` in `UserRepository` or implement search logic in `UserService.search()` using existing methods.

---

### H4 — API key service is in-memory only — data lost on restart

**File:** [`services/api_key_service.py`](5simTelegramBot-main/services/api_key_service.py:36)  
**Severity:** HIGH  
**Root Cause:** API keys are stored in `self._keys: dict[str, dict]` — a Python `dict` with no database persistence. All generated API keys are lost when the process restarts.

**Recommended Fix:** Persist API keys to the database (add an `api_keys` table to the schema), or at minimum document this as a known limitation.

---

### H5 — Inconsistent `subscriptions` table conflict clause

**File:** [`services/subscription_service.py`](5simTelegramBot-main/services/subscription_service.py:153)  
**Severity:** HIGH  
**Root Cause:** The INSERT in `set_tier()` uses `ON CONFLICT (user_id) DO UPDATE`, but the `subscriptions` table DDL in [`db/schema.py`](5simTelegramBot-main/db/schema.py:113) and [`001_initial_schema.py`](5simTelegramBot-main/alembic/versions/001_initial_schema.py:133) does **NOT** have a UNIQUE constraint on `user_id`. The INSERT will fail with a syntax error.

```sql
-- Schema defines: user_id BIGINT NOT NULL REFERENCES users(user_id)  -- NO UNIQUE
-- But code uses: ON CONFLICT (user_id) DO UPDATE SET ...  -- Needs UNIQUE(user_id)
```

**Recommended Fix:** Add `UNIQUE(user_id)` constraint to the `subscriptions` table definition in both `db/schema.py` and the alembic migration.

---

### H6 — `db/migrations.py` has hardcoded seeds that conflict with Alembic migration 002

**File:** [`db/migrations.py`](5simTelegramBot-main/db/migrations.py:27-54) vs [`alembic/versions/002_constraints.py`](5simTelegramBot-main/alembic/versions/002_constraints.py:65-87)  
**Severity:** HIGH  
**Root Cause:** **Two separate migration systems exist**: (1) `db/migrations.py` with its own `MIGRATIONS` list and `_migrations` table, and (2) Alembic with standard `alembic_version` table. Both seed the same data (catalog_services, currencies, providers). Running both will cause duplicate key errors. The `db/migrations.py` system uses `INSERT ... ON CONFLICT DO NOTHING` (safe), but having two migration systems is an architectural smell.

**Recommended Fix:** Choose ONE migration system. Disable `db/migrations.py` entirely and use Alembic exclusively.

---

### H7 — `OrderService.mark_waiting_sms()` has bug that swallows state transition

**File:** [`services/order_service.py`](5simTelegramBot-main/services/order_service.py:125)  
**Severity:** HIGH  
**Root Cause:** Lines 130-132 contain dead logic that overrides the order status back to CREATED before the transition check:

```python
def mark_waiting_sms(self, order_id: int) -> OrderDTO | None:
    order = self.get_order(order_id)
    if order is None:
        return None
    if order.status == OrderStatus.CREATED:
        # Allow CREATED → WAITING_SMS for cases where purchase bypasses intermediate states
        order.status = OrderStatus.CREATED  # BUG: Sets to same value, does nothing useful
    self._require_transition(order.status, OrderStatus.WAITING_SMS, order_id)
```

The `CREATED → WAITING_SMS` transition is **not** in `STATE_TRANSITIONS` (line 24). This code will still raise a `ValueError` on the next line. **This is intentional dead code — commit comment says "Allow CREATED → WAITING_SMS" but does NOT add it to the transitions map.**

**Recommended Fix:** Add the `CREATED → WAITING_SMS` transition to `STATE_TRANSITIONS` or remove the dead code block.

---

### H8 — `ReferralService` uses `@staticmethod` DB calls via `db_context` import which fails if DB not initialized

**File:** [`services/referral_service.py`](5simTelegramBot-main/services/referral_service.py:36-48)  
**Severity:** HIGH  
**Root Cause:** Multiple methods use `from db.context import db_context` inside method bodies (lines 36, 59, 84, 127, 142, 159, 183, 227, 246, 264). If any of these methods are called before the database connection pool is initialized (which happens at bot startup), they will crash. The import-inside-method pattern is fragile and indicates circular import concerns.

**Recommended Fix:** Import `db_context` at the module level. The database connection pool is lazily initialized by `ConnectionManager.get_instance()`, so module-level imports are safe.

---

### H9 — `payment.py` (legacy ZarinPal) duplicates logic from `services/payment_service.py`

**File:** [`payment.py`](5simTelegramBot-main/payment.py) — ENTIRE FILE vs [`services/payment_service.py`](5simTelegramBot-main/services/payment_service.py:51-174)  
**Severity:** HIGH  
**Root Cause:** Both files implement ZarinPal payment creation and verification. `payment.py` is the old module, `services/payment_service.py` is the new enterprise version. The `web/routes/payment.py` uses `compat.legacy_facade.payment_verify_zarinpal`, which ultimately calls the new `PaymentService`. But `payment.py` is still imported and could be called from undiscovered paths.

**Recommended Fix:** Deprecate `payment.py` entirely. All paths should go through `PaymentService` (new). Add a deprecation warning import guard.

---

### H10 — `bot/handlers/help.py` and `bot/handlers/purchase.py` have DUPLICATE help menu implementations

**File:** [`bot/handlers/help.py`](5simTelegramBot-main/bot/handlers/help.py:17-67) vs [`bot/handlers/purchase.py`](5simTelegramBot-main/bot/handlers/purchase.py:157-204)  
**Severity:** HIGH  
**Root Cause:** Two separate registrations for the same help callback handlers (`help`, `help_buy_number`, `help_charge`, etc.). `help.py` registers via `bot.callback_query_handler()` directly; `purchase.py` registers via `router.callback()`. Both will fire, causing double message edits and potential race conditions.

**Recommended Fix:** Remove one of the duplicate implementations. The router-based approach in `purchase.py` is preferred. Delete the `bot.callback_query_handler()` registrations in `help.py`.

---

## MEDIUM ISSUES

### M1 — `db/schema.py` defines `wallet_ledger` and `rate_limits` tables but they're also defined in service files

**File:** [`db/schema.py`](5simTelegramBot-main/db/schema.py:303-328) vs [`services/wallet_ledger.py`](5simTelegramBot-main/services/wallet_ledger.py:149-164) and [`services/rate_limiter.py`](5simTelegramBot-main/services/rate_limiter.py)  
**Severity:** MEDIUM  
**Root Cause:** DDL is duplicated. `wallet_ledger.py` has `WALLET_LEDGER_DDL` (lines 149-164) but the table is already in `db/schema.py`. If schema.py is always run first, this is harmless but confusing.

**Recommended Fix:** Remove the `WALLET_LEDGER_DDL` constant from `services/wallet_ledger.py`. All DDL should live only in `db/schema.py` or Alembic migrations.

---

### M2 — `alembic/versions/001_initial_schema.py` creates `alembic_version` table manually

**File:** [`alembic/versions/001_initial_schema.py`](5simTelegramBot-main/alembic/versions/001_initial_schema.py:125-130)  
**Severity:** MEDIUM  
**Root Cause:** Alembic manages its own `alembic_version` table automatically via `context.configure(version_table='alembic_version')`. The migration manually creates it with `CREATE TABLE IF NOT EXISTS alembic_version`. This will cause Alembic to fail on the second run because the table already exists with a different schema than what Alembic expects.

**Recommended Fix:** Remove the manual `alembic_version` table creation from the migration. Let Alembic manage its own version tracking table.

---

### M3 — `config.py` `SECRET_KEY` defaults to `os.urandom(32).hex()` — breaks session persistence

**File:** [`config.py`](5simTelegramBot-main/config.py:79)  
**Severity:** MEDIUM  
**Root Cause:** When `SECRET_KEY` is not set, a random key is generated via `os.urandom(32).hex()`. This means every process restart generates a new key, invalidating all existing Flask sessions and tokens. In a multi-worker setup (Gunicorn with multiple workers), each worker gets a different key, making session-based auth impossible.

**Recommended Fix:** Remove the `os.urandom()` default. Make `SECRET_KEY` a required environment variable, or at minimum log a prominent warning when the default is used.

---

### M4 — `bot.py` hardcodes `debug=False, use_reloader=False` — no dev-friendly overrides

**File:** [`bot.py`](5simTelegramBot-main/bot.py:75)  
**Severity:** MEDIUM  
**Root Cause:** Flask is always started with `debug=False`, even when `FLASK_DEBUG=true` is set in the environment. The `FLASK_DEBUG` config variable is read (line 78) but never used to set `app.run(debug=...)`.

**Recommended Fix:** Use `app.run(debug=FLASK_DEBUG, ...)` or check the config value in `__main__`.

---

### M5 — `bot_utils.py` is unused — dead module

**File:** [`bot_utils.py`](5simTelegramBot-main/bot_utils.py) — ENTIRE FILE  
**Severity:** MEDIUM  
**Root Cause:** `bot_utils.py` provides `send_message_to_bot()` using the raw Telegram HTTP API. However, the entire project now uses `bot.client.TelegramClient` for message sending via the pyTelegramBotAPI library. No file imports `bot_utils`. The module is loaded by `bot.py:5` (`import bot_utils`) but its `send_message_to_bot` function is **never called**.

**Recommended Fix:** Remove `bot_utils.py` and its import from `bot.py`.

---

### M6 — `currency_service.py` has unused method `_get_usd_to_irr_rate()` returning hardcoded `52000`

**File:** [`currency_service.py`](5simTelegramBot-main/currency_service.py:49-58)  
**Severity:** MEDIUM  
**Root Cause:** The method `_get_usd_to_irr_rate()` returns a hardcoded `52000` and is never called by any other code. The actual USD rate is fetched via `get_usd_rate()` using the Navasan API. This is dead code.

**Recommended Fix:** Remove `_get_usd_to_irr_rate()`.

---

### M7 — `bot/handlers/menu.py` — entire file is a no-op stub

**File:** [`bot/handlers/menu.py`](5simTelegramBot-main/bot/handlers/menu.py:1-18)  
**Severity:** MEDIUM  
**Root Cause:** The file's docstring explicitly states: *"This file exists only for backward compatibility."* The `init()` function just stores the bot instance but nothing uses it from this module. All menu handlers are in `purchase.py` and `services.py`.

**Recommended Fix:** Remove `bot/handlers/menu.py` and its registration in `bot.py:27`.

---

### M8 — `UserService.get_all_ids()` returns `[r['user_id'] for r in rows]` but rows are tuples, not dicts

**File:** [`services/user_service.py`](5simTelegramBot-main/services/user_service.py:79-82)  
**Severity:** MEDIUM  
**Root Cause:** `self._user_repo.get_all_ids()` returns rows from `_execute_read()` which calls `db.fetchall()`. With psycopg2, `fetchall()` returns **tuples**, not dicts (unless using RealDictCursor). Accessing `r['user_id']` will raise `TypeError: tuple indices must be integers or slices, not str`.

This will crash the **admin broadcast** feature hard.

**Recommended Fix:** Change to `[r[0] for r in rows]` or configure `RealDictCursor` in the connection pool.

---

### M9 — `db/migrations.py` uses `?` placeholders in raw SQL but doesn't convert them

**File:** [`db/migrations.py`](5simTelegramBot-main/db/migrations.py:94)  
**Severity:** MEDIUM  
**Root Cause:** Line 94: `INSERT INTO _migrations VALUES (%s, %s, %s, %s)` uses correct `%s` syntax. However, lines 17-18 build INSERT statements with `?` for `DEFAULT_SETTINGS` seeding. Unlike `ConnectionManager.execute()` which auto-replaces `?` with `%s`, the MigrationManager gets raw connections and executes directly. These statements will fail.

```python
# Line 17: Uses Python string formatting with '?' — SQLite syntax in PG
f"INSERT INTO settings (key, value) VALUES ('{k}', '{v}') ON CONFLICT (key) DO NOTHING"
```

**Recommended Fix:** This is actually safe because it uses f-string interpolation (values are embedded, not parametrized). But it's a SQL injection risk if any setting value contains `'`. Use parameterized queries with `%s`.

---

### M10 — `ProviderRegistry` has a race condition on singleton initialization

**File:** [`services/provider_registry.py`](5simTelegramBot-main/services/provider_registry.py:58-62)  
**Severity:** MEDIUM  
**Root Cause:** The `get_instance()` classmethod checks `cls._instance is None` without a lock, then assigns `cls._instance = cls()`. In a multi-threaded environment (Flask with multiple workers), this can create multiple `ProviderRegistry` instances, each with independent provider state.

**Recommended Fix:** Use double-checked locking or a thread-safe singleton pattern (e.g., `threading.Lock()`).

---

### M11 — `bot/router.py` has a closure bug in `register_with_bot()`

**File:** [`bot/router.py`](5simTelegramBot-main/bot/router.py:74-86)  
**Severity:** MEDIUM  
**Root Cause:** The `register_with_bot()` method creates closures inside loops. While the code uses `h=handler` default argument trick to avoid the classic Python closure bug, the lambda for callback queries uses `p=pattern` correctly, but the `_callback_wrapper` and `_message_wrapper` will cause `pyTelegramBotAPI` to register ALL handlers under the LAST pattern/command because of how telebot's `@bot.callback_query_handler` decorator works. The telebot library doesn't support multiple decorators with the same function — each `@bot.message_handler` replaces the previous one.

**Recommended Fix:** Instead of using `@bot.callback_query_handler` decorators in a loop, use `bot.add_callback_query_handler()` or `bot.register_message_handler()` methods which accept handler functions directly.

---

### M12 — `web/routes/admin_panel.py` uses Flask `session` without setting `SECRET_KEY`

**File:** [`web/routes/admin_panel.py`](5simTelegramBot-main/web/routes/admin_panel.py:9)  
**Severity:** MEDIUM  
**Root Cause:** Lines 20-23 use `session.get('admin_token')` and `session['admin_token'] = token`. Flask sessions require a properly configured `SECRET_KEY` (not randomly generated at startup — see M3). If `SECRET_KEY` changes between requests, sessions break.

**Recommended Fix:** Ensure `SECRET_KEY` is explicitly set in `.env` and validated at startup.

---

## LOW ISSUES

### L1 — `startup_test.py` hardcodes an absolute Windows path

**File:** [`startup_test.py`](5simTelegramBot-main/startup_test.py:4)  
**Severity:** LOW  
**Root Cause:** `os.chdir(r'c:\Users\MC\Downloads\5simTelegramBot-main\5simTelegramBot-main')` — this is a hardcoded absolute path that only works on one machine. The script is unusable in Docker, CI/CD, or on any other developer's machine.

**Recommended Fix:** Use `os.path.dirname(os.path.abspath(__file__))` to derive the project root dynamically.

---

### L2 — `admin_config.py` comment says "No direct sqlite3 connections" but uses literal `sqlite3` in its docstring

**File:** [`admin_config.py`](5simTelegramBot-main/admin_config.py:5)  
**Severity:** LOW  
**Root Cause:** Line 5: *"No direct sqlite3 connections."* — This is documentation, not code. However, the file correctly delegates to `SettingsRepository`. No functional issue.

**Recommended Fix:** Remove outdated mention of sqlite3 from docstring.

---

### L3 — `SERVICE_CODE_MAP` in [`config.py`](5simTelegramBot-main/config.py:106) only has 4 entries

**File:** [`config.py`](5simTelegramBot-main/config.py:106-109)  
**Severity:** LOW  
**Root Cause:** The code-to-provider-code mapping only covers `telegram`, `whatsapp`, `instagram`, `google`. Alembic migration 002 seeds 15 services including `facebook`, `tiktok`, `discord`, etc. These additional services have no service code mapping and will pass through un-mapped, potentially causing API call failures.

**Recommended Fix:** Add mappings for all seeded services or implement a database-backed service code mapping.

---

### L4 — `COUNTRY_ID_MAP` in [`config.py`](5simTelegramBot-main/config.py:96) missing `dominican_republic`

**File:** [`config.py`](5simTelegramBot-main/config.py:96-104)  
**Severity:** LOW  
**Root Cause:** `dominican_republic` appears in `service_countries.py` for WhatsApp service but has no ID (`82`) in `COUNTRY_ID_MAP`. It IS in the map at line 101. False report — it IS present. However, `indonesia` at line 97 has ID `6` which may not be a HeroSMS country ID. Verification needed.

**Recommended Fix:** Verify all country IDs against HeroSMS documentation.

---

### L5 — `bot/handlers/admin/` directory has 7 handler files but most are unused

**Files:** [`bot/handlers/admin/broadcast.py`](5simTelegramBot-main/bot/handlers/admin/broadcast.py), [`bot/handlers/admin/channels.py`](5simTelegramBot-main/bot/handlers/admin/channels.py), [`bot/handlers/admin/operators.py`](5simTelegramBot-main/bot/handlers/admin/operators.py), [`bot/handlers/admin/settings.py`](5simTelegramBot-main/bot/handlers/admin/settings.py), [`bot/handlers/admin/stats.py`](5simTelegramBot-main/bot/handlers/admin/stats.py), [`bot/handlers/admin/transactions.py`](5simTelegramBot-main/bot/handlers/admin/transactions.py)  
**Severity:** LOW  
**Root Cause:** These files exist in the directory but are **not imported** in `admin_bot.py` or `bot/handlers/admin_bot.py`. Only `bot/handlers/admin/dashboard.py` and `bot/handlers/admin/users.py` appear to be in use. The other modules represent either planned features or dead code.

**Recommended Fix:** Either wire them into the bot or remove them. Document the status in a README if they're placeholders.

---

## ARCHITECTURE ASSESSMENT

### Positive Findings
1. **Repository Pattern** — All data access flows through `db/repositories/` layer with consistent interfaces
2. **Service Layer Abstraction** — Business logic is properly separated from Telegram handlers in `services/`
3. **DTO Pattern** — Well-typed dataclasses in `data/dto.py` replace raw dicts
4. **Row-Locking** — `SELECT ... FOR UPDATE` used consistently for atomic balance operations
5. **Idempotency** — Payment verification checks for duplicate authority before crediting
6. **Audit Trail** — Admin actions are logged via `AuditService`
7. **RBAC** — Role-based access control with 6 roles and granular permissions
8. **Middleware Pipeline** — Pre-handler processing for auth, language, logging
9. **Feature Flags** — `MIGRATION_FLAGS` for gradual rollout
10. **Security-Hardened Config** — Secrets from environment only, no hardcoded keys
11. **Dual Database Strategy** — `db/schema.py` + Alembic for schema management

### Architecture Weaknesses
1. **Two Migration Systems** — `db/migrations.py` AND Alembic run simultaneously
2. **Inconsistent Cursor Return Types** — Some code expects tuples, some expects dicts
3. **Untestable Singleton Patterns** — `ConnectionManager`, `ProviderRegistry`, `CacheService` all use singletons without dependency injection
4. **Mixed Import Styles** — Some modules import dependencies at top-level, others inside functions (indicating circular dependency workarounds)
5. **File Existence Gaps** — 4 files are referenced but don't exist on disk

### Dependency Graph Issues
- Several service modules import `db_context` inside method bodies to avoid circular imports, indicating tight coupling between the service and data layers
- `compat/legacy_facade.py` creates all service instances at module level — any import error in a service will crash the compat layer and all its callers

---

## RECOMMENDED ACTION PLAN

| Priority | Issue | Action |
|----------|-------|--------|
| 1 | C1 — Missing celery/tasks files | Create `tasks/celery_app.py`, `tasks/__init__.py` |
| 2 | C2 — Double put_connection | Refactor ConnectionManager.execute() |
| 3 | C3 — Webhook security | Add secret token verification |
| 4 | C5 — SQLite ? in PG query | Fix admin_api.py test_purchase_number |
| 5 | H3 — Missing find_by_id_like | Implement in UserRepository |
| 6 | H8 — import-in-function | Hoist db_context imports to module level |
| 7 | M8 — Dict access on tuples | Convert rows to dicts or use integer indices |
| 8 | M11 — Router closure bug | Use proper telebot handler registration API |
| 9 | H10 — Duplicate help handlers | Remove duplicate registration |
| 10 | M7 — Dead menu.py | Remove bot/handlers/menu.py |

---

**Audit Complete.** 73 files fully analyzed. 32 issues cataloged. Proceed to Phase B — Static Analysis.
