# Changelog

All notable changes to this project will be documented in this file.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
versioning follows [Semantic Versioning](https://semver.org/).

---

## [2.0.0] — 2026-05-26

### 🏗️ Architecture (Complete Rewrite as Enterprise SaaS Platform)

#### Added
- **Phase 0: Security Hardening**
  - All secrets moved to `.env` file via `python-dotenv`
  - `.gitignore` with comprehensive ignore rules
  - 22 test endpoints protected with `@_require_admin` decorator
  - Fixed destructive `DROP TABLE transactions` on restart

- **Phase 1: Configuration & Environment**
  - Centralized `data/service_countries.py` — single source of truth
  - `services/settings_service.py` — cached settings access layer
  - All hardcoded URLs replaced with config references
  - Fixed undefined `webhook_base_url` bug

- **Phase 2: Database Layer**
  - `db/connection.py` — ConnectionManager (singleton, WAL mode, query logging)
  - `db/context.py` — DatabaseContext with BEGIN/COMMIT/ROLLBACK
  - `db/schema.py` — all 10 table DDLs + performance indexes
  - `db/migrations.py` — versioned, reversible migration system (4 versions)
  - 5 repositories: User, Order, Transaction, Settings, CardPayment
  - Professional `backup_manager.py` — atomic, checksum-validated, rotated

- **Phase 3: Service Layer**
  - SMS Service — Provider-based architecture (BaseSMSProvider → HeroSMS)
  - Payment Service — Gateway-based (BasePaymentGateway → ZarinPal + CardToCard)
  - Wallet Service — single source for ALL balance changes
  - Order Service — state machine with 9 states (CREATED→...→REFUNDED)
  - User Service — get/create, language, block, search
  - Admin Service — security boundary with audit logging
  - Cache Service — TTL-based with hit/miss tracking
  - 9 DTOs + 4 Enums — typed schemas, no more raw dicts

- **Phase 4: Modular Bot**
  - `bot/client.py` — TelegramClient abstraction layer
  - `bot/middleware.py` — MiddlewarePipeline (auth, language, logging)
  - `bot/error_handler.py` — ErrorBoundary (centralized exception protection)
  - `bot/router.py` — Router system for handler registration
  - `bot/keyboards/` — shared keyboard builders
  - 4 thin handlers: start, language, help, services

- **Phase 5: Infrastructure**
  - `Dockerfile` — multi-stage, non-root, health check
  - `docker-compose.yml` — 5 services (nginx, bot, worker, beat, redis)
  - `nginx/nginx.conf` — production reverse proxy with rate limiting
  - `docker-entrypoint.sh` — graceful startup/shutdown
  - `config/profiles.py` — dev/staging/production profiles
  - `scripts/backup.sh` — timestamped, compressed, retention policy
  - Added: `redis`, `celery`, `gunicorn` to requirements

- **Phase 6: Enterprise Features**
  - RBAC — 6 roles, 22 granular permissions
  - Audit Service — DB-backed audit trail with indexes
  - Analytics — revenue, orders, users, payments, dashboard
  - Subscription — 4 tiers (Free/Premium/Reseller/Enterprise)
  - Referral — anti-fraud with limits
  - Notification — event-driven, queue-based, multi-channel
  - API Keys — lifecycle management (create/validate/revoke/track)
  - Feature Flags — toggle/percentage rollout/A/B testing
  - Event Bus — internal pub/sub system
  - Admin API — RESTful blueprint (7 endpoints)

- **Phase 7: Quality & DevOps**
  - Test suite — wallet, order state machine, RBAC (15+ tests)
  - CI/CD — GitHub Actions (lint → test → security → docker)
  - Prometheus metrics — counters, gauges, histograms
  - `pyproject.toml` — ruff, mypy, bandit, pytest config
  - Disaster Recovery Plan — RTO < 1h, RPO < 5min
  - CHANGELOG.md — semantic versioning

### Changed
- `config.py` — all values from env vars with backward-compatible fallbacks
- `operator_config.py` — imports from centralized data source
- `bot.py` — 4 duplicate service_countries replaced, 3 hardcoded URLs removed
- `database.py` — removed destructive DROP TABLE
- `requirements.txt` — added redis, celery, gunicorn

### Fixed
- CRITICAL: `DROP TABLE transactions` removed (data loss prevention)
- CRITICAL: 5 hardcoded API secrets exposed (now in .env)
- HIGH: 22 unauthenticated test endpoints (now admin-only)
- HIGH: Undefined `webhook_base_url` config key
- MEDIUM: 4 duplicate service-country mappings consolidated

---

## [1.0.0] — 2025 (Legacy)

- Initial monolith release (bot.py, 4010 lines)
- Telegram bot with SMS number purchasing
- SQLite databases (3 separate files)
- ZarinPal + Card-to-Card payment
- Persian/English/Arabic i18n
- Admin panel via Telegram