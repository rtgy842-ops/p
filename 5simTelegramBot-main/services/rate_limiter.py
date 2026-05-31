"""
services/rate_limiter.py — Token-Bucket Rate Limiter
─────────────────────────────────────────────────
PostgreSQL-backed rate limiting for API endpoints.
Prevents brute-force, spam, and DDoS attacks.

Configuration:
- Default: 60 requests per minute per key
- Purchase/verify: 10 requests per minute per user
- Registration: 5 requests per hour per IP

Keys: user_id, IP address, or combination.
"""
import logging
import time
from datetime import datetime, timedelta
from db.context import db_context

logger = logging.getLogger(__name__)

# ── Default limits per endpoint category ──
DEFAULT_LIMITS = {
    'default':      {'max': 60,  'window': 60},     # 60/min
    'purchase':     {'max': 10,  'window': 60},     # 10/min
    'verify':       {'max': 5,   'window': 60},     # 5/min (payment callbacks)
    'register':     {'max': 5,   'window': 3600},   # 5/hour
    'auth':         {'max': 20,  'window': 60},     # 20/min
    'broadcast':    {'max': 3,   'window': 3600},   # 3/hour (admin)
    'sync':         {'max': 1,   'window': 300},    # 1/5min (provider sync)
}


class RateLimiter:
    """
    Simple token-bucket rate limiter using PostgreSQL.
    Uses sliding window per (key, endpoint) combination.
    """

    @staticmethod
    def is_allowed(key: str, endpoint: str = 'default') -> tuple[bool, int]:
        """
        Check if a request is allowed. Returns (allowed, remaining).
        Records the request if allowed.
        """
        limit_cfg = DEFAULT_LIMITS.get(endpoint, DEFAULT_LIMITS['default'])
        max_req = limit_cfg['max']
        window = limit_cfg['window']

        try:
            now = datetime.utcnow()
            window_start = now - timedelta(seconds=window)

            with db_context('default', transactional=True) as db:
                # Check if blocked
                blocked = db.fetchone(
                    "SELECT 1 FROM rate_limits WHERE key = %s AND endpoint = %s AND is_blocked = 1 AND blocked_until > %s",
                    (key, endpoint, now))
                if blocked:
                    return False, 0

                # Count requests in current window
                count_row = db.fetchone(
                    """SELECT COALESCE(SUM(request_count), 0) FROM rate_limits
                       WHERE key = %s AND endpoint = %s AND window_start >= %s""",
                    (key, endpoint, window_start))
                current = int(count_row[0]) if count_row else 0

                if current >= max_req:
                    # Block for 2x window duration
                    db.execute(
                        """UPDATE rate_limits SET is_blocked = 1, blocked_until = %s
                           WHERE key = %s AND endpoint = %s AND window_start >= %s""",
                        (now + timedelta(seconds=window * 2), key, endpoint, window_start))
                    logger.warning(f"Rate limit exceeded: {key} on {endpoint}")
                    return False, 0

                # Record the request
                db.execute(
                    """INSERT INTO rate_limits (key, endpoint, window_start, request_count)
                       VALUES (%s, %s, %s, 1)
                       ON CONFLICT (key, endpoint, window_start) DO UPDATE SET
                       request_count = rate_limits.request_count + 1""",
                    (key, endpoint, now))
                return True, max_req - current - 1

        except Exception as e:
            logger.error(f"Rate limiter error: {e}")
            return True, max_req  # Fail open if DB error

    @staticmethod
    def clear_blocks(key: str = ''):
        """Clear all blocks for a key or all keys."""
        try:
            with db_context('default', transactional=True) as db:
                if key:
                    db.execute(
                        "DELETE FROM rate_limits WHERE key = %s AND is_blocked = 1",
                        (key,))
                else:
                    db.execute("DELETE FROM rate_limits WHERE is_blocked = 1")
        except Exception as e:
            logger.error(f"Rate limiter clear error: {e}")

    @staticmethod
    def cleanup_old_entries(max_age_hours: int = 24):
        """Remove rate limit entries older than max_age_hours."""
        try:
            with db_context('default', transactional=True) as db:
                db.execute(
                    "DELETE FROM rate_limits WHERE window_start < %s AND is_blocked = 0",
                    (datetime.utcnow() - timedelta(hours=max_age_hours),))
        except Exception as e:
            logger.error(f"Rate limiter cleanup error: {e}")


# ── Decorator for Flask routes ──
def rate_limit(endpoint: str = 'default'):
    """Decorator to apply rate limiting to a Flask route."""
    def decorator(func):
        from functools import wraps
        from flask import request, jsonify
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Use user_id if authenticated, else IP
            key = str(getattr(request, 'user_id', None) or request.remote_addr or 'unknown')
            allowed, remaining = RateLimiter.is_allowed(key, endpoint)
            if not allowed:
                return jsonify({'error': 'Rate limit exceeded', 'retry_after': DEFAULT_LIMITS[endpoint]['window']}), 429
            return func(*args, **kwargs)
        return wrapper
    return decorator