"""
services/wallet_service.py — Wallet Service (Atomic Transactions)
─────────────────────────────────────────────────
THE single source of truth for ALL balance operations.
Every balance change MUST pass through this service.

Features:
- Deposit, withdraw, refund — ALL atomic via single PG transaction
- SELECT ... FOR UPDATE row locking to prevent race conditions
- Balance + transaction log committed together or rolled back together
- Audit trail preparation
- Fraud check hooks (extensible)

Zero Telegram dependencies — pure business logic.
"""

import logging

from db.context import db_context

logger = logging.getLogger(__name__)


class WalletService:
    """
    Centralized wallet management with atomic PostgreSQL transactions.
    
    CRITICAL: Every balance mutation uses a SINGLE DatabaseContext
    transaction that encompasses BOTH the row lock + balance update
    AND the transaction log insertion. If either fails, both roll back.
    """

    DB_NAME = 'default'

    # ── Balance Inquiry (read-only, no transaction needed) ─────

    @staticmethod
    def get_balance(user_id: int) -> int:
        """Get current balance. Returns 0 if user doesn't exist."""
        try:
            with db_context(WalletService.DB_NAME, transactional=False) as db:
                row = db.fetchone('SELECT balance FROM users WHERE user_id = %s', (user_id,))
                return int(row[0]) if row else 0
        except Exception as e:
            logger.error(f"get_balance error for {user_id}: {e}")
            return 0

    def get_wallet_info(self, user_id: int) -> dict:
        """Get complete wallet information."""
        try:
            with db_context(self.DB_NAME, transactional=False) as db:
                row = db.fetchone('SELECT balance FROM users WHERE user_id = %s', (user_id,))
                balance = int(row[0]) if row else 0
                dep_row = db.fetchone(
                    "SELECT COALESCE(SUM(amount),0) FROM transactions WHERE user_id=%s AND type='deposit'",
                    (user_id,))
                spent_row = db.fetchone(
                    "SELECT COALESCE(SUM(amount),0) FROM transactions WHERE user_id=%s AND type='purchase'",
                    (user_id,))
                last_row = db.fetchone(
                    "SELECT timestamp FROM transactions WHERE user_id=%s ORDER BY timestamp DESC LIMIT 1",
                    (user_id,))
                return {
                    'balance': balance,
                    'total_deposits': int(dep_row[0]) if dep_row else 0,
                    'total_spent': int(spent_row[0]) if spent_row else 0,
                    'last_transaction': str(last_row[0]) if last_row and last_row[0] else None,
                }
        except Exception as e:
            logger.error(f"get_wallet_info error for {user_id}: {e}")
            return {'balance': 0, 'total_deposits': 0, 'total_spent': 0, 'last_transaction': None}

    def has_sufficient_balance(self, user_id: int, amount: int) -> bool:
        """Check if user has enough balance for a purchase."""
        return self.get_balance(user_id) >= amount

    # ── Atomic Balance Operations ──────────────────────────────

    def deposit(self, user_id: int, amount: int, description: str = '',
                ref_id: str | None = None) -> int | None:
        """
        Add funds to user wallet.
        
        ATOMIC: SELECT...FOR UPDATE → UPDATE balance → INSERT transaction
        all in one PostgreSQL transaction.
        """
        if amount <= 0:
            logger.warning(f"Invalid deposit amount: {amount} for user {user_id}")
            return None

        try:
            with db_context(self.DB_NAME, transactional=True) as db:
                # Lock row to prevent concurrent modifications
                row = db.fetchone(
                    'SELECT balance FROM users WHERE user_id = %s FOR UPDATE', (user_id,))
                if row is None:
                    db.execute(
                        'INSERT INTO users (user_id, balance) VALUES (%s, %s) ON CONFLICT DO NOTHING',
                        (user_id, max(amount, 0)))
                    new_balance = max(amount, 0)
                else:
                    new_balance = int(row[0]) + amount
                    if new_balance < 0:
                        return None
                    db.execute(
                        'UPDATE users SET balance = %s WHERE user_id = %s',
                        (new_balance, user_id))

                # Insert transaction log + wallet_ledger in same transaction
                db.execute(
                    """INSERT INTO transactions (user_id, amount, type, description, ref_id)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (user_id, amount, 'deposit',
                     description or 'deposit', ref_id))
                db.execute(
                    """INSERT INTO wallet_ledger (user_id, amount, entry_type, running_balance, description, ref_id)
                       VALUES (%s, %s, 'deposit', %s, %s, %s)""",
                    (user_id, amount, new_balance, description or 'deposit', ref_id))

            logger.info(f"Deposit: user={user_id}, amount={amount}, new_balance={new_balance}")
            return new_balance
        except Exception as e:
            logger.error(f"Deposit failed: user={user_id}, amount={amount}: {e}")
            return None

    def withdraw(self, user_id: int, amount: int, description: str = '') -> int | None:
        """
        Deduct funds for a purchase.
        
        ATOMIC: SELECT...FOR UPDATE → check balance → UPDATE balance → INSERT transaction
        """
        if amount <= 0:
            return None

        try:
            with db_context(self.DB_NAME, transactional=True) as db:
                # Lock row to prevent race conditions
                row = db.fetchone(
                    'SELECT balance FROM users WHERE user_id = %s FOR UPDATE', (user_id,))
                if row is None or int(row[0]) < amount:
                    logger.warning(
                        f"Withdraw failed: user={user_id}, amount={amount} (insufficient)")
                    return None

                new_balance = int(row[0]) - amount
                db.execute(
                    'UPDATE users SET balance = %s WHERE user_id = %s',
                    (new_balance, user_id))

                # Insert transaction log in same transaction
                db.execute(
                    """INSERT INTO transactions (user_id, amount, type, description)
                       VALUES (%s, %s, %s, %s)""",
                    (user_id, amount, 'purchase',
                     description or 'خرید شماره مجازی'))

            logger.info(
                f"Withdraw: user={user_id}, amount={amount}, new_balance={new_balance}")
            return new_balance
        except Exception as e:
            logger.error(f"Withdraw failed: user={user_id}, amount={amount}: {e}")
            return None

    def refund(self, user_id: int, amount: int, description: str = '',
               ref_id: str | None = None) -> int | None:
        """
        Refund money to user (e.g., order cancellation).
        
        ATOMIC: SELECT...FOR UPDATE → UPDATE balance → INSERT transaction
        """
        if amount <= 0:
            return None

        try:
            with db_context(self.DB_NAME, transactional=True) as db:
                row = db.fetchone(
                    'SELECT balance FROM users WHERE user_id = %s FOR UPDATE', (user_id,))
                if row is None:
                    db.execute(
                        'INSERT INTO users (user_id, balance) VALUES (%s, %s) ON CONFLICT DO NOTHING',
                        (user_id, amount))
                    new_balance = amount
                else:
                    new_balance = int(row[0]) + amount
                    db.execute(
                        'UPDATE users SET balance = %s WHERE user_id = %s',
                        (new_balance, user_id))

                db.execute(
                    """INSERT INTO transactions (user_id, amount, type, description, ref_id)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (user_id, amount, 'refund',
                     description or 'بازگشت وجه بابت لغو سفارش', ref_id))

            logger.info(
                f"Refund: user={user_id}, amount={amount}, new_balance={new_balance}")
            return new_balance
        except Exception as e:
            logger.error(f"Refund failed: user={user_id}, amount={amount}: {e}")
            return None

    def admin_add_balance(self, user_id: int, amount: int, admin_id: int) -> int | None:
        """Admin manually adds balance to a user. Atomic + audited."""
        if amount <= 0:
            return None
        try:
            with db_context(self.DB_NAME, transactional=True) as db:
                row = db.fetchone(
                    'SELECT balance FROM users WHERE user_id = %s FOR UPDATE', (user_id,))
                if row is None:
                    db.execute(
                        'INSERT INTO users (user_id, balance) VALUES (%s, %s) ON CONFLICT DO NOTHING',
                        (user_id, amount))
                    new_balance = amount
                else:
                    new_balance = int(row[0]) + amount
                    db.execute(
                        'UPDATE users SET balance = %s WHERE user_id = %s',
                        (new_balance, user_id))

                db.execute(
                    """INSERT INTO transactions (user_id, amount, type, description)
                       VALUES (%s, %s, %s, %s)""",
                    (user_id, amount, 'admin_add',
                     f'Admin {admin_id} added balance'))

                # Also write to audit_log in same transaction
                db.execute(
                    """INSERT INTO audit_log (admin_id, action, target, details, created_at)
                       VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)""",
                    (admin_id, 'admin_add_balance', str(user_id),
                     f'Added {amount} to user {user_id}'))

            return new_balance
        except Exception as e:
            logger.error(f"admin_add_balance failed: {e}")
            return None

    def admin_deduct_balance(self, user_id: int, amount: int, admin_id: int) -> int | None:
        """Admin manually deducts balance from a user. Atomic + audited."""
        if amount <= 0:
            return None
        try:
            with db_context(self.DB_NAME, transactional=True) as db:
                row = db.fetchone(
                    'SELECT balance FROM users WHERE user_id = %s FOR UPDATE', (user_id,))
                if row is None or int(row[0]) < amount:
                    return None

                new_balance = int(row[0]) - amount
                db.execute(
                    'UPDATE users SET balance = %s WHERE user_id = %s',
                    (new_balance, user_id))

                db.execute(
                    """INSERT INTO transactions (user_id, amount, type, description)
                       VALUES (%s, %s, %s, %s)""",
                    (user_id, amount, 'admin_deduct',
                     f'Admin {admin_id} deducted balance'))

                db.execute(
                    """INSERT INTO audit_log (admin_id, action, target, details, created_at)
                       VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)""",
                    (admin_id, 'admin_deduct_balance', str(user_id),
                     f'Deducted {amount} from user {user_id}'))

            return new_balance
        except Exception as e:
            logger.error(f"admin_deduct_balance failed: {e}")
            return None
