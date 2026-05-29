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
}

DEFAULT_SETTINGS = [
    ('usd_rate', '0'),
    ('profit_percentage', '30'),
    ('channel_lock', 'false'),
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
]
