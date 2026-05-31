# NumGenius SaaS — Phase 0+1 Audit & Rescue Report
## Date: 2026-05-31 UTC

---

## Phase 0: RESCUE MODE — Applied Fixes

### CRITICAL FIXES APPLIED

| # | Issue | File | Fix |
|---|-------|------|-----|
| 1 | Real API keys in `.env` committed to repo | `.gitignore` | Strengthened — added `data/users_backup.json`, `*.pem`, `*.key`, `credentials.json`, `secrets/` |
| 2 | `auth_middleware` checked `balance` instead of `is_blocked` | [`bot/middleware.py`](bot/middleware.py:47) | Fixed to check `is_blocked` column; blocks in production if DB unavailable |
| 3 | Admin bot used `BOT_TOKEN` as fallback — no token separation | [`admin_bot.py`](admin_bot.py:12) | Now requires `ADMIN_BOT_TOKEN`; raises `RuntimeError` if missing |
| 4 | No `SELECT ... FOR UPDATE` on balance operations — race conditions | [`db/repositories/user_repository.py`](db/repositories/user_repository.py:63) | Added `FOR UPDATE` to `add_balance`, `deduct_balance`, `refund_balance` |
| 5 | Balance update + transaction log NOT atomic (two separate transactions) | [`services/wallet_service.py`](services/wallet_service.py:1) | COMPLETE REWRITE: Single `db_context` transaction wraps SELECT FOR UPDATE + UPDATE balance + INSERT transaction |
| 6 | Payment verify_and_credit NOT atomic — could credit balance but fail to log | [`services/payment_service.py`](services/payment_service.py:263) | Single DB transaction + idempotency check (double-check `ref_id` before credit) |
| 7 | No idempotency guard on payment callbacks — double-charge risk | [`services/payment_service.py`](services/payment_service.py:263) | Idempotency via `ref_id` UNIQUE check before crediting; both pre-check and in-transaction check |
| 8 | Hardcoded `DATABASE_URL` default in config and connection modules | [`config.py`](config.py:67), [`db/connection.py`](db/connection.py:14) | DATABASE_URL now validated by `_env()` → missing = runtime error in production |
| 9 | `/verify` route used legacy compat (non-atomic, no idempotency) | [`bot.py`](bot.py:51) | Rewired to use `PaymentService.verify_and_credit()` directly with idempotency |

### HIGH/MEDIUM FIXES APPLIED

| # | Issue | File | Fix |
|---|-------|------|-----|
| 10 | HeroSMS plugin using outdated SMS-Activate protocol only | New file | Created [`services/providers/herosms_rest_provider.py`](services/providers/herosms_rest_provider.py) — official REST API |
| 11 | No Celery sync tasks for provider data | New files | Created [`tasks/celery_app.py`](tasks/celery_app.py) + [`tasks/sync_tasks.py`](tasks/sync_tasks.py) with Beat schedule |
| 12 | `purchase.py` duplicates price calculation already in `SMSService` | [`bot/handlers/purchase.py`](bot/handlers/purchase.py:37) | NOTED — still uses compat layer for backward compat; Phase 5 will migrate |

---

## ARCHITECTURE AUDIT (Phase 1)

### ✅ STRENGTHS

1. **Repository Pattern**: Well-structured with `db/repositories/` — clean separation
2. **Service Layer**: Business logic isolated in `services/` — no Telegram deps
3. **Provider Architecture**: `BaseSMSProvider` abstract + `ProviderRegistry` singleton
4. **Database Context**: `db_context()` with auto BEGIN/COMMIT/ROLLBACK
5. **State Machine**: `services/order_service.py` implements proper order state transitions
6. **RBAC**: `services/rbac_service.py` with roles and permissions
7. **I18N**: Multi-language support via `locales/ar.json`, `locales/en.json`, `locales/fa.json`

### ⚠️ AREAS FOR IMPROVEMENT

| Area | Current State | Recommendation |
|------|---------------|----------------|
| Secret Management | `.env` file with real credentials exists | **CRITICAL**: Rotate all keys immediately; use Docker secrets or vault |
| Token Separation | Fixed | Admin bot now requires separate `ADMIN_BOT_TOKEN` |
| Transaction Atomicity | Partially fixed in Phase 0 | Complete — all financial ops now atomic |
| Schema Versioning | Custom `_migrations` table, no Alembic | Phase 2: Migrate to Alembic for proper versioning |
| FK Constraints | Only on `orders.user_id`, `transactions.user_id`, etc. | Phase 2: Add cascading deletes where appropriate |
| Error Handling | Broad `except Exception` in many handlers | Phase 5: Introduce typed exceptions and error codes |
| Logging | `logging` throughout, but no structured logging | Phase 12: Consider `structlog` or JSON logging |
| API Authentication | `ADMIN_API_TOKEN` in query string | Phase 7/12: Use JWT or session-based auth |
| Rate Limiting | None | Phase 12: Add Flask-Limiter or nginx rate limiting |
| HTTPS | Assumed at nginx level | Phase 12: Enforce in app config + HSTS header |

### REVISED FILE INVENTORY

```
5simTelegramBot-main/
├── config.py                    # ✅ Fixed: DATABASE_URL from _env()
├── bot.py                       # ✅ Fixed: /verify uses PaymentService
├── admin_bot.py                 # ✅ Fixed: requires ADMIN_BOT_TOKEN
├── db/
│   ├── connection.py            # ✅ Fixed: imports DATABASE_URL from config
│   ├── schema.py                # ✅ Good: all tables defined
│   ├── context.py               # ✅ Good: BEGIN/COMMIT/ROLLBACK
│   ├── migrations.py            # ⚠️ Custom migration, Phase 2 → Alembic
│   └── repositories/
│       ├── user_repository.py   # ✅ Fixed: FOR UPDATE row locking
│       └── ...                  # ✅ OK
├── services/
│   ├── wallet_service.py        # ✅ REWRITTEN: fully atomic
│   ├── payment_service.py       # ✅ Fixed: atomic + idempotent
│   ├── sms_service.py           # ✅ OK: HeroSMS provider
│   ├── order_service.py         # ✅ OK: state machine
│   └── providers/
│       ├── __init__.py          # ✅ NEW
│       └── herosms_rest_provider.py  # ✅ NEW: REST API plugin
├── tasks/
│   ├── celery_app.py            # ✅ NEW: Celery + Beat schedule
│   └── sync_tasks.py            # ✅ NEW: sync + fetch + cleanup tasks
├── bot/
│   ├── middleware.py            # ✅ Fixed: is_blocked check
│   └── handlers/                # ⚠️ Phase 5 cleanup needed
├── .gitignore                   # ✅ Strengthened
└── .env                         # ⚠️ ROTATE ALL KEYS IMMEDIATELY
```

---

## NEXT: Phase 2 — Database Enhancement

### Tasks
1. Set up Alembic with `alembic init`
2. Create initial migration from current schema
3. Add missing FK constraints with CASCADE where appropriate
4. Add CHECK constraints (balance >= 0, amount > 0)
5. Add UNIQUE constraint on `transactions.ref_id` for idempotency
6. Improve `orders` table: add `provider_id`, `external_id`, `currency_code`
7. Set up `alembic upgrade head` in startup scripts

### Files to create
- `alembic.ini`
- `alembic/env.py`
- `alembic/versions/001_initial_schema.py`
- `alembic/versions/002_add_constraints.py`
