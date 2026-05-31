"""${message}

Revision ID: 001_initial
Revises: None
Create Date: 2026-05-31

Initial schema — all core and enterprise tables.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Core Tables ───────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id       BIGINT PRIMARY KEY,
            username      TEXT,
            first_name    TEXT,
            last_name     TEXT,
            join_date     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            balance       INTEGER DEFAULT 0 CHECK (balance >= 0),
            is_blocked    INTEGER DEFAULT 0,
            language      TEXT DEFAULT 'fa',
            phone         TEXT
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id          SERIAL PRIMARY KEY,
            user_id     BIGINT NOT NULL REFERENCES users(user_id),
            amount      INTEGER NOT NULL CHECK (amount > 0),
            type        TEXT NOT NULL,
            description TEXT DEFAULT '',
            ref_id      TEXT,
            timestamp   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id              SERIAL PRIMARY KEY,
            user_id         BIGINT NOT NULL REFERENCES users(user_id),
            activation_id   INTEGER NOT NULL,
            service         TEXT NOT NULL,
            country         TEXT NOT NULL,
            operator        TEXT NOT NULL,
            phone           TEXT NOT NULL,
            price           INTEGER NOT NULL CHECK (price >= 0),
            status          TEXT NOT NULL DEFAULT 'PENDING',
            phone_number    TEXT,
            order_id        TEXT UNIQUE,
            order_date      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS card_payments (
            payment_id      TEXT PRIMARY KEY,
            user_id         BIGINT NOT NULL REFERENCES users(user_id),
            amount          INTEGER NOT NULL CHECK (amount > 0),
            status          TEXT DEFAULT 'pending',
            receipt         TEXT,
            admin_response  TEXT,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key         TEXT PRIMARY KEY,
            value       TEXT,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS card_info (
            id           SERIAL PRIMARY KEY,
            card_number  TEXT,
            card_holder  TEXT,
            updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS required_channels (
            username      TEXT PRIMARY KEY,
            display_name  TEXT NOT NULL,
            invite_link   TEXT NOT NULL,
            added_date    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS operator_settings (
            id            SERIAL PRIMARY KEY,
            service       TEXT NOT NULL,
            country       TEXT NOT NULL,
            operator      TEXT NOT NULL,
            country_name  TEXT NOT NULL,
            UNIQUE(service, country)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS activation_codes (
            id          SERIAL PRIMARY KEY,
            order_id    INTEGER NOT NULL REFERENCES orders(id),
            code        TEXT NOT NULL,
            status      TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── Enterprise Tables ─────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id              SERIAL PRIMARY KEY,
            user_id         BIGINT NOT NULL REFERENCES users(user_id),
            tier            TEXT NOT NULL DEFAULT 'free',
            status          TEXT NOT NULL DEFAULT 'active',
            started_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at      TIMESTAMP,
            auto_renew      INTEGER DEFAULT 1,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            id              SERIAL PRIMARY KEY,
            referrer_id     BIGINT NOT NULL REFERENCES users(user_id),
            referred_id     BIGINT NOT NULL REFERENCES users(user_id),
            code            TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT 'active',
            commission_pct  INTEGER DEFAULT 10,
            total_earned    INTEGER DEFAULT 0,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(referred_id)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS referral_codes (
            id              SERIAL PRIMARY KEY,
            user_id         BIGINT NOT NULL REFERENCES users(user_id) UNIQUE,
            code            TEXT NOT NULL UNIQUE,
            is_active       INTEGER DEFAULT 1,
            usage_count     INTEGER DEFAULT 0,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS admin_roles (
            id              SERIAL PRIMARY KEY,
            user_id         BIGINT NOT NULL UNIQUE,
            role            TEXT NOT NULL DEFAULT 'admin',
            assigned_by     BIGINT,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id              SERIAL PRIMARY KEY,
            admin_id        BIGINT NOT NULL,
            action          TEXT NOT NULL,
            target          TEXT DEFAULT '',
            details         TEXT DEFAULT '',
            ip_address      TEXT DEFAULT '',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS currencies (
            id              SERIAL PRIMARY KEY,
            code            TEXT NOT NULL UNIQUE,
            name            TEXT NOT NULL,
            symbol          TEXT DEFAULT '',
            rate_to_usd     NUMERIC(18,8) NOT NULL DEFAULT 1.0,
            is_active       INTEGER DEFAULT 1,
            is_default      INTEGER DEFAULT 0,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS providers (
            id              SERIAL PRIMARY KEY,
            name            TEXT NOT NULL UNIQUE,
            display_name    TEXT NOT NULL,
            api_key         TEXT DEFAULT '',
            api_url         TEXT DEFAULT '',
            is_active       INTEGER DEFAULT 1,
            priority        INTEGER DEFAULT 0,
            config          TEXT DEFAULT '{}',
            last_sync_at    TIMESTAMP,
            health_status   TEXT DEFAULT 'unknown',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS provider_countries (
            id              SERIAL PRIMARY KEY,
            provider_id     INTEGER NOT NULL REFERENCES providers(id),
            country_code    TEXT NOT NULL,
            country_name    TEXT NOT NULL,
            is_active       INTEGER DEFAULT 1,
            available_count INTEGER DEFAULT 0,
            last_sync_at    TIMESTAMP,
            UNIQUE(provider_id, country_code)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS provider_services (
            id              SERIAL PRIMARY KEY,
            provider_id     INTEGER NOT NULL REFERENCES providers(id),
            service_code    TEXT NOT NULL,
            service_name    TEXT NOT NULL,
            is_active       INTEGER DEFAULT 1,
            available_count INTEGER DEFAULT 0,
            last_sync_at    TIMESTAMP,
            UNIQUE(provider_id, service_code)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS provider_prices (
            id              SERIAL PRIMARY KEY,
            provider_id     INTEGER NOT NULL REFERENCES providers(id),
            country_code    TEXT NOT NULL,
            service_code    TEXT NOT NULL,
            operator_name   TEXT NOT NULL DEFAULT 'any',
            price_usd       NUMERIC(12,4) NOT NULL DEFAULT 0,
            available_count INTEGER DEFAULT 0,
            last_sync_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(provider_id, country_code, service_code, operator_name)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS catalog_countries (
            id              SERIAL PRIMARY KEY,
            country_code    TEXT NOT NULL UNIQUE,
            country_name    TEXT NOT NULL,
            is_active       INTEGER DEFAULT 0,
            display_order   INTEGER DEFAULT 0,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS catalog_services (
            id              SERIAL PRIMARY KEY,
            service_code    TEXT NOT NULL UNIQUE,
            service_name    TEXT NOT NULL,
            category        TEXT DEFAULT 'other',
            is_active       INTEGER DEFAULT 0,
            display_order   INTEGER DEFAULT 0,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS catalog_prices (
            id              SERIAL PRIMARY KEY,
            country_code    TEXT NOT NULL,
            service_code    TEXT NOT NULL,
            provider_id     INTEGER NOT NULL REFERENCES providers(id),
            base_price_usd  NUMERIC(12,4) NOT NULL DEFAULT 0,
            profit_pct      NUMERIC(6,2) NOT NULL DEFAULT 30,
            profit_fixed    NUMERIC(12,4) DEFAULT 0,
            min_price       NUMERIC(12,4) DEFAULT 0,
            max_price       NUMERIC(12,4) DEFAULT 0,
            final_price     NUMERIC(12,4) NOT NULL DEFAULT 0,
            is_active       INTEGER DEFAULT 1,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(country_code, service_code, provider_id)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id              SERIAL PRIMARY KEY,
            user_id         BIGINT NOT NULL REFERENCES users(user_id),
            type            TEXT NOT NULL,
            title           TEXT NOT NULL,
            message         TEXT NOT NULL,
            is_read         INTEGER DEFAULT 0,
            channel         TEXT DEFAULT 'telegram',
            metadata        TEXT DEFAULT '{}',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS fraud_log (
            id              SERIAL PRIMARY KEY,
            user_id         BIGINT,
            event_type      TEXT NOT NULL,
            risk_score      INTEGER DEFAULT 0,
            details         TEXT DEFAULT '{}',
            ip_address      TEXT DEFAULT '',
            device_fingerprint TEXT DEFAULT '',
            action_taken    TEXT DEFAULT 'logged',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


def downgrade() -> None:
    """Drop all tables in reverse dependency order."""
    tables = [
        'fraud_log', 'notifications', 'catalog_prices', 'catalog_services',
        'catalog_countries', 'provider_prices', 'provider_services',
        'provider_countries', 'providers', 'currencies', 'audit_log',
        'admin_roles', 'referral_codes', 'referrals', 'subscriptions',
        'activation_codes', 'operator_settings', 'required_channels',
        'card_info', 'settings', 'card_payments', 'orders', 'transactions',
        'users',
    ]
    for table in tables:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
