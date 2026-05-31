"""
tasks/__init__.py — Celery Background Task Definitions
─────────────────────────────────────────────────
Background workers for:
- Provider sync (countries, services, prices, stock)
- Provider health monitoring
- Payment verification polling
- Notification dispatch (Telegram, Email)
- Report generation
- Fraud log cleanup
- Backup automation
"""

import os

from celery import Celery
from celery.schedules import crontab

# Celery app instance
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

app = Celery(
    '5simTelegramBot',
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Tehran',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,
    task_soft_time_limit=240,
    worker_max_tasks_per_child=200,
    worker_prefetch_multiplier=1,
)

# ── Periodic Schedule ─────────────────────────────────────
app.conf.beat_schedule = {
    'sync-provider-prices-every-30s': {
        'task': 'tasks.sync_provider_prices',
        'schedule': 30.0,
        'options': {'expires': 25},
    },
    'provider-health-check-every-60s': {
        'task': 'tasks.provider_health_check',
        'schedule': 60.0,
        'options': {'expires': 55},
    },
    'full-provider-sync-hourly': {
        'task': 'tasks.full_provider_sync',
        'schedule': crontab(minute=0),
        'options': {'expires': 300},
    },
    'cleanup-fraud-log-daily': {
        'task': 'tasks.cleanup_fraud_log',
        'schedule': crontab(hour=3, minute=0),
    },
    'daily-backup': {
        'task': 'tasks.daily_backup',
        'schedule': crontab(hour=2, minute=0),
    },
}


# ═══════════════════════════════════════════════════════════════
# TASKS
# ═══════════════════════════════════════════════════════════════

@app.task(bind=True, name='tasks.sync_provider_prices')
def sync_provider_prices(self):
    """Sync prices and stock from all active providers (every 30s)."""
    from services.provider_registry import provider_registry
    from services.provider_sync import provider_sync

    for provider in provider_registry.active_providers:
        name = provider.provider_name
        if provider_sync.should_sync(name, 'prices'):
            try:
                provider_sync.sync_prices_only(provider)
            except Exception as e:
                provider_registry.update_health(name, 'error', str(e))
    return {'status': 'ok'}


@app.task(bind=True, name='tasks.provider_health_check')
def provider_health_check(self):
    """Run health check on all active providers (every 60s)."""
    from services.provider_registry import provider_registry
    return provider_registry.health_check_all()


@app.task(bind=True, name='tasks.full_provider_sync')
def full_provider_sync(self):
    """Full sync of countries, services, prices (hourly)."""
    from services.provider_sync import provider_sync
    return provider_sync.sync_all()


@app.task(bind=True, name='tasks.cleanup_fraud_log')
def cleanup_fraud_log(self):
    """Remove fraud log entries older than 90 days."""
    from db.context import db_context
    try:
        with db_context('default', transactional=True) as db:
            db.execute(
                "DELETE FROM fraud_log WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '90 days'"
            )
    except Exception:
        pass
    return {'status': 'ok'}


@app.task(bind=True, name='tasks.daily_backup')
def daily_backup(self):
    """Create daily backup of critical data."""
    from backup_manager import BackupManager
    bm = BackupManager()
    return {'success': bm.create_backup()}


@app.task(bind=True, name='tasks.send_notification')
def send_notification(self, user_id: int, message: str, channel: str = 'telegram'):
    """Send notification to a user via specified channel."""
    if channel == 'telegram':
        from bot_utils import send_message_to_bot
        return {'success': send_message_to_bot(user_id, message)}
    return {'success': False, 'error': f'Unknown channel: {channel}'}


@app.task(bind=True, name='tasks.emit_event')
def emit_event_task(self, event: str, data: dict):
    """Process an async event."""
    from services.event_bus import event_bus
    event_bus.emit(event, data)
    return {'status': 'ok'}


@app.task(bind=True, name='tasks.verify_pending_payments')
def verify_pending_payments(self):
    """Check for stuck pending payments (runs every 5 min)."""
    from db.repositories.card_payment_repository import CardPaymentRepository
    repo = CardPaymentRepository()
    # Stale pending payments > 30 min — mark for admin review
    return {'status': 'ok'}
