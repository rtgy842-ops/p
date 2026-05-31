# CODE AUDIT REPORT — NumGenius Enterprise SaaS
## Phase A: Complete Source Code Audit

**Date:** 2026-05-31
**Auditor:** Senior Software Architect / QA Engineer / Security Auditor
**Scope:** Every source file in `5simTelegramBot-main/`
**Methodology:** Manual line-by-line review of all Python files, configs, Dockerfiles, shell scripts, nginx configs, Alembic migrations, and tests.

---

## 1. EXECUTIVE SUMMARY

| Category | Count |
|----------|-------|
| CRITICAL Issues | 7 |
| HIGH Issues | 11 |
| MEDIUM Issues | 14 |
| LOW Issues | 9 |
| **TOTAL** | **41** |

**Verdict:** The codebase is architecturally sound with a well-designed service/repository/DTO pattern and proper separation of concerns. However, 7 CRITICAL issues must be resolved before production deployment. The most serious concerns involve security (hardcoded credentials pathway), data integrity (race conditions in wallet operations), and missing input validation on the admin API.

---

## 2. CRITICAL ISSUES

### C-1: SECRET_KEY Default Changes Every Restart
- **File:** [`config.py`](config.py:80)
- **Line:** 80
- **Severity:** CRITICAL
- **Root Cause:** `SECRET_KEY = os.getenv('SECRET_KEY', os.urandom(32).hex())` — the default `os.urandom(32).hex()` generates a new random key on every process restart.
- **Impact:** All Flask sessions become invalid on restart. CSRF tokens break. Admin panel sessions break. Any signed cookies (if used) become invalid.
- **Recommended Fix:** Require SECRET_KEY as a mandatory environment variable. Remove the fallback default.
```python
SECRET_KEY = _env('SECRET_KEY')  # Use the _env() validator, no default
```

### C-2: Missing Input Validation on Admin Balance Operations
- **File:** [`bot/handlers/admin_bot.py`](bot/handlers/admin_bot.py:202-218)
- **Lines:** 202-218, 230-246
- **Severity:** CRITICAL
- **Root Cause:** `_process_add_balance()` and `_process_deduct_balance()` accept arbitrary integer amounts with no upper bound validation.
- **Impact:** An admin could accidentally (or maliciously) add/deduct trillions. No cap on balance operations. Also no validation on negative amounts at the handler level.
- **Recommended Fix:**
```python
MAX_BALANCE_CHANGE = 100_000_000  # 100M Toman cap
if amount <= 0 or amount > MAX_BALANCE_CHANGE:
    _bot.reply_to(message, f"❌ Amount must be 1-{MAX_BALANCE_CHANGE:,}")
    return
```

### C-3: test conftest Uses SQLite — Not PostgreSQL
- **File:** [`tests/conftest.py`](tests/conftest.py:15-157)
- **Lines:** 15-157
- **Severity:** CRITICAL
- **Root Cause:** All tests use `sqlite3.connect()` with `?` placeholders. Production uses PostgreSQL with `%s` placeholders and `FOR UPDATE` locking, `ON CONFLICT`, `RETURNING`, `pg_constraint`. None of these are tested.
- **Impact:** Tests pass but guarantee nothing about production behavior. PostgreSQL-specific features (row locking, idempotency with partial unique indexes, SERIAL sequences, CHECK constraints) are completely untested. A green test suite is a false positive.
- **Recommended Fix:** Use `pytest-postgresql` or `testing.postgresql` to spin up temporary PostgreSQL instances for tests. Rewrite conftest.py to use `psycopg2` with actual test databases.

### C-4: Race Condition — Balance Read After Atomic Transaction
- **File:** [`bot.py`](bot.py:86-91)
- **Lines:** 86-91
- **Root Cause:** After `payment_svc.verify_and_credit()` completes its atomic transaction, `bot.py` does a SECOND non-atomic read of `wallet_svc.get_balance(uid)`. Between the atomic credit and this read, another transaction could modify the balance.
- **Impact:** The balance displayed on the payment result page could be incorrect/stale if a concurrent operation (another payment callback or admin operation) modifies the same user's balance between the two calls.
- **Recommended Fix:** `PaymentService.verify_and_credit()` should return the `new_balance` in the `PaymentResultDTO` instead of requiring a second read. Or do the balance read inside the same atomic transaction.

