"""
db/connection.py — PostgreSQL Connection Pool (Thread-Safe)
─────────────────────────────────────────────────
Replaces SQLite singleton with psycopg2 ThreadedConnectionPool.
Every connection is thread-safe — no more "objects in different thread" errors.
"""

import os
import logging
import psycopg2
from psycopg2 import pool, extras

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://smsbot:smsbot_secret@postgres:5432/smsbot')


class ConnectionManager:
    """
    Thread-safe PostgreSQL connection pool manager.
    Uses psycopg2 ThreadedConnectionPool.
    All DB operations use a single shared schema (public).
    """

    _instance = None

    def __init__(self):
        self._pool = pool.ThreadedConnectionPool(
            minconn=2, maxconn=10,
            dsn=DATABASE_URL,
            options='-c search_path=public'
        )
        self._query_count = 0
        self._slow_query_threshold = 0.5
        logger.info("PostgreSQL connection pool established (2-10 connections)")

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_connection(self, db_name: str = 'default'):
        """Get a connection from the pool. db_name ignored — single PG database."""
        return self._pool.getconn()

    def put_connection(self, conn):
        """Return a connection to the pool."""
        try:
            self._pool.putconn(conn)
        except Exception as e:
            logger.warning(f"Error returning connection to pool: {e}")

    def execute(self, db_name: str, query: str, params: tuple = ()):
        """Execute a query with logging. Thread-safe via pool."""
        import time
        start = time.time()
        conn = self.get_connection(db_name)
        cursor = conn.cursor()
        try:
            # Convert SQLite ? placeholders to PostgreSQL %s
            query = query.replace('?', '%s')
            cursor.execute(query, params)
            elapsed = time.time() - start
            self._query_count += 1
            if elapsed > self._slow_query_threshold:
                logger.warning(f"SLOW QUERY [{elapsed:.3f}s]: {query[:100]}")
            return cursor
        except Exception as e:
            logger.error(f"DB error: {e}\nQuery: {query}\nParams: {params}")
            raise
        finally:
            self.put_connection(conn)

    def execute_and_commit(self, db_name: str, query: str, params: tuple = ()):
        """Execute and commit within a single connection lifecycle."""
        conn = self.get_connection(db_name)
        cursor = conn.cursor()
        try:
            query = query.replace('?', '%s')
            cursor.execute(query, params)
            conn.commit()
            return cursor
        except Exception as e:
            conn.rollback()
            logger.error(f"DB error (with commit): {e}")
            raise
        finally:
            self.put_connection(conn)

    def commit(self, db_name: str):
        pass  # Each connection handles its own commits

    def rollback(self, db_name: str):
        pass

    def close_all(self):
        """Close the connection pool."""
        if self._pool:
            self._pool.closeall()
            logger.info("PostgreSQL connection pool closed")

    def get_stats(self) -> dict:
        return {
            'active_connections': 'pool(2-10)',
            'query_counts': self._query_count,
            'databases': ['postgresql://smsbot'],
            'type': 'PostgreSQL',
        }

    def __del__(self):
        self.close_all()