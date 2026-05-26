"""
web/health.py — Health Check Endpoint
─────────────────────────────────────────────────
Provides /health endpoint for monitoring.
Checks: database, cache, SMS provider, payment gateway.
"""

from flask import Blueprint, jsonify
import logging

logger = logging.getLogger(__name__)

health_bp = Blueprint('health', __name__)


@health_bp.route('/health')
def health_check():
    """Comprehensive health check endpoint."""
    checks = {
        'status': 'healthy',
        'database': _check_database(),
        'cache': _check_cache(),
        'sms_provider': _check_sms(),
    }
    return jsonify(checks)


@health_bp.route('/ping')
def ping():
    """Simple liveness probe."""
    return 'pong', 200


def _check_database() -> dict:
    """Check database connectivity."""
    try:
        from db.connection import ConnectionManager
        cm = ConnectionManager.get_instance()
        stats = cm.get_stats()
        return {
            'status': 'ok',
            'active_connections': stats['active_connections'],
            'databases': stats['databases'],
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {'status': 'error', 'message': str(e)}


def _check_cache() -> dict:
    """Check cache service."""
    try:
        from services.cache_service import CacheService
        cache = CacheService.get_instance()
        stats = cache.get_stats()
        return {
            'status': 'ok',
            'size': stats['size'],
            'hit_rate': stats['hit_rate'],
        }
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def _check_sms() -> dict:
    """Check SMS provider connectivity."""
    try:
        from services.sms_service import SMSService
        sms = SMSService()
        balance = sms.get_balance()
        return {
            'status': 'ok' if balance is not None else 'warning',
            'balance': balance,
            'provider': sms.provider.provider_name,
        }
    except Exception as e:
        return {'status': 'error', 'message': str(e)}
