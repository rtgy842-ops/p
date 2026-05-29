"""
web/routes/orders.py — User Orders Web View (Enterprise)
─────────────────────────────────────────────
Uses OrderRepository via ConnectionManager.
No direct sqlite3.connect() calls.
"""

import logging
from flask import Blueprint, render_template
from config import BOT_CONFIG

logger = logging.getLogger(__name__)

orders_bp = Blueprint('orders_web', __name__)


@orders_bp.route('/orders/<int:user_id>')
def user_orders(user_id):
    try:
        logger.info(f"Fetching orders for user_id: {user_id}")
        from db.repositories.order_repository import OrderRepository
        repo = OrderRepository()
        orders_data = repo.find_by_user(user_id)

        orders = []
        for order in orders_data:
            orders.append({
                'id': order['activation_id'] if isinstance(order, dict) else order[1],
                'phone_number': order['phone'] if isinstance(order, dict) else order[6] if len(order) > 6 else '',
                'service': order['service'] if isinstance(order, dict) else order[3] if len(order) > 3 else '',
                'country': order['country'] if isinstance(order, dict) else order[4] if len(order) > 4 else '',
                'price': order['price'] if isinstance(order, dict) else order[7] if len(order) > 7 else 0,
                'status': order['status'] if isinstance(order, dict) else order[8] if len(order) > 8 else '',
                'date': order['created_at'] if isinstance(order, dict) else order[9] if len(order) > 9 else '',
                'details_url': f"{BOT_CONFIG['website_url']}/number_details/{order['activation_id'] if isinstance(order, dict) else order[1]}"
            })

        return render_template('user_orders.html', orders=orders)
    except Exception as e:
        logger.error(f"Error in user_orders: {str(e)}")
        return f"System error: {str(e)}", 500