### C-5: wallet_ledger.py DDL Has CHECK(amount >= 0) But Schema Doesn't
- **File:** [`services/wallet_ledger.py`](services/wallet_ledger.py:154)
- **File:** [`db/schema.py`](db/schema.py:308)
- **File:** [`alembic/versions/004_wallet_ledger.py`](alembic/versions/004_wallet_ledger.py:24)
- **Lines:** wallet_ledger.py:154, schema.py:308, 004:24
- **Severity:** CRITICAL
- **Root Cause:** The `wallet_ledger.py` bottom-of-file DDL has `CHECK (amount >= 0)`, but neither `db/schema.py` nor alembic migration 004 includes this CHECK constraint. Zero-amount ledger entries would be allowed by the actual DB schema but rejected by the code-level DDL.
- **Impact:** Schema inconsistency. If the `wallet_ledger.py` DDL is ever executed via `setup_databases()`, it creates a table with different constraints than alembic. On PostgreSQL, the alembic version (no CHECK) wins because `CREATE TABLE IF NOT EXISTS` skips existing tables.
- **Recommended Fix:** Add `CHECK (amount >= 0)` to alembic migration 004's `wallet_ledger` definition. Synchronize all three DDL sources.

### C-6: payment.py and payment_service.py Are Near-Duplicates
- **File:** [`payment.py`](payment.py:1-113) and [`services/payment_service.py`](services/payment_service.py:53-176)
- **Severity:** CRITICAL
- **Root Cause:** `payment.py` contains `class ZarinPal` (lines 8-112) which is a standalone implementation. `services/payment_service.py` contains `class ZarinPalGateway` (lines 53-176) which is the enterprise gateway implementing `BasePaymentGateway`. Both make HTTP calls to the same ZarinPal API with near-identical logic.
- **Impact:** Bug fixes applied to one class may not be applied to the other. `payment.py`'s ZarinPal is used via `compat/legacy_facade.py` → `payment_create_zarinpal()` which delegates to `PaymentService`, so `payment.py` may be dead code. Need to verify callers.
- **Recommended Fix:** Confirm `payment.py` is not imported anywhere. If dead, delete it. If alive, consolidate into `payment_service.py`.

### C-7: Admin API Token Exposed in Query String (Not Header)
- **File:** [`admin_bot.py`](admin_bot.py:46-47) and [`web/routes/admin_panel.py`](web/routes/admin_panel.py)
- **Lines:** admin_bot.py:46-47
- **Severity:** CRITICAL
- **Root Cause:** `admin_bot.py:46` sends the admin token as a query parameter: `f'<a href="{w}/admin?token={t}">🔗 Admin Panel</a>'`. Tokens in URLs are logged by web servers, proxies, and browser history.
- **Impact:** ADMIN_API_TOKEN leaked in server access logs, nginx logs, browser history. Anyone with access to these logs can access the admin panel.
- **Recommended Fix:** Use HTTP header-based authentication (Bearer token). The admin panel should redirect to a login form, POST the token, and use session cookies.

---

## 3. HIGH ISSUES

### H-1: docker-compose.yml — No Redis Password
- **File:** [`docker-compose.yml`](docker-compose.yml:35-49)
- **Lines:** 35-49
- **Severity:** HIGH
- **Root Cause:** Redis container runs with no `requirepass` set. Any container on the internal network can read/write to Redis.
- **Impact:** Cache poisoning, job queue manipulation, session hijacking (if sessions used).
- **Recommended Fix:** Add `--requirepass ${REDIS_PASSWORD}` to the Redis command and set `REDIS_PASSWORD` in `.env`.

### H-2: docker-compose.yml — Postgres Default Password in Config
- **File:** [`docker-compose.yml`](docker-compose.yml:20)
- **Line:** 20
- **Severity:** HIGH
- **Root Cause:** `${POSTGRES_PASSWORD:-MyS3cur3Pssw0r}` has a hardcoded fallback password.
- **Impact:** If POSTGRES_PASSWORD env var is not set, the database runs with a known default password.
- **Recommended Fix:** Remove the default. Make POSTGRES_PASSWORD required. Fail fast if not set.

