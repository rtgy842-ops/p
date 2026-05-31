"""
tasks/ — Celery Background Tasks
─────────────────────────────────────────────────
Periodic tasks for provider synchronization,
SMS code fetching, and system maintenance.

Configured via Celery Beat schedule.
"""
import logging
from celery import Celery
from celery.schedules import crontab
import os

logger = logging.getLogger(__name__)

# ── Celery App ──────────────────────────────────────────────────
REDIS_URL = os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/0')
RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379/0')

app = Celery(
    'numgenius',
    broker=REDIS_URL,
    backend=RESULT_BACKEND,
    include=['tasks.sync_tasks'],
)

app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 minutes max per task
    task_soft_time_limit=540,  # 9 minutes soft limit
    worker_max_tasks_per_child=200,
    worker_prefetch_multiplier=1,
)

# ── Beat Schedule ──────────────────────────────────────────────
app.conf.beat_schedule = {
    # ── Provider Sync Tasks ────────────────────────────────
    'sync-hero-countries': {
        'task': 'tasks.sync_tasks.sync_hero_countries',
        'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
        'args': (),
    },
    'sync-hero-services': {
        'task': 'tasks.sync_tasks.sync_hero_services',
        'schedule': crontab(minute=10, hour='*/6'),  # Every 6 hours, offset 10 min
        'args': (),
    },
    'sync-hero-prices': {
        'task': 'tasks.sync_tasks.sync_hero_prices',
        'schedule': crontab(minute=30, hour='*/3'),  # Every 3 hours
        'args': (),
    },
    # ── SMS Code Fetching ──────────────────────────────────
    'fetch-sms-codes': {
        'task': 'tasks.sync_tasks.fetch_pending_sms_codes',
        'schedule': crontab(minute='*/2'),  # Every 2 minutes
        'args': (),
    },
    # ── System Health ──────────────────────────────────────
    'health-check-providers': {
        'task': 'tasks.sync_tasks.health_check_providers',
        'schedule': crontab(minute=0, hour='*'),  # Every hour
        'args': (),
    },
    # ── Cleanup ────────────────────────────────────────────
    'cleanup-expired-orders': {
        'task': 'tasks.sync_tasks.cleanup_expired_orders',
        'schedule': crontab(minute=45, hour='*/2'),  # Every 2 hours
        'args': (),
    },
}

logger.info("Celery app configured with beat schedule")
