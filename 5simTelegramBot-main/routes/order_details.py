"""
routes/order_details.py — Order Details Routes (Enterprise Refactored)
─────────────────────────────────────────────────
All database access now uses ConnectionManager + OrderRepository.
No direct sqlite3.connect() calls.
"""

from flask import Blueprint, render_template, request, jsonify
import logging
import datetime
import requests
from config import HEROSMS_CONFIG
from bot_utils import send_message_to_bot

logger = logging.getLogger(__name__)

order_details_bp = Blueprint('order_details_bp', __name__)


@order_details_bp.app_template_filter('format_number')
def format_number(value):
    return "{:,}".format(value)


def _get_order_repo():
    from db.repositories.order_repository import OrderRepository
    return OrderRepository()


def _get_bot_cursor():
    from db.connection import ConnectionManager
    cm = ConnectionManager.get_instance()
    conn = cm.get_connection('bot_db')
    return conn.cursor(), conn


@order_details_bp.route('/number_details/<order_id>')
def number_details(order_id):
    try:
        cursor, conn = _get_bot_cursor()
        cursor.execute("""
            SELECT id, phone, service, country, operator,
                   price, status, created_at, user_id, activation_id
            FROM orders WHERE id = ?
        """, (order_id,))
        order = cursor.fetchone()

        if not order:
            return render_template('order_status.html',
                                   status_type="error",
                                   title="Order not found",
                                   message="Order not found in the system.",
                                   user_id=None)

        order_data = {
            'id': order['id'],
            'phone_number': order['phone'],
            'service': order['service'],
            'country': order['country'],
            'operator': order['operator'],
            'price': order['price'],
            'status': order['status'],
            'date': order['created_at'],
            'user_id': order['user_id'],
            'activation_id': order['activation_id'],
            'codes': []
        }

        has_codes = False
        try:
            cursor.execute("""
                SELECT code, created_at FROM activation_codes
                WHERE order_id = ? ORDER BY created_at DESC
            """, (order_id,))
            codes = cursor.fetchall()
            if codes:
                has_codes = True
                order_data['codes'] = [{'code': c['code'], 'time': c['created_at']} for c in codes]
        except Exception as e:
            logger.warning(f"Could not fetch activation codes: {e}")

        status = (order_data['status'] or '').lower()
        created_time = datetime.datetime.strptime(str(order_data['date'] or ''), '%Y-%m-%d %H:%M:%S')
        time_diff = datetime.datetime.now() - created_time
        time_expired = time_diff > datetime.timedelta(minutes=20)

        if status in ('canceled', 'cancelled'):
            return render_template('order_status.html',
                                   status_type="canceled",
                                   title="Order Cancelled",
                                   message="This order has been cancelled.",
                                   user_id=order_data['user_id'])
        elif has_codes:
            code_value = order_data['codes'][0]['code']
            return render_template('order_status.html',
                                   status_type="success",
                                   title="Activation Code Received",
                                   message=f"Activation code: <div class='code-value'>{code_value}</div>",
                                   user_id=order_data['user_id'])
        elif time_expired and status == 'pending':
            return render_template('order_status.html',
                                   status_type="expired",
                                   title="Order Expired",
                                   message="This order has expired.",
                                   user_id=order_data['user_id'])

        return render_template('number_details.html', order=order_data)

    except Exception as e:
        logger.error(f"Error in number_details: {e}")
        return render_template('order_status.html',
                               status_type="error",
                               title="System Error",
                               message=f"Error: {e}",
                               user_id=None)


@order_details_bp.route('/orders/<user_id>')
def user_orders(user_id):
    try:
        cursor, conn = _get_bot_cursor()
        cursor.execute("""
            SELECT id, phone, service, country, operator,
                   price, status, created_at
            FROM orders WHERE user_id = ?
            ORDER BY created_at DESC
        """, (user_id,))
        orders = cursor.fetchall()

        orders_data = []
        for order in orders:
            orders_data.append({
                'id': order['id'],
                'phone_number': order['phone'],
                'service': order['service'],
                'country': order['country'],
                'operator': order['operator'],
                'price': order['price'],
                'status': order['status'],
                'date': order['created_at']
            })

        return render_template('user_orders.html', orders=orders_data, user_id=user_id)
    except Exception as e:
        logger.error(f"Error in user_orders: {e}")
        return f"Error: {e}", 500


@order_details_bp.route('/check_code/<order_id>', methods=['GET'])
def check_code(order_id):
    try:
        cursor, conn = _get_bot_cursor()
        cursor.execute("""
            SELECT code, created_at FROM activation_codes
            WHERE order_id = ? ORDER BY created_at DESC LIMIT 1
        """, (order_id,))
        code = cursor.fetchone()

        if code:
            return jsonify({'code_received': True, 'code': code['code'], 'time': code['created_at']})
        return jsonify({'code_received': False})
    except Exception as e:
        logger.error(f"Error in check_code: {e}")
        return jsonify({'code_received': False, 'error': str(e)}), 500


@order_details_bp.route('/cancel_order/<order_id>')
def cancel_order(order_id):
    try:
        from bot import refund_order_amount

        cursor, conn = _get_bot_cursor()
        cursor.execute('SELECT user_id, price, status, activation_id FROM orders WHERE id = ?', (order_id,))
        order_info = cursor.fetchone()

        if not order_info:
            return jsonify({'success': False, 'message': 'Order not found'})

        user_id = order_info['user_id']
        price = order_info['price']
        status = order_info['status']
        activation_id = order_info['activation_id']

        if (status or '').lower() in ('canceled', 'cancelled'):
            return jsonify({'success': False, 'message': 'Order already cancelled'})

        # Cancel via the SMS provider
        cancel_params = {
            'api_key': HEROSMS_CONFIG['api_key'],
            'action': 'setStatus',
            'id': activation_id,
            'status': '8'
        }
        api_response = requests.get(HEROSMS_CONFIG['api_url'], params=cancel_params, timeout=30)
        if api_response.status_code != 200 or 'ACCESS_CANCEL' not in api_response.text:
            logger.error(f"SMS provider cancel failed: {api_response.text}")
            return jsonify({'success': False, 'message': f'SMS provider error: {api_response.text}'})

        success, result = refund_order_amount(activation_id)
        if not success:
            return jsonify({'success': False, 'message': f'Refund error: {result}'})

        # Notify user via Telegram
        try:
            if isinstance(result, dict):
                refund_amount = result.get('refund_amount', price)
                new_balance = result.get('new_balance', 0)
                msg = f"Order #{order_id} cancelled\nBalance: {new_balance:,} Toman\nRefund: {refund_amount:,} Toman"
            else:
                msg = f"Order #{order_id} cancelled\nRefund: {result:,} Toman"
            send_message_to_bot(user_id, msg)
        except Exception as e:
            logger.warning(f"Could not notify user: {e}")

        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"Error in cancel_order: {e}")
        return jsonify({'success': False, 'message': str(e)})
