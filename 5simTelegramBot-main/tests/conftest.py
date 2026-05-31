"""
tests/conftest.py — Shared Test Fixtures
─────────────────────────────────────────────────
Provides isolated test databases, service instances, and cleanup.
All tests use TEMPORARY databases — NEVER production data.
"""
import os
import shutil
import sqlite3
import tempfile

import pytest


@pytest.fixture
def test_db():
    """Create a temporary SQLite database for testing."""
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, 'test.db')
    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA foreign_keys=ON')

    conn.executescript('''
        CREATE TABLE users (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            language TEXT DEFAULT 'fa',
            is_blocked INTEGER DEFAULT 0
        );

        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            type TEXT NOT NULL,
            description TEXT DEFAULT '',
            ref_id TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            activation_id INTEGER,
            service TEXT DEFAULT '',
            country TEXT DEFAULT '',
            operator TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            price INTEGER DEFAULT 0,
            status TEXT DEFAULT 'CREATED',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE activation_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE card_payments (
            payment_id TEXT PRIMARY KEY,
            user_id INTEGER,
            amount INTEGER,
            status TEXT DEFAULT 'pending',
            receipt TEXT,
            admin_response TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE referral_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            code TEXT NOT NULL UNIQUE,
            is_active INTEGER DEFAULT 1,
            usage_count INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER NOT NULL,
            referred_id INTEGER NOT NULL UNIQUE,
            code TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            commission_pct INTEGER DEFAULT 10,
            total_earned INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE admin_roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            role TEXT NOT NULL DEFAULT 'admin',
            assigned_by INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            tier TEXT NOT NULL DEFAULT 'free',
            status TEXT NOT NULL DEFAULT 'active',
            started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME,
            auto_renew INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE wallet_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            entry_type TEXT NOT NULL,
            running_balance INTEGER NOT NULL,
            description TEXT DEFAULT '',
            ref_id TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE fraud_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            event_type TEXT NOT NULL,
            risk_score INTEGER DEFAULT 0,
            details TEXT DEFAULT '{}',
            ip_address TEXT DEFAULT '',
            device_fingerprint TEXT DEFAULT '',
            action_taken TEXT DEFAULT 'logged',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE providers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            priority INTEGER DEFAULT 0,
            config TEXT DEFAULT '{}',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()

    yield db_path, conn

    conn.close()
    shutil.rmtree(tmpdir)


@pytest.fixture
def test_user(test_db):
    """Create a test user with 100000 balance."""
    db_path, conn = test_db
    conn.execute(
        'INSERT INTO users (user_id, balance, language) VALUES (?, ?, ?)',
        (123456789, 100000, 'fa')
    )
    conn.commit()
    return 123456789


@pytest.fixture
def test_admin(test_db):
    """Create a test admin user."""
    db_path, conn = test_db
    conn.execute(
        'INSERT INTO users (user_id, balance, language) VALUES (?, ?, ?)',
        (1457637832, 0, 'fa')
    )
    conn.commit()
    return 1457637832


@pytest.fixture
def mock_bot_config(monkeypatch):
    """Mock BOT_CONFIG for tests."""
    monkeypatch.setitem(
        __import__('config').BOT_CONFIG, 'admin_ids', [1457637832]
    )
