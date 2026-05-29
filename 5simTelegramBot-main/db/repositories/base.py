"""
db/repositories/base.py — Base Repository (PostgreSQL)
─────────────────────────────────────────────────
Foundation for all repositories.
Uses DatabaseContext + ConnectionManager pool.
Thread-safe via connection pool.
"""

import logging
from db.context import DatabaseContext

logger = logging.getLogger(__name__)


class BaseRepository:
    db_name: str = 'default'

    def _context(self, transactional: bool = True) -> DatabaseContext:
        return DatabaseContext(self.db_name, transactional=transactional)

    def _execute_write(self, query: str, params: tuple = ()):
        with self._context(transactional=True) as db:
            db.execute(query, params)

    def _execute_read(self, query: str, params: tuple = ()):
        with self._context(transactional=False) as db:
            return db.fetchall(query, params)

    def _fetchone(self, query: str, params: tuple = ()):
        with self._context(transactional=False) as db:
            return db.fetchone(query, params)
