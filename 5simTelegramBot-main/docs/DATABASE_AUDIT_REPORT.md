# DATABASE AUDIT REPORT — NumGenius Enterprise SaaS
## Phase D: Database Validation

**Date:** 2026-05-31  
**Database:** PostgreSQL (single database: `smsbot`, schema: `public`)

---

## SCHEMA INVENTORY

### Source Files
- [`db/schema.py`](5simTelegramBot-main/db/schema.py) — `ALL_TABLES` (27 tables), `INDEXES` (24 indexes), `DEFAULT_SETTINGS` (8 settings)
- [`alembic/versions/001_initial_schema.py`](5simTelegramBot-main/alembic/versions/001_initial_schema.py) — Core + Enterprise tables
- [`alembic/versions/002_constraints.py`](5simTelegramBot-main/alembic/versions/002_constraints.py) — Constraints, indexes, seed data
- [`db/migrations.py`](5simTelegramBot-main/db/migrations.py) — Custom migration system (legacy)

---

## TABLES — COMPLETE INVENTORY (27 tables)

### Core Tables (11)

| # | Table | Primary Key | Notes |
|---|-------|-------------|-------|
| 1 | `users` | `user_id` (BIGINT) | Balance stored as INTEGER (Toman) |
| 2 | `transactions` | `id` (SERIAL) | FK → users(user_id) |
| 3 | `orders` | `id` (SERIAL) | FK → users(user_id), UNIQUE(order_id) |
| 4 | `card_payments` | `payment_id` (TEXT) | FK → users(user_id) |
| 5 | `settings` | `key` (TEXT) | Key-value store |
| 6 | `card_info` | `id` (SERIAL) | Bank card info |
| 7 | `required_channels` | `username` (TEXT) | Mandatory join channels |
| 8 | `operator_settings` | `id` (SERIAL) | UNIQUE(service, country) |
| 9 | `activation_codes` | `id` (SERIAL) | FK → orders(id) |
| 10 | `_migrations` | `version` (INTEGER) | Legacy migration tracking |
| 11 | `alembic_version` | `version_num` (VARCHAR) | Alembic's own tracking — **ISSUE: 001 migration creates this manually** |

### Enterprise Tables (16)

| # | Table | Primary Key | Unique Constraints |
|---|-------|-------------|-------------------|
| 12 | `subscriptions` | `id` (SERIAL) | **MISSING: UNIQUE(user_id)** — see issue D1 |
| 13 | `referrals` | `id` (SERIAL) | UNIQUE(referred_id) |
| 14 | `referral_codes` | `id` (SERIAL) | UNIQUE(user_id), UNIQUE(code) |
| 15 | `admin_roles` | `id` (SERIAL) | UNIQUE(user_id) |
| 16 | `audit_log` | `id` (SERIAL) | None |
| 17 | `currencies` | `id` (SERIAL) | UNIQUE(code) |
| 18 | `providers` | `id` (SERIAL) | UNIQUE(name) |
| 19 | `provider_countries` | `id` (SERIAL) | UNIQUE(provider_id, country_code) |
| 20 | `provider_services` | `id` (SERIAL) | UNIQUE(provider_id, service_code) |
| 21 | `provider_prices` | `id` (SERIAL) | UNIQUE(provider_id, country_code, service_code, operator_name) |
| 22 | `catalog_countries` | `id` (SERIAL) | UNIQUE(country_code) |
| 23 | `catalog_services` | `id` (SERIAL) | UNIQUE(service_code) |
| 24 | `catalog_prices` | `id` (SERIAL) | UNIQUE(country_code, service_code, provider_id) |
| 25 | `notifications` | `id` (SERIAL) | None |
| 26 | `fraud_log` | `id` (SERIAL) | None |
| 27 | `wallet_ledger` | `id` (SERIAL) | CHECK (amount >= 0) |
| 28 | `rate_limits` | `id` (SERIAL) | UNIQUE(key, endpoint, window_start) |

---

## ISSUES FOUND

### D1 — MISSING CONSTRAINT: `subscriptions.user_id` needs UNIQUE

