#!/usr/bin/env python3
"""
scripts/health_check.py — System Health Verification
─────────────────────────────────────────────────
Verifies ALL subsystems before deployment.
Run: python scripts/health_check.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

PASS = "✅ PASS"
FAIL = "❌ FAIL"
SKIP = "⚠️ SKIP"

results = {}


def check(name: str, test_func):
    try:
        test_func()
        results[name] = PASS
        print(f"{PASS} {name}")
    except Exception as e:
        results[name] = f"{FAIL} — {e}"
        print(f"{FAIL} {name}: {e}")


# ── 1. Config Loading ─────────────────────────────────────────
def check_config():
    from config import BOT_CONFIG, HEROSMS_CONFIG, PAYMENT_CONFIG, DATABASE_URL
    assert BOT_CONFIG['token'], "BOT_TOKEN not set"
    assert HEROSMS_CONFIG['api_key'], "HEROSMS_API_KEY not set"
    assert PAYMENT_CONFIG['zarinpal_merchant'], "ZARINPAL_MERCHANT not set"
    assert DATABASE_URL, "DATABASE_URL not set"
    assert BOT_CONFIG['admin_ids'], "ADMIN_IDS not set"

check("Config loading", check_config)

# ── 2. Database Connectivity ──────────────────────────────────
def check_database():
    from db.connection import ConnectionManager
    cm = ConnectionManager.get_instance()
    conn = cm.get_connection('default')
    cursor = conn.cursor()
    cursor.execute("SELECT 1")
    assert cursor.fetchone()[0] == 1
    cm.put_connection(conn)

check("Database connectivity", check_database)

# ── 3. Redis Connectivity ─────────────────────────────────────
def check_redis():
    import redis
    url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    r = redis.from_url(url)
    assert r.ping(), "Redis ping failed"

check("Redis connectivity", check_redis)

# ── 4. Celery Connectivity ────────────────────────────────────
def check_celery():
    from celery import Celery
    url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    app = Celery('health_check', broker=url)
    conn = app.connection()
    conn.ensure_connection(max_retries=1)
    conn.release()

check("Celery connectivity", check_celery)

# ── 5. Provider Connectivity ──────────────────────────────────
def check_provider():
    from services.sms_service import HeroSMSProvider
    provider = HeroSMSProvider()
    result = provider.get_balance()
    assert result.success, f"Provider API failed: {result.error}"

check("Provider (HeroSMS) connectivity", check_provider)

# ── 6. Bot Configuration ──────────────────────────────────────
def check_bot():
    import requests
    token = os.getenv('BOT_TOKEN', '')
    resp = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
    assert resp.status_code == 200, f"HTTP {resp.status_code}"
    data = resp.json()
    assert data.get('ok'), f"Telegram API error: {data}"

check("Bot configuration", check_bot)

# ── 7. Admin Bot Configuration ────────────────────────────────
def check_admin_bot():
    import requests
    token = os.getenv('ADMIN_BOT_TOKEN', '')
    resp = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
    assert resp.status_code == 200, f"HTTP {resp.status_code}"
    data = resp.json()
    assert data.get('ok'), f"Telegram API error: {data}"

check("Admin bot configuration", check_admin_bot)

# ── 8. Schema Verification ────────────────────────────────────
def check_schema():
    from db.schema import ALL_TABLES, INDEXES
    assert len(ALL_TABLES) >= 20, f"Only {len(ALL_TABLES)} tables defined"
    assert len(INDEXES) >= 15, f"Only {len(INDEXES)} indexes defined"

check("Schema completeness", check_schema)

# ── 9. Import Chain ───────────────────────────────────────────
def check_imports():
    from services.wallet_service import WalletService
    from services.payment_service import PaymentService
    from services.wallet_ledger import WalletLedger
    from services.rate_limiter import RateLimiter
    from services.catalog_manager import catalog
    from services.sms_service import SMSService, HeroSMSProvider
    from services.provider_registry import provider_registry
    from services.provider_sync import provider_sync
    from services.audit_service import audit_service
    from services.rbac_service import rbac

check("Import chain", check_imports)

# ── Summary ───────────────────────────────────────────────────
print("\n" + "=" * 50)
passed = sum(1 for v in results.values() if v == PASS)
failed = sum(1 for v in results.values() if v.startswith(FAIL))
print(f"RESULTS: {passed} PASS, {failed} FAIL, {len(results)} total")
sys.exit(1 if failed > 0 else 0)
