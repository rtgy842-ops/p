"""
services/event_bus.py — Internal Event Bus
─────────────────────────────────────────────────
Lightweight publish/subscribe event system.
Prepares the codebase for event-driven architecture.

Events:
    order:created
    order:cancelled
    order:completed
    payment:verified
    payment:rejected
    sms:received
    user:registered
    user:banned
    balance:changed

Usage:
    from services.event_bus import event_bus
    
    @event_bus.on('order:created')
    def on_order_created(data): ...
    
    event_bus.emit('order:created', {'order_id': 123})
"""

import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class EventBus:
    """
    In-process event bus. Replaceable with Redis pub/sub or Kafka later.
    """

    def __init__(self):
        self._subscribers: dict[str, list[callable]] = defaultdict(list)

    def on(self, event: str):
        """Decorator to subscribe to an event."""
        def decorator(func):
            self._subscribers[event].append(func)
            logger.debug(f"Subscribed: {func.__name__} → {event}")
            return func
        return decorator

    def emit(self, event: str, data: dict | None = None) -> None:
        """
        Publish an event to all subscribers.
        Errors in one subscriber do not affect others.
        """
        if data is None:
            data = {}

        subscribers = self._subscribers.get(event, [])
        if not subscribers:
            return

        logger.debug(f"Event: {event} → {len(subscribers)} subscribers")

        for handler in subscribers:
            try:
                handler(data)
            except Exception as e:
                logger.error(
                    f"Event handler error: {handler.__name__} for '{event}': {e}"
                )

    def emit_async(self, event: str, data: dict | None = None) -> None:
        """
        Emit event asynchronously (via Celery task).
        Non-blocking — schedules and returns immediately.
        """
        try:
            from tasks import emit_event_task
            emit_event_task.delay(event, data or {})
        except ImportError:
            # Fallback to sync if Celery not available
            self.emit(event, data)


# ── Global instance ────────────────────────────────────────────
event_bus = EventBus()

# ── Built-in event subscribers ─────────────────────────────────

@event_bus.on('order:created')
def _log_order_created(data: dict):
    logger.info(f"Order created: {data.get('order_id')}")

@event_bus.on('payment:verified')
def _log_payment_verified(data: dict):
    logger.info(f"Payment verified: user={data.get('user_id')}, amount={data.get('amount')}")

@event_bus.on('user:banned')
def _log_user_banned(data: dict):
    logger.info(f"User banned: {data.get('user_id')}, by={data.get('admin_id')}")