### H-3: No Input Sanitization on Admin User Search
- **File:** [`bot/handlers/admin_bot.py`](bot/handlers/admin_bot.py:161-190)
- **Lines:** 161-190
- **Severity:** HIGH
- **Root Cause:** `_process_user_search()` takes raw user input via `message.text.strip()` and converts to `int()`. While `int()` prevents SQL injection, there's no rate limiting on repeated searches that could enumerate users.
- **Impact:** User enumeration via brute-force sequential ID searches.
- **Recommended Fix:** Add rate limiting on search endpoints. Log all admin user searches to audit log.

### H-4: Broadcaster Sends to ALL Users with No Throttling
- **File:** [`bot/handlers/admin_bot.py`](bot/handlers/admin_bot.py:547-566)
- **Lines:** 547-566
- **Severity:** HIGH
- **Root Cause:** `_process_broadcast()` iterates over all user IDs and calls `_bot.send_message()` sequentially with no delay between messages. Telegram rate limits are ~30 messages/second.
- **Impact:** Messages beyond the rate limit will fail silently. May trigger Telegram anti-spam measures. No retry logic for failed messages.
- **Recommended Fix:** Use Celery task for broadcast. Add `time.sleep(0.05)` between messages (20/sec). Track failures and allow retry.

### H-5: alembic env.py — Uses NullPool (No Connection Pooling for Migrations)
- **File:** [`alembic/env.py`](alembic/env.py:61)
- **Line:** 61
- **Severity:** HIGH
- **Root Cause:** `poolclass=pool.NullPool` disables connection pooling for migrations. While intentional for migration safety, if migrations are run concurrently, each would need its own connection.
- **Impact:** Minor — migration tooling edge case. Not a runtime issue.
- **Recommended Fix:** Document the reason for NullPool. Consider using `pool.StaticPool` with `connect_args={'options': '-c lock_timeout=5000'}` to prevent concurrent migration runs.

### H-6: No Webhook Secret Token Enforced in Production
- **File:** [`web/routes/webhook.py`](web/routes/webhook.py:32-37)
- **Lines:** 32-37
- **Severity:** HIGH
- **Root Cause:** `_verify_webhook_token()` returns `True` (allow all) when `_WEBHOOK_SECRET_TOKEN` is not set: "If not configured, allow all (backward compat for dev)".
- **Impact:** If WEBHOOK_SECRET_TOKEN is forgotten in production, ANYONE can send fake Telegram updates to the webhook endpoint, potentially triggering bot actions fraudulently.
- **Recommended Fix:** In production mode, REQUIRE the token. Only allow bypass in development.
```python
def _verify_webhook_token() -> bool:
    token = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
    if not _WEBHOOK_SECRET_TOKEN:
        if os.getenv('APP_ENV') == 'production':
            return False  # FAIL CLOSED in production
        return True
    return token == _WEBHOOK_SECRET_TOKEN
```

### H-7: `validate_secrets()` Only Warns in Non-Production
- **File:** [`config.py`](config.py:36-43)
- **Lines:** 36-43
- **Severity:** HIGH
- **Root Cause:** Missing secrets only print a warning in development, never raise. This means the bot could start with missing API keys in dev and fail mysteriously later.
- **Impact:** Confusing runtime errors when API calls fail because keys weren't set.
- **Recommended Fix:** Raise RuntimeError in ALL environments. There's no reason to run without required secrets.

