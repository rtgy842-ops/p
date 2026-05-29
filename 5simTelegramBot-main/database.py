"""
database.py — Core Database Operations (PostgreSQL)
─────────────────────────────────────────────────
ALL operations use the ConnectionManager pool.
No SQLite code whatsoever.
"""

import logging
from db.connection import ConnectionManager
from db.repositories.user_repository import UserRepository
from db.repositories.transaction_repository import TransactionRepository
from db.repositories.settings_repository import SettingsRepository

logger = logging.getLogger(__name__)


def setup_databases():
    """Initialize schema via ConnectionManager (single PG database)."""
    try:
        from db.schema import ALL_TABLES, DEFAULT_SETTINGS, INDEXES
        cm = ConnectionManager.get_instance()
        conn = cm.get_connection('default')
        cursor = conn.cursor()
        for table_name, ddl in ALL_TABLES.items():
            try:
                cursor.execute(ddl)
                logger.debug(f"Table ensured: {table_name}")
            except Exception as e:
                logger.error(f"Failed: {table_name}: {e}")
        conn.commit()

        # Default settings
        repo = SettingsRepository()
        for key, value in DEFAULT_SETTINGS:
            if not repo.exists(key):
                repo.set(key, value)

        # Indexes
        for idx_sql in INDEXES:
            try:
                cursor.execute(idx_sql)
            except Exception as e:
                logger.warning(f"Index ok: {e}")
        conn.commit()
        cm.put_connection(conn)
        logger.info("Database initialized via PostgreSQL pool")
        return True
    except Exception as e:
        logger.error(f"Database setup failed: {e}")
        return False


setup_users_database = setup_databases
setup_admin_database = setup_databases
setup_orders_database = setup_databases


def get_user_balance(user_id):
    return UserRepository().get_balance(user_id)

def add_balance(user_id, amount):
    return UserRepository().add_balance(user_id, amount)

def save_transaction(user_id, amount, type_trans, description, ref_id=None):
    txn_id = TransactionRepository().create(user_id, amount, type_trans, description, ref_id)
    return txn_id is not None

def get_card_info():
    info = SettingsRepository().get_card_info()
    return (info[0], info[1]) if info else None

def save_user_phone(user_id, phone):
    return UserRepository().save_phone(user_id, phone)
