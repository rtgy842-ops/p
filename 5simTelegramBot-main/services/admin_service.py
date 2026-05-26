"""
services/admin_service.py — Admin Service (Security Boundary)
─────────────────────────────────────────────────
ALL admin operations must pass through this service.
Provides:
- Permission checks
- Audit logging for sensitive operations
- Settings management
- Channel management
- User management (ban, balance edit)
- Broadcast coordination
- Statistics aggregation

Zero Telegram dependencies — pure business logic.
"""

import logging
from datetime import datetime
from data.dto import OrderStatus
from db.repositories.settings_repository import SettingsRepository
from db.repositories.user_repository import UserRepository
from db.repositories.order_repository import OrderRepository
from db.repositories.transaction_repository import TransactionRepository
from db.repositories.card_payment_repository import CardPaymentRepository
from services.wallet_service import WalletService
from services.order_service import OrderService

logger = logging.getLogger(__name__)

# ── Audit log ──────────────────────────────────────────────────
_audit_log: list[dict] = []  # In-memory for now; will be DB-backed later


def _audit(action: str, admin_id: int, target: str = '', details: str = '') -> None:
    """Record an audit entry for sensitive admin actions."""
    entry = {
        'timestamp': datetime.now().isoformat(),
        'admin_id': admin_id,
        'action': action,
        'target': target,
        'details': details,
    }
    _audit_log.append(entry)
    logger.info(f"AUDIT: admin={admin_id} action={action} target={target} {details}")


class AdminService:
    """
    Security boundary for ALL admin operations.
    No admin action bypasses this layer.
    """

    def __init__(self):
        self._settings_repo = SettingsRepository()
        self._user_repo = UserRepository()
        self._order_repo = OrderRepository()
        self._txn_repo = TransactionRepository()
        self._card_repo = CardPaymentRepository()
        self._wallet = WalletService()
        self._order_service = OrderService()

    # ── Permission Check ───────────────────────────────────────

    def is_admin(self, user_id: int, admin_ids: list[int]) -> bool:
        """Check if a user is an admin."""
        return user_id in admin_ids

    # ── Settings Management ────────────────────────────────────

    def get_setting(self, key: str) -> str | None:
        return self._settings_repo.get(key)

    def set_setting(self, key: str, value: str, admin_id: int) -> bool:
        _audit('set_setting', admin_id, key, f'value={value}')
        return self._settings_repo.set(key, value)

    def get_usd_rate(self) -> float:
        val = self._settings_repo.get('usd_rate')
        try:
            return float(val) if val else 0.0
        except ValueError:
            return 0.0

    def set_usd_rate(self, rate: float, admin_id: int) -> bool:
        _audit('set_usd_rate', admin_id, '', str(rate))
        return self._settings_repo.set('usd_rate', str(rate))

    def get_profit_percentage(self) -> float:
        val = self._settings_repo.get('profit_percentage')
        try:
            return float(val) if val else 30.0
        except ValueError:
            return 30.0

    def set_profit_percentage(self, pct: float, admin_id: int) -> bool:
        _audit('set_profit', admin_id, '', str(pct))
        return self._settings_repo.set('profit_percentage', str(pct))

    # ── Channel Management ─────────────────────────────────────

    def get_required_channels(self):
        return self._settings_repo.get_required_channels()

    def add_channel(self, username: str, display_name: str,
                    invite_link: str, admin_id: int) -> bool:
        _audit('add_channel', admin_id, username)
        return self._settings_repo.add_channel(username, display_name, invite_link)

    def remove_channel(self, username: str, admin_id: int) -> bool:
        _audit('remove_channel', admin_id, username)
        return self._settings_repo.remove_channel(username)

    def get_lock_status(self) -> bool:
        val = self._settings_repo.get('channel_lock')
        return val.lower() == 'true' if val else False

    def set_lock_status(self, locked: bool, admin_id: int) -> bool:
        _audit('toggle_lock', admin_id, '', str(locked))
        return self._settings_repo.set('channel_lock', str(locked).lower())

    # ── Operator Management ────────────────────────────────────

    def get_operator(self, service: str, country: str):
        return self._settings_repo.get_operator(service, country)

    def set_operator(self, service: str, country: str, operator: str,
                     country_name: str, admin_id: int) -> bool:
        _audit('set_operator', admin_id, f'{service}/{country}', operator)
        return self._settings_repo.set_operator(service, country, operator, country_name)

    def get_all_operators(self):
        return self._settings_repo.get_all_operators()

    # ── Card Info Management ───────────────────────────────────

    def get_card_info(self):
        return self._settings_repo.get_card_info()

    def set_card_info(self, card_number: str, card_holder: str,
                      admin_id: int) -> bool:
        _audit('set_card_info', admin_id, '', card_number[:6] + '...')
        return self._settings_repo.set_card_info(card_number, card_holder)

    # ── User Management (Sensitive) ────────────────────────────

    def get_user(self, user_id: int):
        return self._user_repo.find_by_id(user_id)

    def search_user(self, term: str):
        return self._user_repo.find_by_id_like(term)

    def add_balance(self, user_id: int, amount: int, admin_id: int) -> int | None:
        """Admin adds balance to a user. AUDITED."""
        _audit('add_balance', admin_id, str(user_id), f'amount={amount}')
        return self._wallet.admin_add_balance(user_id, amount, admin_id)

    def reduce_balance(self, user_id: int, amount: int, admin_id: int) -> int | None:
        """Admin reduces user balance. AUDITED."""
        _audit('reduce_balance', admin_id, str(user_id), f'amount={amount}')
        return self._wallet.admin_deduct_balance(user_id, amount, admin_id)

    def set_blocked(self, user_id: int, blocked: bool, admin_id: int) -> bool:
        """Ban or unban a user. AUDITED."""
        _audit('set_blocked', admin_id, str(user_id), str(blocked))
        return self._user_repo.set_blocked(user_id, blocked)

    # ── Statistics ─────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Aggregated statistics for admin dashboard."""
        total_users = self._user_repo.count_all()
        revenue = self._order_service.get_revenue()
        usd_rate = self.get_usd_rate()
        profit = self.get_profit_percentage()

        today_income = revenue['today']
        if profit > 0:
            today_profit = int(today_income - (today_income / (1 + profit / 100)))
        else:
            today_profit = 0

        return {
            'total_users': total_users,
            'usd_rate': usd_rate,
            'profit_percentage': profit,
            'today_revenue': revenue['today'],
            'week_revenue': revenue['week'],
            'month_revenue': revenue['month'],
            'today_profit': today_profit,
            'active_orders': revenue['active_orders'],
        }

    # ── Transactions View ──────────────────────────────────────

    def get_recent_transactions(self, limit: int = 10):
        return self._txn_repo.find_recent(limit)

    def get_card_payments(self, offset: int = 0, limit: int = 5):
        return self._card_repo.list_paginated(offset, limit)

    def approve_payment(self, payment_id: str, admin_id: int) -> bool:
        """Approve a card payment. AUDITED."""
        _audit('approve_payment', admin_id, payment_id)
        success, _ = self._card_repo.approve(payment_id, admin_id)
        return success

    def reject_payment(self, payment_id: str, reason: str, admin_id: int) -> bool:
        """Reject a card payment. AUDITED."""
        _audit('reject_payment', admin_id, payment_id, reason)
        return self._card_repo.reject(payment_id, reason)

    # ── Audit ──────────────────────────────────────────────────

    def get_audit_log(self, limit: int = 50) -> list[dict]:
        """Return recent audit entries."""
        return _audit_log[-limit:]
