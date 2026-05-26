"""
services/notification_service.py — Event-Driven Notifications
─────────────────────────────────────────────────
Queue-based notification dispatcher.
Supports: Telegram, Email (future), Web Push (future).

Design:
    Event → NotificationService.dispatch() → Queue → Send
    This decouples event handling from message delivery.
"""

import logging
from enum import Enum

logger = logging.getLogger(__name__)


class NotificationChannel(str, Enum):
    TELEGRAM = 'telegram'
    EMAIL = 'email'
    PUSH = 'push'


class NotificationType(str, Enum):
    ORDER_CONFIRMED = 'order:confirmed'
    ORDER_CANCELLED = 'order:cancelled'
    SMS_RECEIVED = 'sms:received'
    PAYMENT_APPROVED = 'payment:approved'
    PAYMENT_REJECTED = 'payment:rejected'
    BALANCE_LOW = 'balance:low'
    ADMIN_ALERT = 'admin:alert'


class NotificationService:
    """
    Centralized notification dispatcher.
    All notifications flow through here — nowhere else.
    """

    def __init__(self):
        self._templates: dict[NotificationType, str] = self._load_templates()
        self._handlers: dict[NotificationChannel, callable] = {}

    def register_handler(self, channel: NotificationChannel, handler: callable) -> None:
        """Register a notification handler for a channel."""
        self._handlers[channel] = handler
        logger.info(f"Notification handler registered: {channel.value}")

    def dispatch(self, user_id: int, notification_type: NotificationType,
                 data: dict, channel: NotificationChannel = NotificationChannel.TELEGRAM) -> bool:
        """
        Dispatch a notification to a user via the specified channel.
        Queue-based: schedules via Celery, non-blocking.
        """
        try:
            # Try async dispatch via Celery
            from tasks.notifications import send_notification_task
            send_notification_task.delay(
                user_id=user_id,
                notification_type=notification_type.value,
                data=data,
                channel=channel.value,
            )
            return True
        except ImportError:
            # Fallback: synchronous dispatch
            return self._send_sync(user_id, notification_type, data, channel)

    def _send_sync(self, user_id: int, notification_type: NotificationType,
                   data: dict, channel: NotificationChannel) -> bool:
        """Synchronous fallback for when Celery is unavailable."""
        handler = self._handlers.get(channel)
        if handler is None:
            logger.warning(f"No handler for channel: {channel.value}")
            return False

        template = self._templates.get(notification_type, '')
        message = template.format(**data) if template else str(data)

        try:
            handler(user_id, message)
            return True
        except Exception as e:
            logger.error(f"Notification failed: {e}")
            return False

    def _load_templates(self) -> dict[NotificationType, str]:
        """Load notification message templates."""
        return {
            NotificationType.ORDER_CONFIRMED:
                "✅ Order confirmed!\n📱 Phone: {phone}\n🔰 Service: {service}\n💰 Price: {price} Toman",
            NotificationType.ORDER_CANCELLED:
                "❌ Order cancelled\n💰 Refund: {refund} Toman\n💎 Balance: {balance} Toman",
            NotificationType.SMS_RECEIVED:
                "📩 SMS code received!\n📱 Code: {code}\n🔰 Service: {service}",
            NotificationType.PAYMENT_APPROVED:
                "✅ Payment approved!\n💰 Amount: {amount} Toman\n💎 Balance: {balance} Toman",
            NotificationType.PAYMENT_REJECTED:
                "❌ Payment rejected\nReason: {reason}",
            NotificationType.BALANCE_LOW:
                "⚠️ Your balance is low ({balance} Toman)\n💡 Minimum: {minimum} Toman",
            NotificationType.ADMIN_ALERT:
                "🔔 Admin Alert: {message}",
        }


# ── Global instance ────────────────────────────────────────────
notifications = NotificationService()