**Severity:** HIGH  
**Table:** `subscriptions`  
**Root Cause:** The [`subscriptions`](5simTelegramBot-main/db/schema.py:113) table defines `user_id BIGINT NOT NULL REFERENCES users(user_id)` but **no** `UNIQUE(user_id)` constraint. The application code at [`services/subscription_service.py:153`](5simTelegramBot-main/services/subscription_service.py:153) uses `ON CONFLICT (user_id) DO UPDATE` which requires a unique constraint.

```sql
-- Current schema (db/schema.py:113):
CREATE TABLE IF NOT EXISTS subscriptions (
    id              SERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(user_id),  -- NO UNIQUE!
    ...
)

-- Code expecting uniqueness (subscription_service.py:153):
INSERT INTO subscriptions (user_id, tier, status, started_at)
VALUES (%s, %s, 'active', CURRENT_TIMESTAMP)
ON CONFLICT (user_id) DO UPDATE SET ...  -- WILL FAIL without UNIQUE(user_id)
```

**Fix:** Add `UNIQUE(user_id)` to the `subscriptions` table.

---

### D2 — CONFLICT: Two migration systems manage the same tables

**Severity:** HIGH  
**Root Cause:** `db/migrations.py` AND Alembic both create tables. Running both will cause conflicts on `_migrations` vs `alembic_version` tracking tables. `db/migrations.py:17` uses f-string interpolation for settings INSERT which is a minor SQL injection vector.

**Fix:** Choose one migration system. Recommended: Remove `db/migrations.py` entirely, use Alembic exclusively.

---

### D3 — `alembic_version` table created manually in migration

**Severity:** MEDIUM  
**File:** [`alembic/versions/001_initial_schema.py:125-130`](5simTelegramBot-main/alembic/versions/001_initial_schema.py:125)  
**Root Cause:** Alembic automatically manages its own `alembic_version` table. Creating it manually with `CREATE TABLE IF NOT EXISTS alembic_version` will conflict with Alembic's internal table management. The Alembic `env.py:67` configures `version_table='alembic_version'` which expects to create/manage the table itself.

**Fix:** Remove lines 125-130 from migration 001.

---

### D4 — Missing foreign key indexes

**Severity:** MEDIUM  
**Root Cause:** The following foreign keys lack covering indexes, which will cause sequential scans on DELETE/UPDATE cascade:
- `orders.user_id` — has index `idx_orders_user_id` ✓
- `transactions.user_id` — has index `idx_transactions_user_id` ✓
- `card_payments.user_id` — has index `idx_card_payments_user_id` ✓
- `subscriptions.user_id` — has index `idx_subscriptions_user_id` ✓
- `referrals.referrer_id` — has index `idx_referrals_referrer` ✓
- `referrals.referred_id` — **NO INDEX** ✗
- `provider_countries.provider_id` — **NO INDEX** ✗
- `provider_services.provider_id` — **NO INDEX** ✗
- `provider_prices.provider_id` — covered by composite index ✓
- `catalog_prices.provider_id` — covered by composite index ✓
- `activation_codes.order_id` — has index `idx_activation_codes_order_id` ✓
- `notifications.user_id` — has index `idx_notifications_user` ✓

**Fix:** Add indexes on `referrals(referred_id)`, `provider_countries(provider_id)`, `provider_services(provider_id)`.

---

### D5 — `_migrations` table uses INTEGER version (no auto-increment)

**Severity:** LOW  
**File:** [`db/schema.py:104-111`](5simTelegramBot-main/db/schema.py:104)  
**Root Cause:** `_migrations.version INTEGER PRIMARY KEY` without `SERIAL` or `IDENTITY`. Version numbers are manually specified, which works but is non-standard.

**Fix:** This is the legacy migration table. Remove with `db/migrations.py` (issue D2).

---

### D6 — `admin_bot.py` schema duplicated between schema.py and alembic migration

**Severity:** LOW  
**File:** [`db/schema.py:149-158`](5simTelegramBot-main/db/schema.py:149) vs [`001_initial_schema.py:172-181`](5simTelegramBot-main/alembic/versions/001_initial_schema.py:172)  
**Root Cause:** `admin_roles` table defined in both `db/schema.py` and Alembic. Alembic migration doesn't reference `db/schema.py` — it contains inline SQL. If the schema changes, both sources must be updated.

