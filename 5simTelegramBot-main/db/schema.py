"""
db/schema.py — PostgreSQL Schema Definitions
─────────────────────────────────────────────────
Single database (smsbot) with all tables in public schema.
Replaces 3 separate SQLite files.
"""

# ── All tables in the single PostgreSQL database ────────────────
ALL_TABLES: dict[str, str] = {
    'users': '''
        CREATE TABLE IF NOT EXISTS users (
            user_id       BIGINT PRIMARY KEY,
            username      TEXT,
            first_name    TEXT,
            last_name     TEXT,
            join_date     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            balance       INTEGER DEFAULT 0,
            is_blocked    INTEGER DEFAULT 0,
            language      TEXT DEFAULT 'fa',
            phone         TEXT
        )
    ''',
    'transactions': '''
        CREATE TABLE IF NOT EXISTS transactions (
            id          SERIAL PRIMARY KEY,
            user_id     BIGINT NOT NULL REFERENCES users(user_id),
            amount      INTEGER NOT NULL,
            type        TEXT NOT NULL,
            description TEXT DEFAULT '',
            ref_id      TEXT,
            timestamp   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''',
    'orders': '''
        CREATE TABLE IF NOT EXISTS orders (
            id              SERIAL PRIMARY KEY,
            user_id         BIGINT NOT NULL REFERENCES users(user_id),
            activation_id   INTEGER NOT NULL,
            service         TEXT NOT NULL,
            country         TEXT NOT NULL,
            operator        TEXT NOT NULL,
            phone           TEXT NOT NULL,
            price           INTEGER NOT NULL,
            status          TEXT NOT NULL DEFAULT 'PENDING',
            phone_number    TEXT,
            order_id        TEXT UNIQUE,
            order_date      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''',
    'card_payments': '''
        CREATE TABLE IF NOT EXISTS card_payments (
            payment_id      TEXT PRIMARY KEY,
            user_id         BIGINT NOT NULL REFERENCES users(user_id),
            amount          INTEGER NOT NULL,
            status          TEXT DEFAULT 'pending',
            receipt         TEXT,
            admin_response  TEXT,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''',
    'settings': '''
        CREATE TABLE IF NOT EXISTS settings (
            key         TEXT PRIMARY KEY,
            value       TEXT,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''',
    'card_info': '''
        CREATE TABLE IF NOT EXISTS card_info (
            id           SERIAL PRIMARY KEY,
            card_number  TEXT,
            card_holder  TEXT,
            updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''',
    'required_channels': '''
        CREATE TABLE IF NOT EXISTS required_channels (
            username      TEXT PRIMARY KEY,
            display_name  TEXT NOT NULL,
            invite_link   TEXT NOT NULL,
            added_date    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''',
    'operator_settings': '''
        CREATE TABLE IF NOT EXISTS operator_settings (
            id            SERIAL PRIMARY KEY,
            service       TEXT NOT NULL,
            country       TEXT NOT NULL,
            operator      TEXT NOT NULL,
            country_name  TEXT NOT NULL,
            UNIQUE(service, country)
        )
    ''',
    'activation_codes': '''
        CREATE TABLE IF NOT EXISTS activation_codes (
            id          SERIAL PRIMARY KEY,
            order_id    INTEGER NOT NULL REFERENCES orders(id),
            code        TEXT NOT NULL,
            status      TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''',
    '_migrations': '''
        CREATE TABLE IF NOT EXISTS _migrations (
            version     INTEGER PRIMARY KEY,
            description TEXT NOT NULL,
            applied_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            success     INTEGER DEFAULT 1
        )
    ''',
    # ── Enterprise Tables (Phase 2+) ────────────────────────────
    'subscriptions': '''
        CREATE TABLE IF NOT EXISTS subscriptions (
            id              SERIAL PRIMARY KEY,
            user_id         BIGINT NOT NULL REFERENCES users(user_id),
            tier            TEXT NOT NULL DEFAULT 'free',
            status          TEXT NOT NULL DEFAULT 'active',
            started_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at      TIMESTAMP,
            auto_renew      INTEGER DEFAULT 1,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id)
        )
    ''',
    'referrals': '''
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
    ''',
    'referral_codes': '''
        CREATE TABLE IF NOT EXISTS referral_codes (
            id              SERIAL PRIMARY KEY,
            user_id         BIGINT NOT NULL REFERENCES users(user_id) UNIQUE,
            code            TEXT NOT NULL UNIQUE,
            is_active       INTEGER DEFAULT 1,
            usage_count     INTEGER DEFAULT 0,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''',
    'admin_roles': '''
        CREATE TABLE IF NOT EXISTS admin_roles (
            id              SERIAL PRIMARY KEY,
            user_id         BIGINT NOT NULL UNIQUE,
            role            TEXT NOT NULL DEFAULT 'admin',
            assigned_by     BIGINT,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''',
    'audit_log': '''
        CREATE TABLE IF NOT EXISTS audit_log (
            id              SERIAL PRIMARY KEY,
            admin_id        BIGINT NOT NULL,
            action          TEXT NOT NULL,
            target          TEXT DEFAULT '',
            details         TEXT DEFAULT '',
            ip_address      TEXT DEFAULT '',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''',
    'currencies': '''
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
    ''',
    'providers': '''
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
    ''',
    'provider_countries': '''
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
    ''',
    'provider_services': '''
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
    ''',
    'provider_prices': '''
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
    ''',
    'catalog_countries': '''
        CREATE TABLE IF NOT EXISTS catalog_countries (
            id              SERIAL PRIMARY KEY,
            country_code    TEXT NOT NULL UNIQUE,
            country_name    TEXT NOT NULL,
            is_active       INTEGER DEFAULT 0,
            display_order   INTEGER DEFAULT 0,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''',
    'catalog_services': '''
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
    ''',
    'catalog_prices': '''
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
    ''',
    'notifications': '''
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
    ''',
    'fraud_log': '''
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
    ''',
    'wallet_ledger': '''
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
    ''',
    'rate_limits': '''
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
    ''',
}

