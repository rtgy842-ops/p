"""
web/routes/orders.py — User Orders Web View
─────────────────────────────────────────────
/orders/<user_id> — displays user's order history.
"""

import logging, sqlite3
from flask import Blueprint, render_template
from config import BOT_CONFIG

logger = logging.getLogger(__name__)

orders_bp = Blueprint('orders_web', __name__)


@orders_bp.route('/orders/<int:user_id>')
def user_orders(user_id):
    try:
        logger.info(f"Fetching orders for user_id: {user_id}")
        conn = sqlite3.connect('bot.db')
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='orders'")
        if not cursor.fetchone():
            logger.error("Table 'orders' does not exist")
            return "جدول سفارش‌ها وجود ندارد", 500

        cursor.execute('''SELECT activation_id, phone, service, country, price, status, created_at
                          FROM orders WHERE user_id = ? ORDER BY created_at DESC''', (user_id,))
        orders_data = cursor.fetchall()
        logger.info(f"Found {len(orders_data)} orders for user {user_id}")
        conn.close()

        orders = []
        for order in orders_data:
            orders.append({
                'id': order[0], 'phone_number': order[1], 'service': order[2],
                'country': order[3], 'price': order[4], 'status': order[5],
                'date': order[6], 'details_url': f"{BOT_CONFIG['website_url']}/number_details/{order[0]}"
            })

        return render_template('user_orders.html', orders=orders)
    except Exception as e:
        logger.error(f"Error in user_orders: {str(e)}")
        return f"خطای سیستمی: {str(e)}", 500