**Fix:** Single source of truth. Have Alembic migration read DDL from `db/schema.py` or use SQLAlchemy declarative models.

---

## INDEX INVENTORY

### Performance indexes (24 defined)
All indexes in [`db/schema.py:341-366`](5simTelegramBot-main/db/schema.py:341) and [`002_constraints.py:90-118`](5simTelegramBot-main/alembic/versions/002_constraints.py:90):

| Index | Table | Column(s) | Status |
|-------|-------|-----------|--------|
| idx_transactions_user_id | transactions | user_id | ✓ |
| idx_transactions_timestamp | transactions | timestamp | ✓ |
| idx_transactions_type | transactions | type | ✓ (002 only) |
| idx_transactions_ref_id | transactions | ref_id | ✓ (002 only) |
| idx_orders_user_id | orders | user_id | ✓ |
| idx_orders_activation_id | orders | activation_id | ✓ |
| idx_orders_order_id | orders | order_id | ✓ |
| idx_orders_status | orders | status | ✓ (002 only) |
| idx_orders_created_at | orders | created_at | ✓ (002 only) |
| idx_card_payments_user_id | card_payments | user_id | ✓ |
| idx_card_payments_status | card_payments | status | ✓ |
| idx_activation_codes_order_id | activation_codes | order_id | ✓ |
| idx_subscriptions_user_id | subscriptions | user_id | ✓ |
| idx_subscriptions_tier | subscriptions | tier | ✓ |
| idx_referrals_referrer | referrals | referrer_id | ✓ |
| idx_referral_codes_code | referral_codes | code | ✓ |
| idx_referral_codes_user | referral_codes | user_id | ✓ (002 only) |
| idx_audit_log_admin | audit_log | admin_id | ✓ |
| idx_audit_log_action | audit_log | action | ✓ |
| idx_audit_log_created | audit_log | created_at | ✓ |
| idx_currencies_code | currencies | code | ✓ |
| idx_provider_prices_lookup | provider_prices | composite | ✓ |
| idx_catalog_prices_lookup | catalog_prices | composite | ✓ |
| idx_notifications_user | notifications | user_id, is_read | ✓ |
| idx_fraud_log_user | fraud_log | user_id | ✓ (schema only) |
| idx_wallet_ledger_user | wallet_ledger | user_id | ✓ (schema only) |
| idx_wallet_ledger_type | wallet_ledger | entry_type | ✓ (schema only) |
| idx_wallet_ledger_created | wallet_ledger | created_at | ✓ (schema only) |
| idx_rate_limits_key | rate_limits | key, endpoint | ✓ (schema only) |

### Unique partial index (002_constraints)
| Index | Table | Condition |
|-------|-------|-----------|
| uq_transactions_ref_id | transactions | WHERE ref_id IS NOT NULL |

This ensures idempotency for payment verification — prevents double-crediting the same transaction reference. **Excellent design.**

---

## CHECK CONSTRAINTS

| Table | Constraint | Source |
|-------|-----------|--------|
| users | `ck_users_balance_non_negative` CHECK (balance >= 0) | 002_constraints:38-42 |
| transactions | CHECK (amount > 0) | 001_initial_schema:40 |
| wallet_ledger | CHECK (amount >= 0) | db/schema.py:307 |
| orders | CHECK (price >= 0) | 001_initial_schema:57 |
| card_payments | CHECK (amount > 0) | 001_initial_schema:70 |

**Note:** `users.balance` check is added in migration 002 but NOT present in `db/schema.py:17`. If `setup_databases()` runs before migration 002, this constraint won't exist.

---

## FOREIGN KEY RELATIONSHIPS

All foreign keys are properly defined with `REFERENCES` clauses. No orphaned references detected.

