"""
tasks/__init__.py — Celery Application
─────────────────────────────────────────────────
Async task queue for background processing.
Uses Redis as broker.

Tasks:
- send_notification: Queue-based notification dispatch
- emit_event: Event bus async dispatch
- process_backup: Scheduled automated backup
"""

import os
from celery import Celery

# ── Celery app ─────────────────────────────────────────────────
app = Celery(
    'smsbot',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379/0'),
)

app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Tehran',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes max per task
    task_soft_time_limit=240,  # 4 minutes soft limit
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
)


# ── Tasks ──────────────────────────────────────────────────────

@app.task(name='tasks.send_notification', bind=True, max_retries=3)
def send_notification_task(self, user_id: int, notification_type: str,
                           data: dict, channel: str = 'telegram'):
    """
    Send a notification to a user via the specified channel.
    Retries 3 times with exponential backoff on failure.
    """
    try:
        from services.notification_service import notifications, NotificationType, NotificationChannel
        ntype = NotificationType(notification_type)
        nchannel = NotificationChannel(channel)
        return notifications._send_sync(user_id, ntype, data, nchannel)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


@app.task(name='tasks.emit_event', bind=True)
def emit_event_task(self, event: str, data: dict):
    """
    Emit an event asynchronously via the EventBus.
    """
    try:
        from services.event_bus import event_bus
        event_bus.emit(event, data)
        return {'event': event, 'status': 'emitted'}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=5)
