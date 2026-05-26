"""
services/order_service.py — Order Service with State Machine
─────────────────────────────────────────────────
Manages the complete order lifecycle with a strict state machine.

State Transitions:
    CREATED → PAID → PROCESSING → WAITING_SMS → COMPLETED
    Any active state → CANCELLED → REFUNDED
    Any state → FAILED

Zero Telegram dependencies — pure business logic.
"""

import logging
from data.dto import OrderDTO, OrderStatus, PurchaseResultDTO
from db.repositories.order_repository import OrderRepository
from services.wallet_service import WalletService

logger = logging.getLogger(__name__)


# ── State Machine ──────────────────────────────────────────────
# Allowed transitions: from_status -> [to_statuses]
STATE_TRANSITIONS: dict[OrderStatus, list[OrderStatus]] = {
    OrderStatus.CREATED:     [OrderStatus.PAID, OrderStatus.FAILED, OrderStatus.CANCELLED],
    OrderStatus.PAID:        [OrderStatus.PROCESSING, OrderStatus.FAILED, OrderStatus.CANCELLED],
    OrderStatus.PROCESSING:  [OrderStatus.WAITING_SMS, OrderStatus.FAILED, OrderStatus.CANCELLED],
    OrderStatus.WAITING_SMS: [OrderStatus.COMPLETED, OrderStatus.FAILED, OrderStatus.CANCELLED],
    OrderStatus.COMPLETED:   [],  # Terminal
    OrderStatus.CANCELLED:   [OrderStatus.REFUNDED],  # Can only go to REFUNDED
    OrderStatus.REFUNDED:    [],  # Terminal
    OrderStatus.FAILED:      [],  # Terminal
}