| Child Table | Column | Parent Table | ON DELETE |
|-------------|--------|-------------|-----------|
| transactions | user_id | users | NO ACTION (default) |
| orders | user_id | users | NO ACTION |
| card_payments | user_id | users | NO ACTION |
| activation_codes | order_id | orders | NO ACTION |
| subscriptions | user_id | users | NO ACTION |
| referrals | referrer_id | users | NO ACTION |
| referrals | referred_id | users | NO ACTION |
| referral_codes | user_id | users | NO ACTION |
| notifications | user_id | users | NO ACTION |
| provider_countries | provider_id | providers | NO ACTION |
| provider_services | provider_id | providers | NO ACTION |
| provider_prices | provider_id | providers | NO ACTION |
| catalog_prices | provider_id | providers | NO ACTION |

**Assessment:** No `ON DELETE CASCADE` means manual cleanup is required when deleting users. For a financial system, this is **correct** — financial records should never be automatically deleted.

---

## MIGRATION ROLLBACK TEST

### Migration 001 → downgrade
The `downgrade()` function in [`001_initial_schema.py:339-351`](5simTelegramBot-main/alembic/versions/001_initial_schema.py:339) drops all tables in dependency order:

```python
tables = [
    'fraud_log', 'notifications', 'catalog_prices', 'catalog_services',
    'catalog_countries', 'provider_prices', 'provider_services',
    'provider_countries', 'providers', 'currencies', 'audit_log',
    'admin_roles', 'referral_codes', 'referrals', 'subscriptions',
    'activation_codes', 'operator_settings', 'required_channels',
    'card_info', 'settings', 'card_payments', 'orders', 'transactions',
    'users', 'alembic_version',
]
```

**Assessment:** ✓ Correct reverse-dependency order. All child tables dropped before parents.

### Migration 002 → downgrade
The `downgrade()` in [`002_constraints.py:121-131`](5simTelegramBot-main/alembic/versions/002_constraints.py:121) drops constraints and deletes seed data:
- ✓ Drops `uq_transactions_ref_id` unique index
- ✓ Drops `ck_users_balance_non_negative` check constraint
- ⚠ Deletes ALL rows from `currencies`, `providers`, `catalog_services` — may delete user-added data

**Issue:** Seed data deletion is destructive. Consider using `DELETE WHERE created_in_migration = true` flag or simply not deleting seed data on rollback.

---

## MIGRATION CONSISTENCY

### Schema duplication between db/schema.py and Alembic

**Issue:** `db/schema.py` and Alembic migrations define the same tables independently. This means:
1. A change in `db/schema.py` must be manually replicated in a new Alembic migration
2. `setup_databases()` (which uses `db/schema.py`) and `alembic upgrade head` may produce inconsistent schemas if they diverge

**Recommendation:** Have Alembic be the **single source of truth**. Either:
- Remove `setup_databases()` and always use `alembic upgrade head`
- Or have Alembic migrations import DDL from `db/schema.py` constants

---

## SEED DATA INVENTORY

| Migration | Table | Records |
|-----------|-------|---------|
| 001 (custom) | settings | 8 default key-value pairs |
| 001 (custom) | currencies | 1 (USD) |
| 001 (custom) | providers | 1 (herosms) |
| 001 (custom) | catalog_services | 4 (telegram, whatsapp, instagram, google) |
| 001 (custom) | catalog_countries | 20 countries |
| 002 | currencies | 1 (USD) — duplicate with 001 |
| 002 | providers | 1 (herosms) — duplicate with 001 |
| 002 | catalog_services | 15 services (includes 4 from 001 + 11 more) |
| 002 | settings | 1 (subscription_tiers JSON) |

**Issue:** Seed data is duplicated between custom migrations (`db/migrations.py` MIGRATIONS list) and Alembic migration 002. If both run, `ON CONFLICT DO NOTHING` prevents errors, but the duplicate definitions are a maintenance burden.

---

## OVERALL DATABASE VERDICT

**PARTIALLY CERTIFIED** — 6 issues found (1 HIGH, 3 MEDIUM, 2 LOW).

The schema design is solid with proper foreign keys, unique constraints, check constraints, and performance indexes. The critical issue is the missing `UNIQUE(user_id)` on `subscriptions` (D1) which will cause runtime failures. The dual migration system (D2) is an architectural concern that should be resolved before production.

**Blocking issues for certification:**
- D1: Add `UNIQUE(user_id)` to `subscriptions` table
- D2: Remove `db/migrations.py` or Alembic (keep one)
