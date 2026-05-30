"""
web/app.py — Flask App Factory
───────────────────────────────
Creates the Flask application with all Blueprints registered.
Replaces inline Flask setup in bot.py.
"""

from flask import Flask
from web.health import health_bp


def create_app(bot_instance=None, debug=False):
    """
    Create and configure the Flask application.
    
    Args:
        bot_instance: TeleBot instance for webhook handler injection
        debug: Enable debug mode
    """
    app = Flask(__name__, static_folder='static')
    app.config['DEBUG'] = debug

    # Health check endpoints
    app.register_blueprint(health_bp)

    # Webhook (receives Telegram updates)
    from web.routes.webhook import webhook_bp, init as webhook_init
    if bot_instance:
        webhook_init(bot_instance)
    app.register_blueprint(webhook_bp)

    # Payment verification callback
    from web.routes.payment import payment_bp, init as payment_init
    if bot_instance:
        payment_init(bot_instance)
    app.register_blueprint(payment_bp)

    # User orders web view
    from web.routes.orders import orders_bp
    app.register_blueprint(orders_bp)

    # Admin API + test endpoints
    from web.routes.admin_api import admin_api_bp
    app.register_blueprint(admin_api_bp)

    # Enterprise Admin Panel
    from web.routes.admin_panel import admin_panel_bp
    app.register_blueprint(admin_panel_bp)

    # Legacy order details blueprint
    from routes.order_details import order_details_bp
    app.register_blueprint(order_details_bp)

    # Template filter
    @app.template_filter('format_number')
    def format_number(value):
        return "{:,}".format(value)

    return app