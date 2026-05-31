"""
web/routes/orders.py — User Orders (PostgreSQL)
"""

import logging

from flask import Blueprint, render_template

from config import BOT_CONFIG

logger = logging.getLogger(__name__)
orders_bp = Blueprint('orders_web', __name__)


@orders_bp.route('/orders/<int:user_id>')
def user_orders(user_id):
    try:
        from db.repositories.order_repository import OrderRepository
        repo = OrderRepository()
        orders_data = repo.find_by_user(user_id)
        orders = []
        for o in orders_data:
            orders.append({
                'id': o[1], 'phone_number': o[5], 'service': o[3],
                'country': o[4], 'price': o[6], 'status': o[7],
                'date': str(o[8]) if o[8] else '',
                'details_url': f"{BOT_CONFIG['website_url']}/number_details/{o[1]}"
            })
        return render_template('user_orders.html', orders=orders)
    except Exception as e:
        logger.error(f"Error: {e}")
        return f"Error: {e}", 500
