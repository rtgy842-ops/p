"""${message}

Revision ID: 002_constraints
Revises: 001_initial
Create Date: 2026-05-31

Add missing constraints, indexes, and unique checks for enterprise-grade data integrity.
"""
from typing import Sequence, Union
from alembic import op

revision: str = '002_constraints'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Add UNIQUE constraint on transactions.ref_id for idempotency ──
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_transactions_ref_id'
            ) THEN
                CREATE UNIQUE INDEX uq_transactions_ref_id
                    ON transactions(ref_id)
                    WHERE ref_id IS NOT NULL;
            END IF;
        END $$;
    """)

    # ── Add CHECK constraint on users.balance (non-negative) ──
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'ck_users_balance_non_negative'
            ) THEN
                ALTER TABLE users ADD CONSTRAINT ck_users_balance_non_negative
                    CHECK (balance >= 0);
            END IF;
        END $$;
    """)

    # ── Add default subscription tiers ──
    op.execute("""
        INSERT INTO settings (key, value) VALUES
            ('subscription_tiers', '{"free":{"max_daily":5,"discount_pct":0,"api_access":false},"basic":{"max_daily":20,"discount_pct":5,"api_access":false},"premium":{"max_daily":50,"discount_pct":10,"api_access":false},"reseller":{"max_daily":200,"discount_pct":20,"api_access":true},"business":{"max_daily":500,"discount_pct":25,"api_access":true},"enterprise":{"max_daily":1000,"discount_pct":30,"api_access":true}}')
        ON CONFLICT (key) DO NOTHING
    """)

    # ── Seed default currency (USD) ──
    op.execute("""
        INSERT INTO currencies (code, name, symbol, rate_to_usd, is_active, is_default)
        VALUES ('USD', 'US Dollar', '$', 1.0, 1, 1)
        ON CONFLICT (code) DO NOTHING
    """)

    # ── Seed default provider record ──
    op.execute("""
        INSERT INTO providers (name, display_name, is_active, priority)
        VALUES ('herosms', 'HeroSMS', 1, 1)
        ON CONFLICT (name) DO NOTHING
    """)

    # ── Seed catalog services ──
    services = [
        ('telegram', 'Telegram', 'messaging', 1),
        ('whatsapp', 'WhatsApp', 'messaging', 2),
        ('instagram', 'Instagram', 'social', 3),
        ('google', 'Google', 'other', 4),
        ('facebook', 'Facebook', 'social', 5),
        ('twitter', 'Twitter / X', 'social', 6),
        ('tiktok', 'TikTok', 'social', 7),
        ('discord', 'Discord', 'social', 8),
        ('snapchat', 'Snapchat', 'social', 9),
        ('uber', 'Uber', 'transport', 10),
        ('airbnb', 'Airbnb', 'travel', 11),
        ('tinder', 'Tinder', 'dating', 12),
        ('amazon', 'Amazon', 'ecommerce', 13),
        ('microsoft', 'Microsoft', 'other', 14),
        ('yahoo', 'Yahoo', 'other', 15),
    ]
    for code, name, cat, order in services:
        op.execute(
            """INSERT INTO catalog_services (service_code, service_name, category, is_active, display_order)
               VALUES (%s, %s, %s, 1, %s) ON CONFLICT (service_code) DO NOTHING""",
            (code, name, cat, order))

    # ── Performance Indexes ──
    indexes = [
        'CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id)',
        'CREATE INDEX IF NOT EXISTS idx_transactions_timestamp ON transactions(timestamp)',
        'CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(type)',
        'CREATE INDEX IF NOT EXISTS idx_transactions_ref_id ON transactions(ref_id)',
        'CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id)',
        'CREATE INDEX IF NOT EXISTS idx_orders_activation_id ON orders(activation_id)',
        'CREATE INDEX IF NOT EXISTS idx_orders_order_id ON orders(order_id)',
        'CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)',
        'CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at)',
        'CREATE INDEX IF NOT EXISTS idx_card_payments_user_id ON card_payments(user_id)',
        'CREATE INDEX IF NOT EXISTS idx_card_payments_status ON card_payments(status)',
        'CREATE INDEX IF NOT EXISTS idx_activation_codes_order_id ON activation_codes(order_id)',
        'CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id)',
        'CREATE INDEX IF NOT EXISTS idx_subscriptions_tier ON subscriptions(tier)',
        'CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_id)',
        'CREATE INDEX IF NOT EXISTS idx_referral_codes_code ON referral_codes(code)',
        'CREATE INDEX IF NOT EXISTS idx_referral_codes_user ON referral_codes(user_id)',
        'CREATE INDEX IF NOT EXISTS idx_audit_log_admin ON audit_log(admin_id)',
        'CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action)',
        'CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at)',
        'CREATE INDEX IF NOT EXISTS idx_currencies_code ON currencies(code)',
        'CREATE INDEX IF NOT EXISTS idx_provider_prices_lookup ON provider_prices(provider_id, country_code, service_code)',
        'CREATE INDEX IF NOT EXISTS idx_catalog_prices_lookup ON catalog_prices(country_code, service_code, provider_id)',
        'CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, is_read)',
        'CREATE INDEX IF NOT EXISTS idx_fraud_log_user ON fraud_log(user_id)',
    ]
    for idx_sql in indexes:
        op.execute(idx_sql)


def downgrade() -> None:
    """Remove Phase 2 constraints and seed data."""
    op.execute("DROP INDEX IF EXISTS uq_transactions_ref_id")
    op.execute("ALTER TABLE IF EXISTS users DROP CONSTRAINT IF EXISTS ck_users_balance_non_negative")

    seed_tables = ['currencies', 'providers', 'catalog_services']
    for table in seed_tables:
        op.execute(f"DELETE FROM {table}")

    op.execute("DELETE FROM settings WHERE key = 'subscription_tiers'")
