"""add subscriptions UNIQUE(user_id) constraint

Revision ID: 003_subscriptions_unique
Revises: 002_constraints
Create Date: 2026-05-31

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers
revision: str = '003_subscriptions_unique'
down_revision: Union[str, None] = '002_constraints'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add UNIQUE(user_id) constraint on subscriptions table for ON CONFLICT support."""
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_subscriptions_user_id'
            ) THEN
                ALTER TABLE subscriptions ADD CONSTRAINT uq_subscriptions_user_id UNIQUE(user_id);
            END IF;
        END $$;
    """)


def downgrade() -> None:
    """Remove the UNIQUE constraint."""
    op.execute("ALTER TABLE IF EXISTS subscriptions DROP CONSTRAINT IF EXISTS uq_subscriptions_user_id")
