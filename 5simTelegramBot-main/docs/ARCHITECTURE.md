# NumGenius — Enterprise SaaS Platform
## Architecture Documentation v3.0

---

## 1. Executive Summary

NumGenius is an enterprise-grade SaaS platform for virtual number provisioning. It serves as a multi-provider aggregation layer, enabling customers to purchase virtual phone numbers for SMS verification across services like Telegram, WhatsApp, Instagram, and Google.

**Key Differentiators:**
- Multi-provider architecture (HeroSMS, 5SIM, SMS-Activate, SMS-Man, etc.)
- Complete separation of Customer Bot and Admin Bot (zero admin capabilities in customer bot)
- Multi-currency support with USD as base currency
- Tiered subscription model (FREE → ENTERPRISE)
- Enterprise RBAC with audit logging
- Database-persisted referral system with fraud prevention
- Smart routing engine across providers

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                                  │
├──────────────┬──────────────┬──────────────┬────────────────────────┤
│ Customer Bot │  Admin Bot   │ Web Panel    │ REST API Clients       │
│ (Telegram)   │ (Telegram)   │ (Web UI)     │ (External Integrations)│
└──────┬───────┴──────┬───────┴──────┬───────┴───────────┬────────────┘
       │              │              │                   │
       ▼              ▼              ▼                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       API / SERVICE LAYER                            │
├─────────────────────────────────────────────────────────────────────┤
│ Flask REST API  │  Bot Handlers (Customer/Admin) │  Webhook Gateway  │
├─────────────────────────────────────────────────────────────────────┤
│                    SERVICE ORCHESTRATION                             │
│ ┌───────────┐ ┌─────────────┐ ┌──────────────┐ ┌────────────────┐  │
│ │  Wallet   │ │   Order     │ │  Payment     │ │  Subscription  │  │
│ │  Service  │ │   Service   │ │  Service     │ │  Service       │  │
│ └───────────┘ └─────────────┘ └──────────────┘ └────────────────┘  │
│ ┌───────────┐ ┌─────────────┐ ┌──────────────┐ ┌────────────────┐  │
│ │  SMS      │ │  Provider   │ │  Catalog     │ │  Referral      │  │
│ │  Service  │ │  Manager    │ │  Manager     │ │  Service       │  │
│ └───────────┘ └─────────────┘ └──────────────┘ └────────────────┘  │
│ ┌───────────┐ ┌─────────────┐ ┌──────────────┐ ┌────────────────┐  │
│ │  RBAC     │ │  Audit      │ │  Analytics   │ │  Notification  │  │
│ │  Service  │ │  Service    │ │  Service     │ │  Service       │  │
│ └───────────┘ └─────────────┘ └──────────────┘ └────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
       │              │              │
       ▼              ▼              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       DATA LAYER                                     │