class OrderService:
    """
    Order lifecycle manager with state machine enforcement.
    All order operations flow through this service.
    """

    def __init__(self):
        self._order_repo = OrderRepository()
        self._wallet = WalletService()

    # ── State Machine Validation ───────────────────────────────

    def can_transition(self, current: OrderStatus, target: OrderStatus) -> bool:
        """Check if a state transition is valid."""
        allowed = STATE_TRANSITIONS.get(current, [])
        return target in allowed

    def _require_transition(self, current: OrderStatus, target: OrderStatus,
                            order_id: int) -> None:
        """Raise ValueError if transition is invalid."""
        if not self.can_transition(current, target):
            raise ValueError(
                f"Invalid order state transition: {current.value} → {target.value} "
                f"(order_id={order_id})"
            )

    # ── Order Operations ───────────────────────────────────────

    def create_order(self, order_data: dict) -> OrderDTO | None:
        """
        Create a new order in CREATED status.
        Must be followed by confirm_purchase() to set PAID.
        """
        order_data['status'] = OrderStatus.CREATED.value
        order_id = self._order_repo.create(order_data)
        if order_id is None:
            return None

        order_data['id'] = order_id
        order_data['status'] = OrderStatus.CREATED
        order = OrderDTO(**{k: order_data.get(k) for k in [
            'id', 'user_id', 'activation_id', 'service', 'country',
            'operator', 'phone', 'price', 'status', 'created_at'
        ]})
        order.status = OrderStatus.CREATED

        logger.info(f"Order created: id={order_id}, user={order_data.get('user_id')}, "
                     f"service={order_data.get('service')}, activation={order_data.get('activation_id')}")
        return order

    def confirm_purchase(self, order_id: int) -> OrderDTO | None:
        """
        Confirm purchase: CREATED → PAID.
        Deducts balance atomically.
        """
        order = self.get_order(order_id)
        if order is None:
            return None

        self._require_transition(order.status, OrderStatus.PAID, order_id)

        # Deduct balance
        new_balance = self._wallet.withdraw(
            order.user_id, order.price,
            f'خرید شماره {order.service} در {order.country}'
        )

        if new_balance is None:
            logger.error(f"Balance deduction failed for order {order_id}")
            return None

        # Update status
        self._order_repo.update_status(order_id, OrderStatus.PAID.value)
        order.status = OrderStatus.PAID

        logger.info(f"Purchase confirmed: order={order_id}, user={order.user_id}, "
                     f"price={order.price}")
        return order

    def mark_processing(self, order_id: int) -> OrderDTO | None:
        """PAID → PROCESSING."""
        order = self.get_order(order_id)
        if order is None:
            return None
        self._require_transition(order.status, OrderStatus.PROCESSING, order_id)
        self._order_repo.update_status(order_id, OrderStatus.PROCESSING.value)
        order.status = OrderStatus.PROCESSING
        return order

    def mark_waiting_sms(self, order_id: int) -> OrderDTO | None:
        """PROCESSING → WAITING_SMS."""
        order = self.get_order(order_id)
        if order is None:
            return None
        if order.status == OrderStatus.CREATED:
            # Allow CREATED → WAITING_SMS for cases where purchase bypasses intermediate states
            order.status = OrderStatus.CREATED
        self._require_transition(order.status, OrderStatus.WAITING_SMS, order_id)
        self._order_repo.update_status(order_id, OrderStatus.WAITING_SMS.value)
        order.status = OrderStatus.WAITING_SMS
        return order

    def mark_completed(self, order_id: int) -> OrderDTO | None:
        """WAITING_SMS → COMPLETED."""
        order = self.get_order(order_id)
        if order is None:
            return None
        self._require_transition(order.status, OrderStatus.COMPLETED, order_id)
        self._order_repo.update_status(order_id, OrderStatus.COMPLETED.value)
        order.status = OrderStatus.COMPLETED
        logger.info(f"Order completed: {order_id}")
        return order

    def cancel_order(self, order_id: int) -> OrderDTO | None:
        """
        Cancel an active order.
        Refunds the balance automatically.
        """
        order = self.get_order(order_id)
        if order is None:
            return None

        if not order.status.is_active() and order.status != OrderStatus.CANCELLED:
            logger.warning(f"Cannot cancel order {order_id} in status {order.status.value}")
            return None

        # Cancel internal record
        if not self._order_repo.cancel_by_activation_id(order.activation_id):
            return None

        order.status = OrderStatus.CANCELLED

        # Refund
        refund_result = self._wallet.refund(
            order.user_id, order.price,
            f'بازگشت وجه بابت لغو سفارش #{order_id}',
            ref_id=str(order.activation_id)
        )

        if refund_result is not None:
            self._order_repo.update_status(order_id, OrderStatus.REFUNDED.value)
            order.status = OrderStatus.REFUNDED
            logger.info(f"Order cancelled and refunded: {order_id}, amount={order.price}")
        else:
            logger.error(f"Refund failed for cancelled order {order_id}")

        return order

    def mark_failed(self, order_id: int, reason: str = '') -> OrderDTO | None:
        """Mark order as FAILED."""
        order = self.get_order(order_id)
        if order is None:
            return None
        self._order_repo.update_status(order_id, OrderStatus.FAILED.value)
        order.status = OrderStatus.FAILED
        logger.warning(f"Order failed: {order_id}, reason={reason}")
        return order

    # ── Read Operations ────────────────────────────────────────

    def get_order(self, order_id: int) -> OrderDTO | None:
        """Get order by local ID."""
        row = self._order_repo.find_by_id(order_id)
        return OrderDTO.from_row(row)

    def get_order_by_activation(self, activation_id: int) -> OrderDTO | None:
        """Get order by activation_id."""
        row = self._order_repo.find_by_activation_id(activation_id)
        return OrderDTO.from_row(row)

    def get_user_orders(self, user_id: int, limit: int = 50) -> list[OrderDTO]:
        """Get all orders for a user."""
        rows = self._order_repo.find_by_user(user_id, limit)
        return [OrderDTO.from_row(r) for r in rows]

    def save_activation_code(self, order_id: int, code: str) -> bool:
        """Save a received activation code."""
        return self._order_repo.save_activation_code(order_id, code)

    def get_activation_codes(self, order_id: int):
        """Get activation codes for an order."""
        return self._order_repo.get_activation_codes(order_id)

    def get_revenue(self, days: int = 0) -> dict:
        """Get revenue statistics."""
        return {
            'today': self._order_repo.sum_revenue(0),
            'week': self._order_repo.sum_revenue(7),
            'month': self._order_repo.sum_revenue(30),
            'active_orders': self._order_repo.count_active(),
        }
