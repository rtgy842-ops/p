"""
db/connection.py — Centralized Connection Manager
─────────────────────────────────────────────────
Single entry point for ALL database connections.
Prevents scattered sqlite3.connect() calls across the codebase.

Features:
- Connection reuse (not opening/closing per query)
- Thread-safe (one connection per thread)
- WAL mode for better concurrency
- Foreign keys enforced
- Query logging for performance analysis

Usage:
    from db.connection import ConnectionManager
    cm = ConnectionManager.get_instance()
    conn = cm.get_connection('admin.db')
"""

import sqlite3
import logging
import threading
import time
import os
from config import DB_CONFIG

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Singleton connection manager.
    One instance per process, thread-local connections.
    """

    _instance: 'ConnectionManager | None' = None
    _lock = threading.Lock()

    def __init__(self):
        self._connections: dict[str, sqlite3.Connection] = {}
        self._query_count: dict[str, int] = {}
        self._slow_query_threshold: float = 0.5  # seconds

    @classmethod
    def get_instance(cls) -> 'ConnectionManager':
        """Get or create the singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def get_connection(self, db_name: str) -> sqlite3.Connection:
        """
        Get a connection for the given database name.
        Returns an existing connection if available, creates new one otherwise.
        Thread-safe via instance lock.
        """
        if db_name not in self._connections:
            # Resolve the actual filename from config if it's a config key
            db_path = self._resolve_db_path(db_name)
            conn = sqlite3.connect(db_path, timeout=10)
            conn.row_factory = sqlite3.Row
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA foreign_keys=ON')
            conn.execute('PRAGMA busy_timeout=5000')
            self._connections[db_name] = conn
            self._query_count[db_name] = 0
            logger.info(f"Database connection established: {db_path} (WAL mode, FK enforced)")

        return self._connections[db_name]

    def execute(self, db_name: str, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """
        Execute a query with automatic logging and timing.
        Tracks slow queries for performance analysis.
        """
        start = time.time()
        conn = self.get_connection(db_name)
        cursor = conn.cursor()

        try:
            cursor.execute(query, params)
            elapsed = time.time() - start
            self._query_count[db_name] += 1

            if elapsed > self._slow_query_threshold:
                logger.warning(
                    f"SLOW QUERY [{elapsed:.3f}s] on {db_name}: "
                    f"{query[:100]}{'...' if len(query) > 100 else ''}"
                )
            else:
                logger.debug(f"Query [{elapsed:.4f}s] on {db_name}: {query[:80]}")

            return cursor
        except sqlite3.Error as e:
            logger.error(f"Database error on {db_name}: {e}\nQuery: {query}\nParams: {params}")
            raise

    def commit(self, db_name: str) -> None:
        """Commit pending transaction on the given database."""
        if db_name in self._connections:
            self._connections[db_name].commit()

    def rollback(self, db_name: str) -> None:
        """Rollback pending transaction on the given database."""
        if db_name in self._connections:
            self._connections[db_name].rollback()

    def close_all(self) -> None:
        """Close all managed connections gracefully."""
        for db_name, conn in self._connections.items():
            try:
                conn.close()
                logger.info(f"Database connection closed: {db_name}")
            except Exception as e:
                logger.error(f"Error closing {db_name}: {e}")
        self._connections.clear()

    def get_stats(self) -> dict:
        """Return connection and query statistics."""
        return {
            'active_connections': len(self._connections),
            'query_counts': dict(self._query_count),
            'databases': list(self._connections.keys()),
        }

    def _resolve_db_path(self, db_name: str) -> str:
        """Resolve a database name to its file path."""
        # Check if it's a config key
        if db_name in ('users_db', 'admin_db'):
            return DB_CONFIG.get(db_name, f'{db_name}.db')
        if db_name == 'bot_db':
            return 'bot.db'
        # Direct filename
        if db_name.endswith('.db'):
            return db_name
        return f'{db_name}.db'

    def __del__(self):
        """Ensure connections are closed on garbage collection."""
        self.close_all()