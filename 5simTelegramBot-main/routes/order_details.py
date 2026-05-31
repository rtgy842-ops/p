"""
routes/order_details.py — Order Details (PostgreSQL)
"""

import logging

from flask import Blueprint, render_template

logger = logging.getLogger(__name__)
order_details_bp = Blueprint('order_details_bp', __name__)


def _cursor():
    from db.connection import ConnectionManager
    cm = ConnectionManager.get_instance()
    conn = cm.get_connection('default')
    return conn.cursor(), conn, cm


@order_details_bp.app_template_filter('format_number')
def format_number(value):
    return "{:,}".format(value)


@order_details_bp.route('/number_details/<order_id>')
def number_details(order_id):
    try:
        cursor, conn, cm = _cursor()
        cursor.execute(
            'SELECT id, phone, service, country, operator, price, status, created_at, user_id, activation_id FROM orders WHERE id = %s',
            (order_id,))
        order = cursor.fetchone()
        if not order:
            cm.put_connection(conn)
            return render_template('order_status.html', status_type="error", title="Not found", message="Order not found.", user_id=None)

        order_data = {
            'id': order[0], 'phone_number': order[1], 'service': order[2], 'country': order[3],
            'operator': order[4], 'price': order[5], 'status': order[6], 'date': order[7],
            'user_id': order[8], 'activation_id': order[9], 'codes': []
        }

        cursor.execute('SELECT code, created_at FROM activation_codes WHERE order_id = %s ORDER BY created_at DESC', (order_id,))
        codes = cursor.fetchall()
        if codes:
            order_data['codes'] = [{'code': c[0], 'time': str(c[1])} for c in codes]

        cm.put_connection(conn)

        status = (order_data['status'] or '').lower()
        if status in ('canceled', 'cancelled'):
            return render_template('order_status.html', status_type="canceled", title="Cancelled", message="Order cancelled.", user_id=order_data['user_id'])
        elif order_data['codes']:
            cv = order_data['codes'][0]['code']
            return render_template('order_status.html', status_type="success", title="Code Received", message=f"Code: <div class='code-value'>{cv}</div>", user_id=order_data['user_id'])

        return render_template('number_details.html', order=order_data)
    except Exception as e:
        logger.error(f"Error: {e}")
        return render_template('order_status.html', status_type="error", title="Error", message=str(e), user_id=None)