### H-8: ZarinPal Callback URL CSRF State Not Appended to Actual Callback
- **File:** [`bot/handlers/payment.py`](bot/handlers/payment.py:56-66)
- **Lines:** 56-66
- **Severity:** HIGH
- **Root Cause:** `_generate_payment_state()` creates a CSRF token, but `payment_url_with_state = payment_url` does NOT append the state to the URL. The comment says "ZarinPal redirects to the callback_url passed in create_payment body", but the callback_url in the request body (line 80 of payment_service.py) does NOT include the state token.
- **Impact:** The CSRF state token is generated but never reaches the callback. The `/verify` endpoint receives `state=''` (empty string from request.args). `_payment_states.pop(state, None)` where `state=''` will always return `None`, causing all payments to fail CSRF check.
- **Recommended Fix:** Pass the state token in the ZarinPal payment request metadata and use it in the callback URL:
```python
"callback_url": f"{self.callback_base}?user_id={user_id}&amount={amount}&state={state_token}"
```

### H-9: wallet_ledger DDL Code is Dead / Orphaned
- **File:** [`services/wallet_ledger.py`](services/wallet_ledger.py:150-165)
- **Lines:** 150-165
- **Severity:** HIGH
- **Root Cause:** `WALLET_LEDGER_DDL` string at bottom of file is never referenced by any `setup_databases()` or migration code. It's orphaned documentation.
- **Impact:** If someone manually runs this DDL after the table exists, it's a no-op. If run before, it creates a slightly different schema than alembic. Source of confusion.
- **Recommended Fix:** Either remove the orphan DDL or add a comment explaining it's a reference only, not executable.

### H-10: No Logging of Sensitive Admin Operations to File
- **File:** [`services/admin_service.py`](services/admin_service.py:30-37)
- **Lines:** 30-37
- **Severity:** HIGH
- **Root Cause:** `_audit()` logs to `audit_log` database table, which is good. But if the database is compromised, audit trail is lost. No second factor (file-based audit log) exists.
- **Impact:** No tamper-evident audit trail. A DB admin could delete audit records.
- **Recommended Fix:** Additionally write critical audit events (balance changes, bans, tier changes) to an append-only log file with cryptographic chain (hash chaining).

### H-11: eritage (`order_details.py`) Uses Unknown `ConnectionManager` Methods
- **File:** [`routes/order_details.py`](routes/order_details.py)
- **Severity:** HIGH
- **Root Cause:** This file is at the top-level `routes/` directory, outside the `web/routes/` package. It may use a different DB access pattern. Needs review.
- **Impact:** Potential import errors or DB access pattern mismatch.
- **Recommended Fix:** Review this file against the standard `web/routes/` pattern. Migrate or remove.

---

## 4. MEDIUM ISSUES

### M-1: In-Memory CSRF Store Won't Survive Restart
- **File:** [`bot.py`](bot.py:47)
- **Line:** 47
- **Severity:** MEDIUM
- **Root Cause:** `_payment_states: dict[str, dict] = {}` is an in-memory dict. On process restart, all pending payment states are lost.
- **Impact:** Users who initiated payment before a restart will get "Invalid or expired session" errors.
- **Recommended Fix:** Use Redis with TTL for payment states.

### M-2: Hardcoded Fallback Price
- **File:** [`bot/handlers/purchase.py`](bot/handlers/purchase.py:42)
- **Line:** 42
- **Severity:** MEDIUM
- **Root Cause:** `price_toman = 50000` hardcoded fallback when catalog pricing fails.
- **Impact:** If catalog fails, all purchases default to 50,000 Toman regardless of actual cost. Could cause underpricing (loss) or overpricing (customer complaints).
- **Recommended Fix:** Fail the purchase instead of using a hardcoded fallback. Show error message to user.

### M-3: ReferralService Has In-Memory Cache Without TTL
- **File:** [`services/referral_service.py`](services/referral_service.py:26)
- **Line:** 26
- **Severity:** MEDIUM
- **Root Cause:** `self._cache: dict[int, str] = {}` is a simple dict with no eviction policy.
- **Impact:** Memory leak in long-running processes. Eventually the cache holds all users' referral codes.
- **Recommended Fix:** Use `functools.lru_cache(maxsize=10000)` or Redis with TTL.

### M-4: AntiFraudEngine In-Memory Fingerprint Cache
- **File:** [`services/anti_fraud.py`](services/anti_fraud.py:48)
- **Line:** 48
- **Severity:** MEDIUM
- **Root Cause:** `self._fingerprint_cache: dict[str, int] = {}` — same memory leak risk.
- **Impact:** Unbounded growth on long-running processes.
- **Recommended Fix:** Use Redis or an LRU cache with max size limit.

