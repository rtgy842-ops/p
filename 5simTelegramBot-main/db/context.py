"""
db/context.py — Transaction-Safe Database Context (PostgreSQL)
─────────────────────────────────────────────────
Auto-commit for reads, BEGIN/COMMIT/ROLLBACK for writes.
Thread-safe via ConnectionManager pool.
"""

import logging
from db.connection import ConnectionManager

logger = logging.getLogger(__name__)


class DatabaseContext:
    def __init__(self, db_name: str = 'default', transactional: bool = True):
        self._db_name = db_name
        self._transactional = transactional
        self._cm = ConnectionManager.get_instance()
        self._conn = None
        self._cursor = None

    def __enter__(self):
        self._conn = self._cm.get_connection(self._db_name)
        self._cursor = self._conn.cursor()
        if self._transactional:
            self._cursor.execute('BEGIN')
            logger.debug("Transaction BEGIN")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            if self._transactional:
                try:
                    self._conn.rollback()
                    logger.warning(f"Transaction ROLLBACK due to: {exc_type.__name__}: {exc_val}")
                except Exception as e:
                    logger.error(f"Rollback error: {e}")
            self._cm.put_connection(self._conn)
            return False
        else:
            if self._transactional:
                try:
                    self._conn.commit()
                    logger.debug("Transaction COMMIT")
                except Exception as e:
                    logger.error(f"Commit error: {e}")
                    raise
            self._cm.put_connection(self._conn)
            return True

    def execute(self, query: str, params: tuple = ()):
        query = query.replace('?', '%s')
        self._cursor.execute(query, params)
        return self

    def fetchone(self, query: str, params: tuple = ()):
        query = query.replace('?', '%s')
        self._cursor.execute(query, params)
        rows = self._cursor.fetchall()
        if rows:
            return rows[0]
        return None

    def fetchall(self, query: str, params: tuple = ()):
        query = query.replace('?', '%s')
        self._cursor.execute(query, params)
        return self._cursor.fetchall()

    @property
    def lastrowid(self):
        if self._cursor and self._cursor.description:
            try:
                return self._cursor.fetchone()[0]
            except: pass
        return 0

    @property
    def rowcount(self):
        return self._cursor.rowcount if self._cursor else 0


def db_context(db_name: str = 'default', transactional: bool = True):
    return DatabaseContext(db_name, transactional=transactional)