├──────────────┬──────────────┬──────────────┬────────────────────────┤
│  PostgreSQL  │    Redis     │   Celery     │  File Storage          │
│  (Primary)   │  (Cache/Q)   │ (Workers)    │  (Receipts/Backups)    │
└──────────────┴──────────────┴──────────────┴────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     PROVIDER ECOSYSTEM                                │
├──────────────┬──────────────┬──────────────┬────────────────────────┤
│ HeroSMS      │ 5SIM         │ SMS-Activate │ SMS-Man / VakSMS / ... │
│ (Primary)    │ (Planned)    │ (Planned)    │ (Plugin Architecture)  │
└──────────────┴──────────────┴──────────────┴────────────────────────┘
```

---

## 3. Database Schema (Enterprise)

### Core Tables
| Table | Purpose | Key Constraints |
|-------|---------|----------------|
| `users` | User accounts | PK: user_id |
| `transactions` | Financial records | FK → users, type enum |
| `orders` | Number purchases | FK → users, unique order_id |
| `card_payments` | Card payment requests | FK → users, status tracking |
| `settings` | Key-value configuration | PK: key |
| `operator_settings` | Service+country+operator | UNIQUE(service, country) |
| `activation_codes` | SMS codes received | FK → orders |

### Enterprise Tables (Phase 1+)
| Table | Purpose |
|-------|---------|
| `subscriptions` | User subscription tiers (FREE→ENTERPRISE) |
| `referrals` | Referral tracking and earnings |
| `referral_codes` | Unique referral codes per user |
| `admin_roles` | RBAC role assignments |
| `audit_log` | Compliance-grade audit trail |
| `currencies` | Multi-currency configuration |
| `providers` | SMS provider registry |
| `provider_countries` | Provider country availability |
| `provider_services` | Provider service availability |
| `provider_prices` | Provider pricing data |
| `catalog_countries` | Admin-curated country catalog |
| `catalog_services` | Admin-curated service catalog |
| `catalog_prices` | Final customer-facing prices |
| `notifications` | Notification queue |
| `fraud_log` | Anti-fraud event log |

---

## 4. Customer Bot (bot.py)

**Security Boundary:** Customer Bot has ZERO administrative capabilities.

### Handlers
- `/start` — Registration and main menu
- `/language` — Language selection (fa/en/ar)
- Buy Number flow (service → country → operator → purchase → get code)
- My Orders (web view)
- Wallet / Balance check
- Add Funds (ZarinPal / Card-to-Card)
- Help system
- Channel membership verification

### Customer Bot has NO access to:
- User management
- Balance modification
- Provider configuration
- Broadcast messaging
- System statistics
- Admin dashboard

---

## 5. Admin Bot (Planned — Separated)

### Capabilities
- User management (search, block, unblock)
- Balance management (add/deduct per user)
- Subscription management (assign/revoke tiers)
- Referral management (view/disable)
- Provider management (add/remove/toggle providers)
- Catalog management (countries, services, pricing)
- Currency management (add/edit/disable currencies)
- Broadcast messaging to all users
- System statistics and reports
- Audit log viewer
- Backup/restore operations
- System health monitoring

---

## 6. Security Architecture

### Secrets Management
- ALL secrets via environment variables only
- NO hardcoded defaults for production secrets
- `_require()` function fails fast on missing secrets
- `.env.example` contains ONLY placeholders

### Authentication & Authorization
- JWT-based API authentication (planned)
- RBAC with 6 predefined roles (SUPER_ADMIN → ANALYST)
- Permission granularity: per-action (e.g., `users:ban`)
- All admin operations audited to `audit_log` table

### Data Protection
- PostgreSQL with SSL connections
- Sensitive data encrypted at rest (API keys)
- Audit trail for ALL balance/role/permission changes
- Idempotency keys for payment operations
- Race condition prevention via DB transactions

---

## 7. Provider Architecture

### Provider Interface (Abstract)
```python
class BaseSMSProvider(ABC):
    provider_name: str
    get_balance() → SMSProviderResponse
    get_prices(service, country) → SMSProviderResponse
    get_numbers_status(country) → SMSProviderResponse
    buy_number(service, country, operator) → SMSProviderResponse
    get_sms(activation_id) → SMSProviderResponse
    cancel_number(activation_id) → SMSProviderResponse
```

### Implemented Providers
- **HeroSMS** (`HeroSMSProvider`) — SMS-Activate compatible protocol

### Planned Providers
- 5SIM, SMS-Activate, SMS-Man, VakSMS, OnlineSIM, SMSHub

Each provider is a self-contained plugin registered in `providers` table.

---

## 8. Deployment

### Docker Compose
```
postgres:16  →  Primary database
redis:7      →  Cache + Celery broker
bot:latest   →  Flask + TeleBot
celery_worker → Background tasks
nginx        →  Reverse proxy
```

### Environment Profiles
- `APP_ENV=development` — Config fallbacks allowed
- `APP_ENV=production` — Strict env validation

---

## 9. Testing Strategy

- **Unit Tests:** Service layer, repositories
- **Integration Tests:** Database operations, provider API
- **Security Tests:** RBAC enforcement, audit logging
- **Target Coverage:** 80%+

---

## 10. Migration Path

1. ✅ Phase 1 — Audit & Architecture Refactor
2. ✅ Phase 1 — Security Hardening (env-only secrets)
3. ✅ Phase 1 — SQLite → PostgreSQL cleanup
4. ✅ Phase 1 — Enterprise schema creation
5. ✅ Phase 1 — Subscription/Referral DB persistence
6. 🔄 Phase 2 — Provider Ecosystem (in progress)
7. ⬜ Phase 3 — Admin Bot (separate bot token)
8. ⬜ Phase 4 — Web Admin Panel
9. ⬜ Phase 5 — Multi-Currency Engine
10. ⬜ Phase 6+ — DevOps, Testing, Final Review

---

*Generated: Phase 1 Completion — Enterprise SaaS Platform Architecture*
