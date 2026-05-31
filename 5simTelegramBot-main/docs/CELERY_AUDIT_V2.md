# PHASE 4 — CELERY VALIDATION V2
**Date**: 2026-05-31 19:17 UTC
**Auditor**: Automated Celery Task Validation
**Scope**: `tasks/` package, Celery configuration, task discovery, broker config

---

## EXECUTIVE SUMMARY

| Metric | Value |
|--------|-------|
| Celery app import | ✅ Successful |
| Task count | 7 tasks registered |
| Periodic tasks | 5 configured |
| Broker URL | `redis://redis:6379/0` |
| Result backend | `redis://redis:6379/0` |

---

## CELERY CONFIGURATION

**Source**: [`tasks/__init__.py`](5simTelegramBot-main/tasks/__init__.py)

```python
app = Celery(
    '5simTelegramBot',
    broker='redis://redis:6379/0',
    backend='redis://redis:6379/0',
)
```

### Configuration Parameters
| Parameter | Value | Valid? |
|-----------|-------|--------|
| `task_serializer` | `json` | ✅ |
| `accept_content` | `['json']` | ✅ |
| `result_serializer` | `json` | ✅ |
| `timezone` | `Asia/Tehran` | ✅ |
| `enable_utc` | `True` | ✅ |
| `task_track_started` | `True` | ✅ |
| `task_time_limit` | 300s | ✅ |
| `task_soft_time_limit` | 240s | ✅ |
| `worker_max_tasks_per_child` | 200 | ✅ |
| `worker_prefetch_multiplier` | 1 | ✅ |

---

## TASK REGISTRY

### Periodic Tasks (Beat Schedule)

| Name | Schedule | Timeout |
|------|----------|---------|
| `tasks.sync_provider_prices` | Every 30s | 25s expires |
| `tasks.provider_health_check` | Every 60s | 55s expires |
| `tasks.full_provider_sync` | Every hour (minute 0) | 300s expires |
| `tasks.cleanup_fraud_log` | Daily 03:00 | None |
| `tasks.daily_backup` | Daily 02:00 | None |

### One-shot / On-demand Tasks

| Name | Signature | Purpose |
|------|-----------|---------|
| `tasks.send_notification` | `(user_id: int, message: str, channel: str)` | Notification dispatch |
| `tasks.emit_event` | `(event: str, data: dict)` | Async event processing |

---

## TASK DISCOVERY VERIFICATION

All tasks are defined in [`tasks/__init__.py`](5simTelegramBot-main/tasks/__init__.py) as module-level `@app.task` decorated functions. Import verification:

| Task | Import | Status |
|------|--------|--------|
| `sync_provider_prices` | `from tasks import sync_provider_prices` | ✅ |
| `provider_health_check` | `from tasks import provider_health_check` | ✅ |
| `full_provider_sync` | `from tasks import full_provider_sync` | ✅ |
| `cleanup_fraud_log` | `from tasks import cleanup_fraud_log` | ✅ |
| `daily_backup` | `from tasks import daily_backup` | ✅ |
| `send_notification` | `from tasks import send_notification` | ✅ |
| `emit_event_task` | `from tasks import emit_event_task` | ✅ |

---

## BROKER CONNECTIVITY

**No active Redis available for runtime test**. Configuration validated:
- URL format: Valid `redis://` scheme ✅
- Hostname: `redis` (Docker service name) or `localhost` (direct)
- Port: 6379
- DB: 0

---

## RETRY CONFIGURATION

Tasks do not have explicit `autoretry_for` or `max_retries` parameters. The SMS service layer handles retries at the HTTP level (in [`sms_service.py`](5simTelegramBot-main/services/sms_service.py:78-110)):
- 3 retries with exponential backoff (1s, 2s, 4s)
- 15s request timeout
- This is correct — SMS retries should NOT be at Celery task level

---

## ISSUES FOUND

### CEL1 — Missing `@app.task` decorator for health check tasks (LOW)

Both `sync_provider_prices` and `provider_health_check` are simple function calls inside their task wrappers but lack explicit retry configuration. Each task uses `@app.task(bind=True)` which is correct.

### CEL2 — `send_notification` task imports from `bot_utils` (INFO)

[`tasks/__init__.py:130`](5simTelegramBot-main/tasks/__init__.py:130) imports `from bot_utils import send_message_to_bot`. This creates a circular dependency chain: `tasks → bot_utils → bot`. The import works because `bot_utils` doesn't import from `tasks`, but it's fragile.

---

## VERDICT

**CELERY AUDIT: PASSED** — All 7 tasks importable. 5 beat schedule entries configured correctly. Broker URL valid. No broken task references.
