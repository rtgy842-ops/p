"""
config/profiles.py — Environment Configuration Profiles
─────────────────────────────────────────────────
No more 'if DEBUG' everywhere.
Single source of truth for environment detection.

Usage:
    from config.profiles import Profile
    if Profile.is_production():
        # production-only code
"""

import os


class AppEnvironment:
    """Application environment constants."""
    DEVELOPMENT = 'development'
    STAGING = 'staging'
    PRODUCTION = 'production'


class Profile:
    """
    Static profile detector.
    Reads APP_ENV from environment, defaults to 'production'.
    """

    _env: str | None = None

    @classmethod
    def get(cls) -> str:
        if cls._env is None:
            cls._env = os.getenv('APP_ENV', AppEnvironment.PRODUCTION).lower()
        return cls._env

    @classmethod
    def is_production(cls) -> bool:
        return cls.get() == AppEnvironment.PRODUCTION

    @classmethod
    def is_staging(cls) -> bool:
        return cls.get() == AppEnvironment.STAGING

    @classmethod
    def is_development(cls) -> bool:
        return cls.get() == AppEnvironment.DEVELOPMENT

    @classmethod
    def is_debug(cls) -> bool:
        """Debug features enabled in dev/staging only."""
        return cls.get() in (AppEnvironment.DEVELOPMENT, AppEnvironment.STAGING)

    @classmethod
    def log_level(cls) -> str:
        levels = {
            AppEnvironment.DEVELOPMENT: 'DEBUG',
            AppEnvironment.STAGING: 'INFO',
            AppEnvironment.PRODUCTION: 'WARNING',
        }
        return levels.get(cls.get(), 'INFO')
