"""
db/context.py — Database Context / Session Layer
─────────────────────────────────────────────────
Provides a transaction-safe context manager for database operations.
Ensures ALL financial operations use BEGIN/COMMIT/ROLLBACK.

Usage:
    from db.context import db_context
    
    with db_context('users_db') as db:
        db.execute("UPDATE users SET balance = ? WHERE user_id = ?", (1000, 123))
        db.execute("INSERT INTO transactions ...")
        # Auto-commits on success, auto-rollbacks on exception

    # Or with explicit transaction control:
    with db_context('users_db', transactional=True) as db:
        db.execute("...")
        db.execute("...")
        # Commit only if no exception occurs
"""

import logging
from db.connection import ConnectionManager

logger = logging.getLogger(__name__)


class DatabaseContext:
    """
    Transaction-safe database context manager.
    
    Patterns:
    - Auto-commit for read operations (transactional=False)
    - BEGIN/COMMIT/ROLLBACK for write operations (transactional=True)
    - All financial operations MUST use transactional=True
    """

    def __init__(self, db_name: str, transactional: bool = True):
        self._db_name = db_name
        self._transactional = transactional
        self._cm = ConnectionManager.get_instance()
        self._conn = None
        self._cursor = None

    def __enter__(self) -> 'DatabaseContext':
        self._conn = self._cm.get_connection(self._db_name)
        self._cursor = self._conn.cursor()

        if self._transactional:
            self._conn.execute('BEGIN')
            logger.debug(f"Transaction BEGIN on {self._db_name}")

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # Exception occurred — ROLLBACK
            if self._transactional:
                try:
                    self._conn.rollback()
                    logger.warning(
                        f"Transaction ROLLBACK on {self._db_name} "
                        f"due to: {exc_type.__name__}: {exc_val}"
                    )
                except Exception as e:
                    logger.error(f"Rollback error on {self._db_name}: {e}")
            return False  # Re-raise the exception
        else:
            # Success — COMMIT
            if self._transactional:
                try:
                    self._conn.commit()
                    logger.debug(f"Transaction COMMIT on {self._db_name}")
                except Exception as e:
                    logger.error(f"Commit error on {self._db_name}: {e}")
                    raise
            return True

    def execute(self, query: str, params: tuple = ()) -> 'DatabaseContext':
        """Execute a parameterized query. Returns self for chaining."""
        self._cm.execute(self._db_name, query, params)
        return self

    def fetchone(self, query: str, params: tuple = ()):
        """Execute and fetch one row."""
        cursor = self._cm.execute(self._db_name, query, params)
        return cursor.fetchone()

    def fetchall(self, query: str, params: tuple = ()):
        """Execute and fetch all rows."""
        cursor = self._cm.execute(self._db_name, query, params)
        return cursor.fetchall()

    @property
    def lastrowid(self) -> int:
        """Return the last inserted row id."""
        return self._cursor.lastrowid if self._cursor else 0

    @property
    def rowcount(self) -> int:
        """Return the number of affected rows."""
        return self._cursor.rowcount if self._cursor else 0


# ── Convenience function ───────────────────────────────────────
def db_context(db_name: str, transactional: bool = True) -> DatabaseContext:
    """
    Create a database context for the given database.
    
    Args:
        db_name: Database name ('users_db', 'admin_db', or 'bot.db')
        transactional: Use BEGIN/COMMIT/ROLLBACK (True for writes!)
    """
    return DatabaseContext(db_name, transactional=transactional)