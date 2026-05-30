# NumGenius — Enterprise SaaS Platform
## Deployment Guide v3.0

---

## 1. Prerequisites

- Docker 24+ & Docker Compose v2+
- PostgreSQL 16 (or use Docker container)
- Redis 7 (or use Docker container)
- Python 3.11+
- Two Telegram Bot Tokens (Customer + Admin)
- SSL certificate for webhook (production)

---

## 2. Quick Start (Development)

```bash
# Clone and enter project
cd 5simTelegramBot-main/5simTelegramBot-main

# Create .env from example
cp .env.example .env

# Edit .env with your values:
# - BOT_TOKEN (customer bot)
# - ADMIN_BOT_TOKEN (admin bot — separate!)
# - HEROSMS_API_KEY
# - ZARINPAL_MERCHANT
# - ADMIN_API_TOKEN
# - SECRET_KEY

# Install dependencies
pip install -r requirements.txt

# Set up PostgreSQL (or use Docker)
docker compose up -d postgres redis

# Start customer bot
BOT_TOKEN=your_token python bot.py

# Start admin bot (in another terminal)
BOT_TOKEN=your_admin_token python admin_bot.py
```

---

## 3. Production Deployment (Docker)

### 3.1 Configure Environment

```bash
# .env — production values
APP_ENV=production
BOT_TOKEN=1234567890:AAxxxxxxxxxxxxxxxxxxxxxxxxxx
ADMIN_BOT_TOKEN=9876543210:BBxxxxxxxxxxxxxxxxxxxxxxxxxx
ADMIN_IDS=YOUR_TELEGRAM_USER_ID
WEBHOOK_URL=https://yourdomain.com
WEBSITE_URL=https://yourdomain.com
HEROSMS_API_KEY=your_herosms_key
ZARINPAL_MERCHANT=your_merchant_id
ZARINPAL_SANDBOX=false
NAVASAN_API_KEY=your_navasan_key
DATABASE_URL=postgresql://smsbot:StrongPassword123!@postgres:5432/smsbot
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
SECRET_KEY=$(openssl rand -hex 32)
ADMIN_API_TOKEN=$(openssl rand -hex 24)
LOG_LEVEL=INFO
```

### 3.2 Start Full Stack

```bash
# Full stack (all services)
docker compose --profile full up -d

# Check all services running
docker compose ps

# View logs
docker compose logs -f customer_bot
docker compose logs -f admin_bot
```

### 3.3 Individual Service Profiles

```bash
# Customer Bot only
docker compose --profile customer up -d

# Admin Bot only
docker compose --profile admin up -d

# Workers only (Celery + Beat)
docker compose --profile worker up -d
```

---

## 4. Database Migration

Migrations run automatically on startup via `MigrationManager`. The system is idempotent — safe to re-run.

Current migration versions:
- v0: Core tables (users, transactions, orders, settings)
- v1: Default settings
- v2: Performance indexes
- v3: Default currency (USD)
- v4: Default provider (HeroSMS)
- v5: Catalog services
- v6: Catalog countries

---

## 5. Admin Panel Access

1. Start the admin bot
2. Send `/start` to the admin bot on Telegram
3. Click "🖥️ Web Panel" to open the secure admin dashboard
4. The admin panel is at `https://yourdomain.com/admin?token=ADMIN_API_TOKEN`

---

## 6. Architecture

```
┌─────────────┐  ┌─────────────┐  ┌──────────────┐
│ Customer Bot │  │  Admin Bot  │  │ Web Panel    │
│ (bot.py)     │  │(admin_bot)  │  │ (/admin)     │
│ Separate tok │  │ Separate tok│  │ Secure token │
└──────┬───────┘  └──────┬──────┘  └──────┬───────┘
       │                 │                │
       └────────┬────────┴────────────────┘
                │
     ┌──────────▼──────────┐
     │   Service Layer     │
     │   18 Services       │
     └──────────┬──────────┘
                │
     ┌──────────▼──────────┐
     │   PostgreSQL 16     │
     │   20+ tables        │
     └─────────────────────┘
```

---

## 7. Monitoring

- Provider health checks: every 60s (Celery Beat)
- Price sync: every 30s
- Full provider sync: hourly
- Fraud log cleanup: daily at 3 AM
- Database backup: daily at 2 AM

View provider health: Admin Bot → Providers → Health Check

---

## 8. Security Checklist

- [x] All secrets in .env (never committed)
- [x] Separate bot tokens for customer/admin
- [x] RBAC with 6 roles
- [x] Audit log for ALL admin operations
- [x] Anti-fraud with risk scoring
- [x] DB transactions prevent race conditions
- [x] Web admin panel requires token

---

## 9. Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_enterprise_services.py -v

# Run with coverage
pytest tests/ --cov=. --cov-report=term-missing
```

---

## 10. Troubleshooting

| Issue | Solution |
|-------|----------|
| Admin bot doesn't start | Check `ADMIN_BOT_TOKEN` is set |
| Web panel unauthorized | Check `ADMIN_API_TOKEN` in .env |
| Database connection failed | Check `DATABASE_URL` and postgres container |
| Provider sync failing | Check `HEROSMS_API_KEY` validity |
| Balance not updating | Check transaction logs in DB |
