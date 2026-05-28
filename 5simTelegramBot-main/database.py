"""
database.py — Core Database Operations Layer
─────────────────────────────────────────────────
ALL database operations use the ConnectionManager singleton.
No direct sqlite3.connect() calls anywhere in this file.
Database setup is done via db/schema.py + migrations.

This file provides backward-compatible functions for legacy callers
that now delegate to the enterprise repository layer.
"""

import logging
from db.connection import ConnectionManager
from db.repositories.user_repository import UserRepository
from db.repositories.transaction_repository import TransactionRepository
from db.repositories.settings_repository import SettingsRepository
from config import DB_CONFIG

logger = logging.getLogger(__name__)


def setup_databases():
    """Initialize all database schemas via ConnectionManager."""
    try:
        from db.schema import ALL_SCHEMAS, DEFAULT_SETTINGS, INDEXES
        cm = ConnectionManager.get_instance()

        # Create all tables across all databases
        for db_name, tables in ALL_SCHEMAS.items():
            conn = cm.get_connection(db_name)
            cursor = conn.cursor()
            for table_name, ddl in tables.items():
                try:
                    cursor.execute(ddl)
                    logger.debug(f"Table ensured: {db_name}.{table_name}")
                except Exception as e:
                    logger.error(f"Failed to create table {db_name}.{table_name}: {e}")
            conn.commit()

        # Insert default settings
        repo = SettingsRepository()
        for key, value in DEFAULT_SETTINGS:
            if not repo.exists(key):
                repo.set(key, value)
                logger.info(f"Default setting inserted: {key}={value}")

        # Create indexes
        for db_name, idx_list in INDEXES.items():
            conn = cm.get_connection(db_name)
            cursor = conn.cursor()
            for idx_sql in idx_list:
                try:
                    cursor.execute(idx_sql)
                except Exception as e:
                    logger.warning(f"Index may already exist in {db_name}: {e}")
            conn.commit()

        logger.info("All databases initialized via ConnectionManager")
        return True
    except Exception as e:
        logger.error(f"Database setup failed: {e}")
        return False


def setup_users_database():
    """Create users_db tables via ConnectionManager."""
    setup_databases()


def setup_admin_database():
    """Create admin_db tables via ConnectionManager."""
    setup_databases()


def setup_orders_database():
    """Create orders tables via ConnectionManager."""
    setup_databases()


def get_user_balance(user_id):
    """Get user balance via repository layer."""
    try:
        repo = UserRepository()
        return repo.get_balance(user_id)
    except Exception as e:
        logger.error(f"Error in get_user_balance: {e}")
        return 0


def add_balance(user_id, amount):
    """Add balance via repository layer. Transaction-safe."""
    try:
        repo = UserRepository()
        return repo.add_balance(user_id, amount)
    except Exception as e:
        logger.error(f"Error in add_balance: {e}", exc_info=True)
        return None


def save_transaction(user_id, amount, type_trans, description, ref_id=None):
    """Record a transaction via repository layer. Transaction-safe."""
    try:
        repo = TransactionRepository()
        txn_id = repo.create(user_id, amount, type_trans, description, ref_id)
        return txn_id is not None
    except Exception as e:
        logger.error(f"Error in save_transaction: {e}")
        return False


def get_card_info():
    """Get bank card info from admin.db."""
    try:
        repo = SettingsRepository()
        return repo.get_card_info()
    except Exception as e:
        logger.error(f"Error in get_card_info: {e}")
        return None


def add_test_transaction():
    """Add a test transaction (for debugging)."""
    try:
        repo = TransactionRepository()
        repo.create(123456, 100000, 'purchase', 'Test transaction')
        logger.info("Test transaction added")
    except Exception as e:
        logger.error(f"Error adding test transaction: {e}")


def save_user_phone(user_id, phone):
    """Save user phone number via repository."""
    try:
        repo = UserRepository()
        return repo.save_phone(user_id, phone)
    except Exception as e:
        logger.error(f"Error saving phone number: {e}")
        return False
