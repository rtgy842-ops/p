"""
db/repositories/base.py — Base Repository
─────────────────────────────────────────────────
Foundation for all repositories. Provides:
- Automatic DB context via DatabaseContext
- Transaction safety for write operations
- Consistent error handling and logging
- Query logging through ConnectionManager

All financial repositories MUST use transactional=True for writes.
"""

import logging
import sqlite3
from db.context import DatabaseContext

logger = logging.getLogger(__name__)


class BaseRepository:
    """
    Base class for all repositories.
    
    Subclasses must set:
        db_name: str — which database this repository operates on
    """

    db_name: str = 'users_db'

    def _context(self, transactional: bool = True) -> DatabaseContext:
        """Create a database context. Financial ops must be transactional."""
        return DatabaseContext(self.db_name, transactional=transactional)

    def _execute_write(self, query: str, params: tuple = ()) -> None:
        """Execute a write query within a transaction."""
        with self._context(transactional=True) as db:
            db.execute(query, params)

    def _execute_read(self, query: str, params: tuple = ()):
        """Execute a read query (no transaction needed)."""
        with self._context(transactional=False) as db:
            return db.fetchall(query, params)

    def _fetchone(self, query: str, params: tuple = ()):
        """Fetch a single row (no transaction needed)."""
        with self._context(transactional=False) as db:
            return db.fetchone(query, params)

    def _insert_and_get_id(self, query: str, params: tuple = ()) -> int | None:
        """Execute INSERT and return lastrowid within a transaction."""
        from db.connection import ConnectionManager
        cm = ConnectionManager.get_instance()
        conn = cm.get_connection(self.db_name)
        cursor = conn.cursor()
        try:
            conn.execute('BEGIN')
            cursor.execute(query, params)
            rowid = cursor.lastrowid
            conn.commit()
            return rowid
        except sqlite3.Error:
            conn.rollback()
            raise