DEFAULT_SETTINGS = [
    ('usd_rate', '0'),
    ('profit_percentage', '30'),
    ('channel_lock', 'false'),
    ('base_currency', 'USD'),
    ('app_name', 'NumGenius'),
    ('referral_bonus', '5000'),
    ('referral_commission_pct', '10'),
    ('max_referrals_per_user', '50'),
]

INDEXES: list[str] = [
    'CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id)',
    'CREATE INDEX IF NOT EXISTS idx_transactions_timestamp ON transactions(timestamp)',
    'CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id)',
    'CREATE INDEX IF NOT EXISTS idx_orders_activation_id ON orders(activation_id)',
    'CREATE INDEX IF NOT EXISTS idx_orders_order_id ON orders(order_id)',
    'CREATE INDEX IF NOT EXISTS idx_card_payments_user_id ON card_payments(user_id)',
    'CREATE INDEX IF NOT EXISTS idx_card_payments_status ON card_payments(status)',
    'CREATE INDEX IF NOT EXISTS idx_activation_codes_order_id ON activation_codes(order_id)',
    'CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id)',
    'CREATE INDEX IF NOT EXISTS idx_subscriptions_tier ON subscriptions(tier)',
    'CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_id)',
    'CREATE INDEX IF NOT EXISTS idx_referrals_code ON referral_codes(code)',
    'CREATE INDEX IF NOT EXISTS idx_audit_log_admin ON audit_log(admin_id)',
    'CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action)',
    'CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at)',
    'CREATE INDEX IF NOT EXISTS idx_currencies_code ON currencies(code)',
    'CREATE INDEX IF NOT EXISTS idx_provider_prices_lookup ON provider_prices(provider_id, country_code, service_code)',
    'CREATE INDEX IF NOT EXISTS idx_catalog_prices_lookup ON catalog_prices(country_code, service_code, provider_id)',
    'CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, is_read)',
    'CREATE INDEX IF NOT EXISTS idx_fraud_log_user ON fraud_log(user_id)',
    'CREATE INDEX IF NOT EXISTS idx_wallet_ledger_user ON wallet_ledger(user_id)',
    'CREATE INDEX IF NOT EXISTS idx_wallet_ledger_type ON wallet_ledger(entry_type)',
    'CREATE INDEX IF NOT EXISTS idx_wallet_ledger_created ON wallet_ledger(created_at)',
    'CREATE INDEX IF NOT EXISTS idx_rate_limits_key ON rate_limits(key, endpoint)',
]
