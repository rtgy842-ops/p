"""
web/routes/__init__.py — Web Route Blueprints Package
────────────────────────────────────────────────────────
Exports all Blueprint modules for the Flask app factory.
"""

from web.routes.admin_api import admin_api_bp
from web.routes.orders import orders_bp
from web.routes.payment import payment_bp
from web.routes.webhook import webhook_bp

__all__ = ['webhook_bp', 'orders_bp', 'payment_bp', 'admin_api_bp']
