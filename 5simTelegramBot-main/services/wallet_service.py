"""
services/wallet_service.py — Wallet Service
─────────────────────────────────────────────────
THE single source of truth for ALL balance operations.
Every balance change MUST pass through this service.

Features:
- Deposit, withdraw, refund
- Balance inquiry
- Transaction recording
- Audit trail preparation
- Fraud check hooks (extensible)

Zero Telegram dependencies — pure business logic.
"""

import logging
from db.repositories.user_repository import UserRepository
from db.repositories.transaction_repository import TransactionRepository

logger = logging.getLogger(__name__)


class WalletService:
    """
    Centralized wallet management.
    No balance change anywhere else in the system.
    """

    def __init__(self):
        self._user_repo = UserRepository()
        self._txn_repo = TransactionRepository()

    # ── Balance Inquiry ────────────────────────────────────────

    def get_balance(self, user_id: int) -> int:
        """Get current balance. Returns 0 if user doesn't exist."""
        return self._user_repo.get_balance(user_id)

    def get_wallet_info(self, user_id: int) -> dict:
        """
        Get complete wallet information:
        balance, total deposits, total spent, last transaction time.
        """
        balance = self._user_repo.get_balance(user_id)
        total_deposits = self._txn_repo.sum_by_type(user_id, 'deposit')
        total_spent = self._txn_repo.sum_by_type(user_id, 'purchase')
        last_txn = self._txn_repo.get_last_transaction_time(user_id)

        return {
            'balance': balance,
            'total_deposits': total_deposits,
            'total_spent': total_spent,
            'last_transaction': last_txn,
        }

    def has_sufficient_balance(self, user_id: int, amount: int) -> bool:
        """Check if user has enough balance for a purchase."""
        return self.get_balance(user_id) >= amount

    # ── Balance Operations ─────────────────────────────────────

    def deposit(self, user_id: int, amount: int, description: str = '',
                ref_id: str | None = None) -> int | None:
        """
        Add funds to user wallet.
        
        Returns new balance or None on failure.
        TRANSACTION-SAFE — atomic balance + transaction log.
        """
        if amount <= 0:
            logger.warning(f"Invalid deposit amount: {amount} for user {user_id}")
            return None

        new_balance = self._user_repo.add_balance(user_id, amount)
        if new_balance is None:
            return None

        self._txn_repo.create(
            user_id=user_id,
            amount=amount,
            type_trans='deposit',
            description=description or 'افزایش موجودی',
            ref_id=ref_id,
        )

        logger.info(f"Deposit: user={user_id}, amount={amount}, new_balance={new_balance}")
        return new_balance

    def withdraw(self, user_id: int, amount: int, description: str = '') -> int | None:
        """
        Deduct funds for a purchase. Checks balance first.
        
        Returns new balance or None if insufficient funds.
        TRANSACTION-SAFE.
        """
        if amount <= 0:
            return None

        new_balance = self._user_repo.deduct_balance(user_id, amount)
        if new_balance is None:
            logger.warning(f"Withdraw failed: user={user_id}, amount={amount} (insufficient)")
            return None

        self._txn_repo.create(
            user_id=user_id,
            amount=amount,
            type_trans='purchase',
            description=description or 'خرید شماره مجازی',
        )

        logger.info(f"Withdraw: user={user_id}, amount={amount}, new_balance={new_balance}")
        return new_balance

    def refund(self, user_id: int, amount: int, description: str = '',
               ref_id: str | None = None) -> int | None:
        """
        Refund money to user (e.g., order cancellation).
        
        Returns new balance or None on failure.
        TRANSACTION-SAFE.
        """
        if amount <= 0:
            return None

        new_balance = self._user_repo.refund_balance(user_id, amount)
        if new_balance is None:
            return None

        self._txn_repo.create(
            user_id=user_id,
            amount=amount,
            type_trans='refund',
            description=description or 'بازگشت وجه بابت لغو سفارش',
            ref_id=ref_id,
        )

        logger.info(f"Refund: user={user_id}, amount={amount}, new_balance={new_balance}")
        return new_balance

    def admin_add_balance(self, user_id: int, amount: int, admin_id: int) -> int | None:
        """
        Admin manually adds balance to a user.
        Audited separately.
        """
        new_balance = self._user_repo.add_balance(user_id, amount)
        if new_balance is None:
            return None

        self._txn_repo.create(
            user_id=user_id,
            amount=amount,
            type_trans='admin_add',
            description=f'Admin {admin_id} added balance',
        )
        return new_balance

    def admin_deduct_balance(self, user_id: int, amount: int, admin_id: int) -> int | None:
        """Admin manually deducts balance from a user."""
        new_balance = self._user_repo.deduct_balance(user_id, amount)
        if new_balance is None:
            return None

        self._txn_repo.create(
            user_id=user_id,
            amount=amount,
            type_trans='admin_deduct',
            description=f'Admin {admin_id} deducted balance',
        )
        return new_balance
