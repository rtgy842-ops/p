"""
services/wallet_ledger.py — Double-Entry Wallet Ledger
─────────────────────────────────────────────────
Enterprise-grade wallet ledger with immutable transaction records.
Every balance change produces a ledger entry with running balance.

Supports:
- Deposit, Withdrawal, Transfer, Refund, Hold (reserved balance)
- Running balance after each entry
- Immutable record (no UPDATE on ledger entries)
- Summary reports by user, type, date range
"""

import logging
from datetime import datetime

from db.context import db_context

logger = logging.getLogger(__name__)

DB_NAME = 'default'

LEDGER_TYPES = ['deposit', 'withdrawal', 'transfer', 'refund', 'hold', 'release', 'admin_adjust']


class WalletLedger:
    """
    Append-only double-entry ledger for all balance mutations.
    Each entry records: user_id, amount, type, running_balance, description, ref_id.
    """

    @staticmethod
    def record(user_id: int, amount: int, entry_type: str,
               description: str = '', ref_id: str | None = None,
               metadata: dict | None = None) -> int | None:
        """
        Record a ledger entry and return the entry ID.
        The running_balance is calculated atomically.
        """
        import json
        if entry_type not in LEDGER_TYPES:
            raise ValueError(f"Invalid ledger type: {entry_type}")

        try:
            with db_context(DB_NAME, transactional=True) as db:
                # Lock user row and get current balance
                row = db.fetchone(
                    'SELECT balance FROM users WHERE user_id = %s FOR UPDATE',
                    (user_id,))
                current_balance = int(row[0]) if row else 0

                # Calculate new running balance
                if entry_type in ('deposit', 'refund', 'release', 'admin_adjust'):
                    direction = 1 if entry_type != 'admin_adjust' else 1
                    new_balance = current_balance + amount * direction
                elif entry_type in ('withdrawal', 'hold', 'transfer'):
                    new_balance = current_balance - amount
                else:
                    new_balance = current_balance

                # Insert ledger entry (append-only, no updates)
                meta_json = json.dumps(metadata or {})
                db.execute(
                    """INSERT INTO wallet_ledger
                       (user_id, amount, entry_type, running_balance, description, ref_id, metadata)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (user_id, amount, entry_type, new_balance, description, ref_id, meta_json))

                # Also update the actual balance
                db.execute(
                    'UPDATE users SET balance = %s WHERE user_id = %s',
                    (new_balance, user_id))

                row_id = db.fetchone("SELECT lastval()")
                return int(row_id[0]) if row_id else None
        except Exception as e:
            logger.error(f"Ledger record failed for user {user_id}: {e}")
            return None

    @staticmethod
    def get_entries(user_id: int, limit: int = 50,
                    offset: int = 0, entry_type: str | None = None) -> list[dict]:
        """Get ledger entries for a user."""
        try:
            where = "WHERE user_id = %s"
            params = [user_id]
            if entry_type:
                where += " AND entry_type = %s"
                params.append(entry_type)

            with db_context(DB_NAME, transactional=False) as db:
                rows = db.fetchall(
                    f"""SELECT id, amount, entry_type, running_balance, description, ref_id, created_at
                        FROM wallet_ledger {where}
                        ORDER BY created_at DESC LIMIT %s OFFSET %s""",
                    params + [limit, offset])
                return [
                    {'id': r[0], 'amount': int(r[1]), 'type': r[2],
                     'balance': int(r[3]), 'description': r[4],
                     'ref_id': r[5], 'created_at': str(r[6])}
                    for r in rows
                ]
        except Exception as e:
            logger.error(f"Ledger get_entries error: {e}")
            return []

    @staticmethod
    def get_balance_at(user_id: int, timestamp: datetime) -> int:
        """Get balance at a specific point in time."""
        try:
            with db_context(DB_NAME, transactional=False) as db:
                row = db.fetchone(
                    """SELECT running_balance FROM wallet_ledger
                       WHERE user_id = %s AND created_at <= %s
                       ORDER BY created_at DESC LIMIT 1""",
                    (user_id, timestamp))
                return int(row[0]) if row else 0
        except Exception:
            return 0

    @staticmethod
    def get_summary(user_id: int) -> dict:
        """Get ledger summary: total deposits, withdrawals, current balance."""
        try:
            with db_context(DB_NAME, transactional=False) as db:
                deposits = db.fetchone(
                    "SELECT COALESCE(SUM(amount),0) FROM wallet_ledger WHERE user_id=%s AND entry_type='deposit'",
                    (user_id,))
                withdrawals = db.fetchone(
                    "SELECT COALESCE(SUM(amount),0) FROM wallet_ledger WHERE user_id=%s AND entry_type='withdrawal'",
                    (user_id,))
                refunds = db.fetchone(
                    "SELECT COALESCE(SUM(amount),0) FROM wallet_ledger WHERE user_id=%s AND entry_type='refund'",
                    (user_id,))
                balance = db.fetchone(
                    'SELECT balance FROM users WHERE user_id = %s', (user_id,))
            return {
                'total_deposits': int(deposits[0]) if deposits else 0,
                'total_withdrawals': int(withdrawals[0]) if withdrawals else 0,
                'total_refunds': int(refunds[0]) if refunds else 0,
                'current_balance': int(balance[0]) if balance else 0,
            }
        except Exception as e:
            logger.error(f"Ledger summary error: {e}")
            return {'total_deposits': 0, 'total_withdrawals': 0,
                    'total_refunds': 0, 'current_balance': 0}


# ── Ensure wallet_ledger table exists ──
WALLET_LEDGER_DDL = """
CREATE TABLE IF NOT EXISTS wallet_ledger (
    id              SERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(user_id),
    amount          INTEGER NOT NULL CHECK (amount >= 0),
    entry_type      TEXT NOT NULL,
    running_balance INTEGER NOT NULL,
    description     TEXT DEFAULT '',
    ref_id          TEXT,
    metadata        TEXT DEFAULT '{}',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_wallet_ledger_user ON wallet_ledger(user_id);
CREATE INDEX IF NOT EXISTS idx_wallet_ledger_type ON wallet_ledger(entry_type);
CREATE INDEX IF NOT EXISTS idx_wallet_ledger_created ON wallet_ledger(created_at);
"""
