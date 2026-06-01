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
        # psycopg2 starts a transaction implicitly on the first statement.
        # Issuing an explicit BEGIN here would raise
        # "there is already a transaction in progress". Rely on the implicit
        # transaction and commit/rollback in __exit__ instead.
        self._cursor = self._conn.cursor()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is not None:
                try:
                    self._conn.rollback()
                    logger.warning(f"Transaction ROLLBACK due to: {exc_type.__name__}: {exc_val}")
                except Exception as e:
                    logger.error(f"Rollback error: {e}")
                return False
            else:
                try:
                    self._conn.commit()
                    logger.debug("Transaction COMMIT")
                except Exception as e:
                    logger.error(f"Commit error: {e}")
                    # Ensure the connection is rolled back so it is not
                    # returned to the pool in an aborted state.
                    try:
                        self._conn.rollback()
                    except Exception:
                        pass
                    raise
                return True
        finally:
            if self._cursor is not None:
                try:
                    self._cursor.close()
                except Exception:
                    pass
            # put_connection performs a rollback() to guarantee the pooled
            # connection is reset to a clean, non-aborted state.
            self._cm.put_connection(self._conn)

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
            except Exception:
                pass
        return 0

    @property
    def rowcount(self):
        return self._cursor.rowcount if self._cursor else 0


def db_context(db_name: str = 'default', transactional: bool = True):
    return DatabaseContext(db_name, transactional=transactional)
