"""
bot/middleware.py — Middleware Layer
─────────────────────────────────────────────────
Pre-handler processing pipeline.
All handlers are wrapped with these middlewares.

Architecture:
    Request → AuthMiddleware → LanguageMiddleware → LoggingMiddleware → Handler
"""

import logging
import time
from functools import wraps
from config import BOT_CONFIG

logger = logging.getLogger(__name__)


class MiddlewarePipeline:
    """
    Chain of middlewares that process every incoming update.
    """

    def __init__(self):
        self._middlewares: list[callable] = []

    def add(self, middleware: callable) -> None:
        """Add a middleware to the pipeline."""
        self._middlewares.append(middleware)

    def process(self, call) -> bool:
        """
        Run all middlewares. Returns False if any middleware blocks the request.
        """
        for mw in self._middlewares:
            try:
                if not mw(call):
                    return False
            except Exception as e:
                logger.error(f"Middleware error in {mw.__name__}: {e}")
                return False
        return True


# ── Built-in Middlewares ───────────────────────────────────────

def auth_middleware(call) -> bool:
    """
    Check if user is blocked.
    Returns True to allow, False to block.
    """
    user_id = getattr(call, 'from_user', None)
    if user_id is None:
        return True  # System messages

    uid = user_id.id
    # Admin check — admins always pass
    if uid in BOT_CONFIG['admin_ids']:
        return True

    # Block check (lazy — avoids import at module level)
    try:
        from db.repositories.user_repository import UserRepository
        repo = UserRepository()
        user = repo.find_by_id(uid)
        if user is not None:
            is_blocked = user[5] if len(user) > 5 else 0
            if is_blocked:
                logger.warning(f"Blocked user {uid} attempted to interact")
                return False
    except Exception as e:
        logger.error(f"auth_middleware DB error: {e}")
        # If DB check fails in production, BLOCK to be safe
        from config import IS_PRODUCTION
        if IS_PRODUCTION:
            return False

    return True


def language_middleware(call) -> bool:
    """
    Ensure user language is loaded.
    Doesn't block requests, just ensures user exists.
    """
    user_id = getattr(call, 'from_user', None)
    if user_id is None:
        return True

    try:
        from db.repositories.user_repository import UserRepository
        repo = UserRepository()
        repo.create_if_not_exists(user_id.id, 'fa')
    except Exception:
        pass

    return True


def logging_middleware(call) -> bool:
    """
    Log every incoming request with timing.
    """
    user_id = getattr(call, 'from_user', None)
    uid = user_id.id if user_id else 'SYSTEM'

    data = getattr(call, 'data', None) or ''
    logger.info(f"Request: user={uid}, data={data[:100]}")

    # Store start time for timing
    call._start_time = time.time()

    return True


# ── Default pipeline ───────────────────────────────────────────
default_pipeline = MiddlewarePipeline()
default_pipeline.add(logging_middleware)
default_pipeline.add(auth_middleware)
default_pipeline.add(language_middleware)