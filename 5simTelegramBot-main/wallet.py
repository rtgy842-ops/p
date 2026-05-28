"""
wallet.py — Wallet Operations (Enterprise Delegation)
─────────────────────────────────────────────────
Now delegates ALL operations to WalletService + UserRepository.
No direct sqlite3 connections. Transaction-safe.
Backward-compatible API for legacy callers.
"""

import logging
from db.repositories.user_repository import UserRepository
from db.repositories.transaction_repository import TransactionRepository

logger = logging.getLogger(__name__)


class Wallet:
    """Legacy-compatible wallet using enterprise repositories."""

    def __init__(self):
        self._user_repo = UserRepository()
        self._txn_repo = TransactionRepository()

    def ensure_user_exists(self, user_id):
        """Ensure user exists in database."""
        try:
            return self._user_repo.create_if_not_exists(user_id)
        except Exception as e:
            logger.error(f"Error ensuring user {user_id}: {e}")
            return False

    def get_balance(self, user_id):
        """Get user balance via repository."""
        try:
            self.ensure_user_exists(user_id)
            return self._user_repo.get_balance(user_id)
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            return 0

    def create_wallet(self, user_id):
        """Create a wallet (user record)."""
        try:
            return self._user_repo.create_if_not_exists(user_id)
        except Exception as e:
            logger.error(f"Error creating wallet: {e}")
            return False

    def add_balance(self, user_id, amount):
        """Add balance via repository. Transaction-safe."""
        try:
            result = self._user_repo.add_balance(user_id, amount)
            if result is not None:
                self._txn_repo.create(user_id, amount, 'deposit', 'Balance increased')
                return True
            return False
        except Exception as e:
            logger.error(f"Error in add_balance: {e}")
            return False

    def reduce_balance(self, user_id, amount):
        """Deduct balance via repository. Transaction-safe."""
        try:
            result = self._user_repo.deduct_balance(user_id, amount)
            return result is not None
        except Exception as e:
            logger.error(f"Error reducing balance: {e}")
            return False

    def deduct_balance(self, user_id, amount):
        """Deduct balance for purchase. Transaction-safe."""
        try:
            result = self._user_repo.deduct_balance(user_id, amount)
            if result is not None:
                self._txn_repo.create(user_id, amount, 'purchase', 'Virtual number purchase')
                return True
            return False
        except Exception as e:
            logger.error(f"Error in deduct_balance: {e}")
            return False

    def get_wallet_info(self, user_id):
        """Get comprehensive wallet info."""
        try:
            balance = self._user_repo.get_balance(user_id)
            total_deposits = self._txn_repo.sum_by_type(user_id, 'deposit')
            total_spent = self._txn_repo.sum_by_type(user_id, 'purchase')
            last_txn = self._txn_repo.get_last_transaction_time(user_id)

            return {
                'balance': balance,
                'total_deposit': total_deposits,
                'total_spent': total_spent,
                'last_transaction': last_txn,
            }
        except Exception as e:
            logger.error(f"Error in get_wallet_info: {e}")
            return None