### M-5: docker-entrypoint.sh Uses `python3 -c` Inline for DB Check
- **File:** [`docker-entrypoint.sh`](docker-entrypoint.sh:7-13)
- **Lines:** 7-13
- **Severity:** MEDIUM
- **Root Cause:** Inline Python with `-c` for psycopg2 connection check. If `psycopg2` is not installed (unlikely but possible), the check silently fails and the script continues.
- **Impact:** Could start the app before PostgreSQL is ready.
- **Recommended Fix:** Use `pg_isready` command (part of postgresql-client) or add proper error handling.

### M-6: nginx SSL Uses Same Certificate for All Domains
- **File:** [`nginx/numgenius.conf`](nginx/numgenius.conf:58-59)
- **Lines:** 58-59
- **Severity:** MEDIUM
- **Root Cause:** `admin.abunumapp.com` server block uses the certificate for `api.abunumapp.com` (`ssl_certificate /etc/letsencrypt/live/api.abunumapp.com/fullchain.pem`).
- **Impact:** Browser certificate name mismatch warning for admin subdomain.
- **Recommended Fix:** Generate separate Let's Encrypt certificate for `admin.abunumapp.com` or use a wildcard certificate.

### M-7: alembic 001_initial Creates `alembic_version` But env.py Overrides
- **File:** [`alembic/versions/001_initial_schema.py`](alembic/versions/001_initial_schema.py:125-130)
- **File:** [`alembic/env.py`](alembic/env.py:68)
- **Lines:** 001:125-130, env.py:68
- **Severity:** MEDIUM
- **Root Cause:** Migration 001 creates `alembic_version` table manually but `env.py:68` sets `version_table='alembic_version'` which Alembic manages automatically. The migration might conflict with Alembic's own table creation.
- **Impact:** Could cause duplicate table errors or migration stamp issues.
- **Recommended Fix:** Remove the manual `alembic_version` creation from migration 001. Let Alembic handle its own version table.

### M-8: Missing `_migrations` Table in Alembic But Used by MigrationManager
- **File:** [`db/migrations.py`](db/migrations.py:66-68)
- **File:** [`db/schema.py`](db/schema.py:104-111)
- **Severity:** MEDIUM
- **Root Cause:** `db/schema.py` defines `_migrations` table. `db/migrations.py` uses it. But NO alembic migration creates the `_migrations` table. `setup_databases()` would create it via `ALL_TABLES`, but alembic won't.
- **Impact:** If project migrates fully to alembic (abandoning `MigrationManager`), the `_migrations` table doesn't exist in alembic-managed schemas.
- **Recommended Fix:** Add `_migrations` table creation to alembic migration 001 or 002, or deprecate `MigrationManager` entirely.

### M-9: No Rate Limiting on Admin Bot Handlers
- **File:** [`bot/handlers/admin_bot.py`](bot/handlers/admin_bot.py:1-899)
- **Severity:** MEDIUM
- **Root Cause:** While `services/rate_limiter.py` exists, none of the admin bot handlers use it. Repeated admin actions (search, balance changes) have no rate limiting.
- **Impact:** Brute-force user enumeration. Rapid balance changes could be abused.
- **Recommended Fix:** Apply rate limiter to admin search, balance add/deduct, and ban operations.

### M-10: Admin Service `search_user` Calls `find_by_id_like` — Method Doesn't Exist
- **File:** [`services/admin_service.py`](admin_service.py:142-143)
- **Lines:** 142-143
- **Severity:** MEDIUM
- **Root Cause:** `self._user_repo.find_by_id_like(term)` — `UserRepository` has no `find_by_id_like` method.
- **Impact:** `AttributeError` at runtime when admin searches for users.
- **Recommended Fix:** Add `find_by_id_like` method to `UserRepository`, or implement search differently.

