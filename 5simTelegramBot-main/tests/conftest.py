"""
tests/conftest.py — Shared Test Fixtures
─────────────────────────────────────────────────
Provides isolated test databases, service instances, and cleanup.
All tests use TEMPORARY databases — NEVER production data.
"""

import os
import pytest
import sqlite3
import tempfile
import shutil


# ── Isolated test database ─────────────────────────────────────

@pytest.fixture
def test_db():
    """Create a temporary SQLite database for testing."""
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, 'test.db')
    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA foreign_keys=ON')

    # Create essential tables
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
    ''')
    conn.commit()

    yield db_path, conn

    conn.close()
    shutil.rmtree(tmpdir)


# ── Test user fixture ──────────────────────────────────────────

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


# ── Test admin fixture ─────────────────────────────────────────

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


# ── Mock Bot fixture ───────────────────────────────────────────

@pytest.fixture
def mock_bot_config(monkeypatch):
    """Mock BOT_CONFIG for tests."""
    monkeypatch.setitem(
        __import__('config').BOT_CONFIG, 'admin_ids', [1457637832]
    )