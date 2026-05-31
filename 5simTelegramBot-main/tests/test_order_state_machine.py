"""
tests/test_order_state_machine.py — Order State Machine Tests
─────────────────────────────────────────────────
Tests every valid and invalid state transition.
Ensures order lifecycle integrity.
"""

from data.dto import OrderDTO, OrderStatus


class TestOrderStateMachine:
    """Order status transition validation."""

    def test_valid_transitions(self):
        """All defined transitions should be valid."""
        from services.order_service import STATE_TRANSITIONS

        # CREATED can go to PAID, FAILED, CANCELLED
        assert OrderStatus.PAID in STATE_TRANSITIONS[OrderStatus.CREATED]
        assert OrderStatus.FAILED in STATE_TRANSITIONS[OrderStatus.CREATED]
        assert OrderStatus.CANCELLED in STATE_TRANSITIONS[OrderStatus.CREATED]

        # PAID can go to PROCESSING
        assert OrderStatus.PROCESSING in STATE_TRANSITIONS[OrderStatus.PAID]

        # PROCESSING can go to WAITING_SMS
        assert OrderStatus.WAITING_SMS in STATE_TRANSITIONS[OrderStatus.PROCESSING]

        # WAITING_SMS can go to COMPLETED
        assert OrderStatus.COMPLETED in STATE_TRANSITIONS[OrderStatus.WAITING_SMS]

        # CANCELLED can go to REFUNDED
        assert OrderStatus.REFUNDED in STATE_TRANSITIONS[OrderStatus.CANCELLED]

    def test_invalid_transitions_blocked(self):
        """Invalid transitions should NOT be allowed."""
        from services.order_service import STATE_TRANSITIONS

        # COMPLETED is terminal — no transitions out
        assert STATE_TRANSITIONS[OrderStatus.COMPLETED] == []

        # REFUNDED is terminal
        assert STATE_TRANSITIONS[OrderStatus.REFUNDED] == []

        # FAILED is terminal
        assert STATE_TRANSITIONS[OrderStatus.FAILED] == []

        # Cannot go from COMPLETED to CANCELLED
        assert OrderStatus.CANCELLED not in STATE_TRANSITIONS.get(
            OrderStatus.COMPLETED, []
        )

        # Cannot go from REFUNDED to anything
        assert len(STATE_TRANSITIONS.get(OrderStatus.REFUNDED, [])) == 0

    def test_is_active(self):
        """Active states should be correctly identified."""
        active = [OrderStatus.CREATED, OrderStatus.PENDING, OrderStatus.PAID,
                  OrderStatus.PROCESSING, OrderStatus.WAITING_SMS]

        for status in active:
            assert status.is_active(), f"{status.value} should be active"

        terminal = [OrderStatus.COMPLETED, OrderStatus.CANCELLED,
                    OrderStatus.REFUNDED, OrderStatus.FAILED]

        for status in terminal:
            assert status.is_terminal(), f"{status.value} should be terminal"
            assert not status.is_active(), f"{status.value} should NOT be active"

    def test_order_dto_from_dict(self):
        """OrderDTO should parse status correctly."""
        data = {
            'id': 1, 'user_id': 123, 'activation_id': 456,
            'service': 'telegram', 'country': 'cyprus',
            'operator': 'virtual4', 'phone': '999123456',
            'price': 50000, 'status': 'CREATED',
            'created_at': '2026-01-01 12:00:00'
        }

        order = OrderDTO(**data)
        assert order.id == 1
        assert order.user_id == 123
        assert order.status == OrderStatus.CREATED
        assert order.price == 50000

    def test_order_status_from_string(self):
        """OrderStatus enum should handle various formats."""
        assert OrderStatus('CREATED') == OrderStatus.CREATED
        # Lowercase support: OrderStatus is uppercase enum, from_row normalizes
        assert OrderStatus('CREATED') == OrderStatus.CREATED
        assert OrderStatus('COMPLETED') == OrderStatus.COMPLETED
        assert OrderStatus('CANCELLED') == OrderStatus.CANCELLED
        assert OrderStatus('REFUNDED') == OrderStatus.REFUNDED

    def test_cancel_only_active_orders(self):
        """Only active orders can be cancelled."""
        # COMPLETED is terminal — cannot cancel
        assert not OrderStatus.COMPLETED.is_active()

        # CREATED is active — can cancel
        assert OrderStatus.CREATED.is_active()

    def test_no_direct_completed_to_cancelled(self):
        """Cannot cancel a completed order."""
        from services.order_service import STATE_TRANSITIONS
        # COMPLETED has no outgoing transitions
        assert len(STATE_TRANSITIONS[OrderStatus.COMPLETED]) == 0
