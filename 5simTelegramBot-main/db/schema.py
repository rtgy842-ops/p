"""
db/schema.py — Complete Database Schema Definitions
─────────────────────────────────────────────────
All table DDL in one place. No scattered CREATE TABLE statements.
Used by ConnectionManager.setup_all() and migration system.

Schema version: 1
"""

# ── users.db tables ────────────────────────────────────────────
USERS_TABLES: dict[str, str] = {
    'users': '''
        CREATE TABLE IF NOT EXISTS users (
            user_id       INTEGER PRIMARY KEY,
            username      TEXT,
            first_name    TEXT,
            last_name     TEXT,
            join_date     DATETIME DEFAULT CURRENT_TIMESTAMP,
            balance       INTEGER DEFAULT 0,
            is_blocked    INTEGER DEFAULT 0,
            language      TEXT DEFAULT 'fa',
            phone         TEXT
        )
    ''',
    'transactions': '''
        CREATE TABLE IF NOT EXISTS transactions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            amount      INTEGER NOT NULL,
            type        TEXT NOT NULL,
            description TEXT DEFAULT '',
            ref_id      TEXT,
            timestamp   DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''',
    'orders': '''
        CREATE TABLE IF NOT EXISTS orders (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            service         TEXT,
            country         TEXT,
            phone_number    TEXT,
            price           INTEGER,
            status          TEXT DEFAULT 'active',
            order_id        TEXT UNIQUE,
            order_date      DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''',
    'card_payments': '''
        CREATE TABLE IF NOT EXISTS card_payments (
            payment_id      TEXT PRIMARY KEY,
            user_id         INTEGER NOT NULL,
            amount          INTEGER NOT NULL,
            status          TEXT DEFAULT 'pending',
            receipt         TEXT,
            admin_response  TEXT,
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''',
}

# ── admin.db tables ────────────────────────────────────────────
ADMIN_TABLES: dict[str, str] = {
    'settings': '''
        CREATE TABLE IF NOT EXISTS settings (
            key         TEXT PRIMARY KEY,
            value       TEXT,
            updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''',
    'card_info': '''
        CREATE TABLE IF NOT EXISTS card_info (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            card_number  TEXT,
            card_holder  TEXT,
            updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''',
    'required_channels': '''
        CREATE TABLE IF NOT EXISTS required_channels (
            username      TEXT PRIMARY KEY,
            display_name  TEXT NOT NULL,
            invite_link   TEXT NOT NULL,
            added_date    DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''',
    'operator_settings': '''
        CREATE TABLE IF NOT EXISTS operator_settings (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            service       TEXT NOT NULL,
            country       TEXT NOT NULL,
            operator      TEXT NOT NULL,
            country_name  TEXT NOT NULL,
            UNIQUE(service, country)
        )
    ''',
}

# ── bot.db tables ──────────────────────────────────────────────
BOT_TABLES: dict[str, str] = {
    'settings': '''
        CREATE TABLE IF NOT EXISTS settings (
            key    TEXT PRIMARY KEY,
            value  TEXT NOT NULL
        )
    ''',
    'orders': '''
        CREATE TABLE IF NOT EXISTS orders (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            activation_id   INTEGER NOT NULL,
            service         TEXT NOT NULL,
            country         TEXT NOT NULL,
            operator        TEXT NOT NULL,
            phone           TEXT NOT NULL,
            price           INTEGER NOT NULL,
            status          TEXT NOT NULL DEFAULT 'PENDING',
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''',
    'activation_codes': '''
        CREATE TABLE IF NOT EXISTS activation_codes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id    INTEGER NOT NULL,
            code        TEXT NOT NULL,
            status      TEXT,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (order_id) REFERENCES orders(id)
        )
    ''',
}

# ── All tables mapped to their database ────────────────────────
ALL_SCHEMAS: dict[str, dict[str, str]] = {
    'users_db': USERS_TABLES,
    'admin_db': ADMIN_TABLES,
    'bot_db': BOT_TABLES,
}

# ── Default settings ───────────────────────────────────────────
DEFAULT_SETTINGS = [
    ('usd_rate', '0'),
    ('profit_percentage', '30'),
    ('channel_lock', 'false'),
]

# ── Index definitions ──────────────────────────────────────────
INDEXES: dict[str, list[str]] = {
    'users_db': [
        'CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id)',
        'CREATE INDEX IF NOT EXISTS idx_transactions_timestamp ON transactions(timestamp)',
        'CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id)',
        'CREATE INDEX IF NOT EXISTS idx_orders_order_id ON orders(order_id)',
        'CREATE INDEX IF NOT EXISTS idx_card_payments_user_id ON card_payments(user_id)',
        'CREATE INDEX IF NOT EXISTS idx_card_payments_status ON card_payments(status)',
    ],
    'admin_db': [],
    'bot_db': [
        'CREATE INDEX IF NOT EXISTS idx_bot_orders_user_id ON orders(user_id)',
        'CREATE INDEX IF NOT EXISTS idx_bot_orders_activation_id ON orders(activation_id)',
        'CREATE INDEX IF NOT EXISTS idx_activation_codes_order_id ON activation_codes(order_id)',
    ],
}
