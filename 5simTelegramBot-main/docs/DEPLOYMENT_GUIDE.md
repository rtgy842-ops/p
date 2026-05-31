# NumGenius — Production Deployment Guide

## Environment Variables (`.env`)

```bash
# Application
APP_ENV=production

# Customer Bot (REQUIRED)
BOT_TOKEN=<your-customer-bot-token>

# Admin Bot (REQUIRED — MUST be different from BOT_TOKEN!)
ADMIN_BOT_TOKEN=<your-admin-bot-token>
ADMIN_IDS=<your-telegram-user-id>

# Webhook URLs
WEBHOOK_URL=https://api.yourdomain.com
WEBSITE_URL=https://app.yourdomain.com
ADMIN_WEBHOOK_URL=https://admin.yourdomain.com

# SMS Provider (HeroSMS)
HEROSMS_API_KEY=<your-herosms-api-key>

# Payment (ZarinPal)
ZARINPAL_MERCHANT=<your-zarinpal-merchant-id>
ZARINPAL_SANDBOX=false

# Database
DATABASE_URL=postgresql://smsbot:<STRONG_PASSWORD>@postgres:5432/smsbot
POSTGRES_USER=smsbot
POSTGRES_PASSWORD=<STRONG_PASSWORD>
POSTGRES_DB=smsbot

# Redis / Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Flask Security
SECRET_KEY=<generate-with: python -c "import secrets; print(secrets.token_hex(32))">

# Admin Panel
ADMIN_API_TOKEN=<generate-with: python -c "import secrets; print(secrets.token_hex(16))">

# Logging
LOG_LEVEL=INFO
```

## Deployment Steps

### 1. Clone and configure

```bash
git clone <repo-url> /opt/numgenius
cd /opt/numgenius
cp .env.example .env
# Edit .env with real values
```

### 2. Set up Nginx reverse proxy

```bash
cp nginx/numgenius.conf /etc/nginx/sites-available/
ln -s /etc/nginx/sites-available/numgenius.conf /etc/nginx/sites-enabled/
certbot --nginx -d api.yourdomain.com -d app.yourdomain.com -d admin.yourdomain.com
```

### 3. Start services

```bash
# With all services
docker compose --profile full up -d

# Customer bot only
docker compose --profile customer up -d

# Admin bot only
docker compose --profile admin up -d

# Workers only
docker compose --profile worker up -d
```

### 4. Run migrations

```bash
docker compose exec customer_bot alembic upgrade head
```

### 5. Set webhooks (one-time)

```bash
# Customer bot webhook
curl "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook?url=https://api.yourdomain.com/"

# Admin bot webhook
curl "https://api.telegram.org/bot<ADMIN_BOT_TOKEN>/setWebhook?url=https://admin.yourdomain.com/"
```

### 6. Verify

```bash
# Health check
curl https://api.yourdomain.com/ping

# Check Docker status
docker compose ps

# Check logs
docker compose logs -f customer_bot
```

## Service Architecture

```
                    ┌─────────────┐
                    │   NGINX     │ :443 (SSL by certbot)
                    └──┬──┬──┬───┘
                       │  │  │
         ┌─────────────┘  │  └─────────────┐
         ▼                ▼                 ▼
   ┌──────────┐    ┌──────────┐    ┌──────────────┐
   │Customer  │    │Admin Bot │    │Web Admin     │
   │Bot:5001  │    │:5002     │    │Panel (Flask) │
   └────┬─────┘    └────┬─────┘    └──────┬───────┘
        │               │                 │
        └───────────────┼─────────────────┘
                        ▼
              ┌─────────────────┐
              │  PostgreSQL:16  │
              └─────────────────┘
                        ▲
         ┌──────────────┼──────────────┐
         ▼              ▼              ▼
   ┌──────────┐  ┌──────────┐  ┌──────────┐
   │  Redis   │  │ Worker   │  │  Beat    │
   │  :6379   │  │ (Celery) │  │(Scheduler)│
   └──────────┘  └──────────┘  └──────────┘
```

## Backup Strategy

```bash
# Daily automated backup (add to crontab)
0 3 * * * docker compose exec -T postgres pg_dump -U smsbot smsbot > /backups/numgenius_$(date +\%Y\%m\%d).sql

# Manual backup
docker compose exec postgres pg_dump -U smsbot smsbot > backup.sql

# Restore
docker compose exec -T postgres psql -U smsbot smsbot < backup.sql
```

## Security Checklist

- [x] All secrets in `.env` (NOT in code)
- [x] `ADMIN_BOT_TOKEN` separate from `BOT_TOKEN`
- [x] `ADMIN_API_TOKEN` for web panel auth
- [x] Row-level locking (`SELECT ... FOR UPDATE`) on all balance ops
- [x] Idempotent payment callbacks (unique `ref_id` check)
- [x] Atomic transactions (BEGIN/COMMIT) for all financial operations
- [x] Rate limiting on API endpoints
- [x] Audit logging for all admin actions
- [x] SSL/HTTPS via certbot + nginx
- [x] `.env` and secrets excluded from git
- [x] PostgreSQL with strong password
- [x] Redis AOF persistence enabled