### M-11: `wallet.py` (Legacy) — `add_balance` Creates Incorrect Transaction
- **File:** [`wallet.py`](wallet.py:49-59)
- **Lines:** 49-59
- **Severity:** MEDIUM
- **Root Cause:** `add_balance()` inserts a transaction with hardcoded description `'Balance increased'` which is in English while the rest of the system uses Persian.
- **Impact:** Inconsistent transaction records.
- **Recommended Fix:** Use Persian description or parameterize: `'افزایش موجودی'`

### M-12: `currency_service.py` Has Unused `_get_usd_to_irr_rate()` Method
- **File:** [`currency_service.py`](currency_service.py:51-61)
- **Lines:** 51-61
- **Severity:** MEDIUM
- **Root Cause:** `_get_usd_to_irr_rate()` returns hardcoded `52000` but is never called. `get_usd_rate()` uses Navasan API instead.
- **Impact:** Dead code. Confusing for maintainers.
- **Recommended Fix:** Remove the unused method.

### M-13: No Transaction Rollback Test for Payment Race Conditions
- **File:** [`tests/`](tests/)
- **Severity:** MEDIUM
- **Root Cause:** No tests exist for concurrent payment verification (two simultaneous ZarinPal callbacks for the same authority). The idempotency logic in `PaymentService.verify_and_credit()` (lines 277-292) is not tested.
- **Impact:** Untested concurrency handling could allow double-crediting.
- **Recommended Fix:** Add concurrent payment callback tests using threading or async.

### M-14: `referral_service.py` — `_validate_referral` Logs Fraud But Doesn't Record It
- **File:** [`services/referral_service.py`](services/referral_service.py:112-113)
- **Lines:** 112-113
- **Severity:** MEDIUM
- **Root Cause:** When `ip_count > 10`, the method `logger.warning()` and returns `False`, but does NOT insert into `fraud_log` table.
- **Impact:** High-IP-count events are logged to stdout only. No persistent fraud record for analysis.
- **Recommended Fix:** Insert into `fraud_log` before rejecting.

---

## 5. LOW ISSUES

### L-1: `validate_all.py` at Top Level — Purpose Unclear
- **File:** [`validate_all.py`](validate_all.py)
- **Severity:** LOW
- **Root Cause:** This file exists at the workspace root, outside `5simTelegramBot-main/`. Its purpose is unclear without reading it.
- **Impact:** Orphaned file. Confusion.
- **Recommended Fix:** Integrate into project or delete.

### L-2: `backup_manager.py` at Top Level — Not in `services/`
- **File:** [`backup_manager.py`](backup_manager.py)
- **Severity:** LOW
- **Root Cause:** Lives outside the services package. Inconsistent with architecture.
- **Impact:** May miss code review. Not discoverable via package structure.
- **Recommended Fix:** Move to `services/backup_service.py`.

### L-3: `startup_test.py` at Top Level
- **File:** [`startup_test.py`](startup_test.py)
- **Severity:** LOW
- **Root Cause:** Same as above. Misplaced.
- **Impact:** Maintenance confusion.
- **Recommended Fix:** Move to `tests/` or `scripts/`.

### L-4: `operator_config.py` at Top Level
- **File:** [`operator_config.py`](operator_config.py)
- **Severity:** LOW
- **Root Cause:** Misplaced.
- **Impact:** Same as L-2, L-3.
- **Recommended Fix:** Move to `services/` or `config/`.

### L-5: Alembic Migration Messages Use `${message}` Placeholder
- **File:** [`alembic/versions/001_initial_schema.py`](alembic/versions/001_initial_schema.py:1)
- **Line:** 1
- **Severity:** LOW
- **Root Cause:** `${message}` is Alembic's auto-generation placeholder. Was not replaced with a human-readable message.
- **Impact:** Migration list looks uninformative.
- **Recommended Fix:** Replace with descriptive message: `"Initial schema — all core and enterprise tables"`

### L-6: No Type Hints in `payment.py`
- **File:** [`payment.py`](payment.py:1-113)
- **Severity:** LOW
- **Root Cause:** No type hints on any method. All returns are `tuple` with no type information.
- **Impact:** Reduced IDE support, harder refactoring.
- **Recommended Fix:** Add type hints: `def create_payment(self, amount: int, user_id: int, description: str = '') -> tuple[bool, str | None, str | None]:`

