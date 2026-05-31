"""add wallet_ledger and rate_limits tables

Revision ID: 004_wallet_ledger
Revises: 003_subscriptions_unique
Create Date: 2026-05-31

Adds tables that exist in db/schema.py ALL_TABLES but were missing from Alembic.
"""
from typing import Sequence, Union

from alembic import op

revision: str = '004_wallet_ledger'
down_revision: Union[str, None] = '003_subscriptions_unique'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
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
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS rate_limits (
            id              SERIAL PRIMARY KEY,
            key             TEXT NOT NULL,
            endpoint        TEXT NOT NULL,
            window_start    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            request_count   INTEGER DEFAULT 1,
            is_blocked      INTEGER DEFAULT 0,
            blocked_until   TIMESTAMP,
            UNIQUE(key, endpoint, window_start)
        )
    """)

    # Indexes for new tables
    op.execute('CREATE INDEX IF NOT EXISTS idx_wallet_ledger_user ON wallet_ledger(user_id)')
    op.execute('CREATE INDEX IF NOT EXISTS idx_wallet_ledger_type ON wallet_ledger(entry_type)')
    op.execute('CREATE INDEX IF NOT EXISTS idx_wallet_ledger_created ON wallet_ledger(created_at)')
    op.execute('CREATE INDEX IF NOT EXISTS idx_rate_limits_key ON rate_limits(key, endpoint)')


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS rate_limits CASCADE")
    op.execute("DROP TABLE IF EXISTS wallet_ledger CASCADE")