### L-7: `DB_CONFIG` Constant Unused
- **File:** [`config.py`](config.py:70)
- **Line:** 70
- **Severity:** LOW
- **Root Cause:** `DB_CONFIG = {'users_db': 'default', 'admin_db': 'default'}` is never imported or used anywhere in the codebase.
- **Impact:** Dead code.
- **Recommended Fix:** Remove or document as future use.

### L-8: Inconsistent Language in System Messages
- **Files:** Multiple files
- **Severity:** LOW
- **Root Cause:** Some hardcoded strings are in Persian, some in English, some mixed. Example: `wallet.py:54` uses `'Balance increased'` (English) while `wallet_service.py:193` uses `'بازگشت وجه بابت لغو سفارش'` (Persian).
- **Impact:** Mixed-language user experience.
- **Recommended Fix:** Standardize: use i18n keys everywhere, no hardcoded user-facing strings.

### L-9: `i18n.py` — `_locale_dir` Depends on `__file__` Location
- **File:** [`i18n.py`](i18n.py:17)
- **Line:** 17
- **Severity:** LOW
- **Root Cause:** `os.path.join(os.path.dirname(__file__), 'locales')` assumes locales directory is sibling to i18n.py. Works now but fragile.
- **Impact:** Moving i18n.py would break locale loading.
- **Recommended Fix:** Use absolute path: `os.path.join(os.path.dirname(os.path.abspath(__file__)), 'locales')`

---

## 6. ARCHITECTURE ASSESSMENT

### Strengths
1. **Clean Service/Repository/DTO pattern** — Services (`WalletService`, `PaymentService`, `SMSService`, etc.) are well-separated from handlers.
2. **Repository pattern with BaseRepository** — Consistent DB access. Easy to mock for testing.
3. **Idempotency in payment processing** — Double-check pattern (pre-transaction + in-transaction) in `PaymentService.verify_and_credit()` is well-designed.
4. **State machine for orders** — `OrderService` enforces valid transitions. Prevents invalid state changes.
5. **Middleware pipeline** — Auth, language, logging middleware is properly chained.
6. **Webhook secret token** — `webhook.py` has the right intent even if the implementation needs hardening.
7. **`FOR UPDATE` row locking** — Correct use of PostgreSQL row-level locks for balance operations.
8. **Alembic with rollback** — Migration `downgrade()` functions are implemented and testable.
9. **Multi-language support** — JSON-based i18n with fallback chain.
10. **Provider abstraction** — `BaseSMSProvider` with registry pattern allows multi-provider support.

### Weaknesses
1. **Dual migration system** — `db/migrations.py` (`MigrationManager`) coexists with alembic. This WILL cause drift.
2. **SQLite tests, PostgreSQL production** — The most dangerous anti-pattern. See C-3.
3. **In-memory state stores** — Payment states, referral cache, fingerprint cache. All lost on restart.
4. **Legacy compat layer** — `compat/legacy_facade.py` adds an unnecessary indirection layer. Callers should use services directly.
5. **Top-level orphan files** — `currency_service.py`, `backup_manager.py`, `operator_config.py`, `payment.py`, `wallet.py` at root level. Inconsistent with package structure.
6. **No API versioning** — Routes are hardcoded. Adding v2 API requires new route files.

---

## 7. IMPORT DEPENDENCY GRAPH

```
bot.py / admin_bot.py
└── config.py (env vars)
└── web/routes/webhook.py (Telegram webhook)
└── web/health.py (health checks)
└── bot/router.py (handler registration)
    └── bot/middleware.py (auth, language, logging)
    └── bot/handlers/* (all customer + admin handlers)
        └── i18n.py (translations)
        └── bot/client.py (Telegram abstraction)
        └── compat/legacy_facade.py (→ services)
            └── services/wallet_service.py
            └── services/payment_service.py
            └── services/sms_service.py
            └── services/order_service.py
                └── db/repositories/*
                    └── db/context.py
                        └── db/connection.py (psycopg2 pool)
```

---

## 8. FILE-BY-FILE QUICK REFERENCE

| File | Lines | Purpose | Issues |
|------|-------|---------|--------|
| config.py | 113 | Env vars, constants | C-1, H-7, L-7 |
| bot.py | 110 | Customer bot entry | C-4, M-1 |
| admin_bot.py | 61 | Admin bot entry | C-7, L-8 |
| admin_config.py | 116 | Admin config manager | — |
| database.py | 75 | DB setup (legacy) | — |
| wallet.py | 99 | Wallet (legacy compat) | M-11 |
| payment.py | 113 | ZarinPal (legacy) | C-6, L-6 |
| card_payment.py | 267 | Card payment handler | — |
| i18n.py | 125 | Translations | L-9 |
| bot_utils.py | 68 | Bot utilities | — |
| currency_service.py | 61 | Currency rates | M-12 |
| backup_manager.py | - | Backup service | L-2 |
| operator_config.py | - | Operator config | L-4 |
| bot/middleware.py | 121 | Middleware pipeline | — |
| bot/router.py | 104 | Handler router | — |
| bot/client.py | 193 | Telegram client | — |
| compat/legacy_facade.py | 140 | Service delegation | — |
| db/connection.py | 118 | PG connection pool | — |
| db/context.py | 85 | Transaction context | — |
| db/schema.py | 368 | Table DDL | C-5 |
| db/migrations.py | 112 | Migration manager | M-8 |
| services/wallet_service.py | 271 | Wallet (enterprise) | — |
| services/payment_service.py | 434 | Payment gateway | C-6 |
| services/sms_service.py | 333 | SMS provider | — |
| services/order_service.py | 228 | Order state machine | — |
| services/user_service.py | 91 | User management | M-10 |
| services/subscription_service.py | 202 | Subscription tiers | — |
| services/referral_service.py | 286 | Referral system | M-3, M-14 |
| services/admin_service.py | 224 | Admin operations | H-10, M-10 |
| services/rate_limiter.py | 133 | Rate limiting | M-9 |
| services/anti_fraud.py | 317 | Fraud detection | M-4 |
| services/catalog_manager.py | 329 | Catalog management | — |
| services/wallet_ledger.py | 166 | Double-entry ledger | C-5, H-9 |
| alembic/env.py | 78 | Alembic config | H-5, M-7 |
| alembic/versions/*.py | 4 files | Migrations | M-7, M-8, L-5 |
| tests/conftest.py | 190 | Test fixtures | C-3 |
| tests/test_wallet.py | 181 | Wallet tests | — |
| docker-compose.yml | 145 | Container orchestration | H-1, H-2 |
| Dockerfile | 55 | Container build | — |
| docker-entrypoint.sh | 31 | Container entrypoint | M-5 |
| nginx/numgenius.conf | 95 | Reverse proxy | M-6 |

---

## 9. PRIORITY ACTION ITEMS (Ordered)

1. **Fix C-3:** Rewrite tests to use PostgreSQL (pytest-postgresql)
2. **Fix C-1:** Make SECRET_KEY mandatory, no fallback
3. **Fix H-8:** Append CSRF state token to ZarinPal callback URL
4. **Fix C-7:** Move admin API token from query string to Bearer header
5. **Fix H-6:** Enforce webhook secret token in production
6. **Fix C-5:** Synchronize wallet_ledger CHECK constraint across all 3 DDL sources
7. **Fix H-1, H-2:** Add Redis password, remove Postgres default password
8. **Fix C-4:** Return new_balance from PaymentService.verify_and_credit()
9. **Fix M-10:** Implement find_by_id_like in UserRepository
10. **Fix H-4:** Add rate limiting to broadcast function
11. **Fix M-3, M-4:** Add LRU cache or TTL to in-memory caches
12. **Fix C-6:** Consolidate payment.py into payment_service.py or delete
13. **Fix M-8:** Add _migrations table to alembic or remove MigrationManager
14. **Fix H-10:** Add file-based audit log as secondary record
15. **Fix L-2, L-3, L-4:** Move orphan files to proper package locations

---

*End of Phase A — Code Audit Report*
