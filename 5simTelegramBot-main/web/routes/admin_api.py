"""
web/routes/admin_api.py — Admin API + Test Endpoints (Enterprise)
──────────────────────────────────────────────────────
All protected by @_require_admin. Uses enterprise repositories.
No direct sqlite3.connect() calls.
"""

import logging, os, json, time
from flask import Blueprint, request, jsonify, render_template
from functools import wraps
from config import BOT_CONFIG

logger = logging.getLogger(__name__)

admin_api_bp = Blueprint('admin_api', __name__)


def _require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        admin_token = request.headers.get('X-Admin-Token', '')
        admin_id_str = request.args.get('admin_id', '')
        if admin_token == BOT_CONFIG['token']:
            return f(*args, **kwargs)
        if admin_id_str.isdigit() and int(admin_id_str) in BOT_CONFIG['admin_ids']:
            return f(*args, **kwargs)
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    return decorated


@admin_api_bp.route('/test_db_connection')
@_require_admin
def test_db_connection():
    try:
        from db.connection import ConnectionManager
        cm = ConnectionManager.get_instance()
        stats = cm.get_stats()
        return jsonify({'success': True, 'message': f'Connected — {stats["active_connections"]} active connections'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@admin_api_bp.route('/test_create_user', methods=['POST'])
@_require_admin
def test_create_user():
    try:
        data = request.get_json()
        user_id = int(data['user_id'])
        from db.repositories.user_repository import UserRepository
        repo = UserRepository()
        repo.create_if_not_exists(user_id)
        return jsonify({'success': True, 'message': f'User {user_id} created'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@admin_api_bp.route('/test_add_balance', methods=['POST'])
@_require_admin
def test_add_balance():
    from compat.legacy_facade import add_balance as _add
    data = request.get_json()
    new_balance = _add(int(data['user_id']), int(data['amount']), description='Test transaction')
    if new_balance is not None:
        return jsonify({'success': True, 'message': f'Balance: {new_balance:,}'})
    return jsonify({'success': False, 'message': 'Error'})


@admin_api_bp.route('/test_transaction', methods=['POST'])
@_require_admin
def test_transaction():
    from compat.legacy_facade import add_balance as _add
    data = request.get_json()
    user_id = int(data['user_id'])
    amount = int(data['amount'])
    new_balance = _add(user_id, amount, description='Test transaction')
    if new_balance is None:
        return jsonify({'success': False, 'message': 'Error'})
    return jsonify({'success': True, 'message': f'New balance: {new_balance:,}'})


@admin_api_bp.route('/test_check_balance', methods=['POST'])
@_require_admin
def test_check_balance():
    data = request.get_json()
    user_id = int(data['user_id'])
    from compat.legacy_facade import get_balance as _get
    balance = _get(user_id)
    return jsonify({'success': True, 'message': f'Balance: {balance:,}'})


@admin_api_bp.route('/test_payment')
@_require_admin
def test_payment_page():
    return render_template('test_payment.html')


@admin_api_bp.route('/recreate_transactions_table')
@_require_admin
def recreate_transactions_table():
    from database import setup_users_database
    if setup_users_database():
        return jsonify({'success': True, 'message': 'Table recreated'})
    return jsonify({'success': False, 'message': 'Error'})


@admin_api_bp.route('/test_backup')
@_require_admin
def test_backup_page():
    return render_template('test_backup.html')


@admin_api_bp.route('/create_backup')
@_require_admin
def create_backup():
    from backup_manager import BackupManager
    bm = BackupManager(backup_interval=5)
    if bm.create_backup():
        return jsonify({'success': True, 'message': 'Backup created'})
    return jsonify({'success': False, 'message': 'Error'})


@admin_api_bp.route('/restore_backup')
@_require_admin
def restore_backup():
    from backup_manager import BackupManager
    bm = BackupManager(backup_interval=5)
    if bm.restore_backup():
        return jsonify({'success': True, 'message': 'Restored'})
    return jsonify({'success': False, 'message': 'Error'})


@admin_api_bp.route('/backup_content')
@_require_admin
def backup_content():
    try:
        with open('data/users_backup.json', 'r', encoding='utf-8') as f:
            content = json.load(f)
        return jsonify({'success': True, 'content': content})
    except FileNotFoundError:
        return jsonify({'success': False, 'message': 'File not found'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@admin_api_bp.route('/backup_status')
@_require_admin
def backup_status():
    return jsonify({'success': True, 'message': 'Service active'})


@admin_api_bp.route('/check_database')
@_require_admin
def check_database():
    from db.repositories.user_repository import UserRepository
    repo = UserRepository()
    total_users = repo.count_all()
    recent = repo.list_recent(5)
    return jsonify({
        'success': True,
        'stats': {
            'total_users': total_users,
            'total_balance': 'N/A',
            'recent_users': [
                {'user_id': r['user_id'] if isinstance(r, dict) else r[0],
                 'balance': r['balance'] if isinstance(r, dict) else r[1]}
                for r in recent
            ]
        }
    })


@admin_api_bp.route('/test_purchase')
@_require_admin
def test_purchase_page():
    return render_template('test_purchase.html')


@admin_api_bp.route('/test_purchase_number', methods=['POST'])
@_require_admin
def test_purchase_number():
    from compat.legacy_facade import deduct_balance as _deduct
    data = request.get_json()
    service = data['service']
    country = data['country']
    number = data['number']
    test_user_id = 8683874068
    price = 50000
    new_balance = _deduct(test_user_id, price, description='Test purchase')
    if new_balance is None:
        return jsonify({'success': False, 'message': 'Balance update failed'})
    order_id = f'TEST{int(time.time())}'
    from db.connection import ConnectionManager
    cm = ConnectionManager.get_instance()
    conn = cm.get_connection('users_db')
    conn.execute(
        'INSERT INTO orders (user_id, service, country, phone_number, price, status, order_id) VALUES (?, ?, ?, ?, ?, ?, ?)',
        (test_user_id, service, country, number, price, 'active', order_id))
    conn.commit()
    return jsonify({'success': True, 'order_id': order_id, 'number': number, 'price': price, 'balance': new_balance})


@admin_api_bp.route('/price_calculator')
@_require_admin
def price_calculator():
    from db.repositories.settings_repository import SettingsRepository
    repo = SettingsRepository()
    usd_rate = repo.get('usd_rate') or '0'
    profit = repo.get('profit_percentage') or '30'
    return render_template('price_calculator.html', usd_rate=usd_rate, profit_percentage=profit)


@admin_api_bp.route('/test_api_key')
@_require_admin
def test_api_key():
    from compat.legacy_facade import sms_get_balance
    balance = sms_get_balance()
    if balance is not None:
        return jsonify({'status': 'success', 'message': f'Valid key — Balance: {balance}'})
    return jsonify({'status': 'error', 'message': 'Error'})


@admin_api_bp.route('/api/get_telegram_price/<country>')
@_require_admin
def get_telegram_price(country):
    import requests
    from config import COUNTRY_ID_MAP, SERVICE_CODE_MAP, HEROSMS_CONFIG
    country_id = COUNTRY_ID_MAP.get(country, country)
    service_code = SERVICE_CODE_MAP.get('telegram', 'tg')
    params = {'api_key': HEROSMS_CONFIG['api_key'], 'action': 'getPrices', 'country': country_id, 'service': service_code}
    response = requests.get(HEROSMS_CONFIG['api_url'], params=params, timeout=10)
    if response.status_code == 200:
        data = response.json()
        if country_id in data and service_code in data[country_id]:
            operators = data[country_id][service_code]
            min_price = float('inf')
            available = 0
            for od in operators.values():
                if od['count'] > 0 and od['cost'] < min_price:
                    min_price = od['cost']
                    available = od['count']
            if min_price != float('inf'):
                from db.repositories.settings_repository import SettingsRepository
                repo = SettingsRepository()
                usd_rate = float(repo.get('usd_rate') or 0)
                profit = float(repo.get('profit_percentage') or 0)
                price_toman = round(min_price * usd_rate * (1 + profit / 100))
                return jsonify({'status': 'available', 'price_usd': min_price, 'price_toman': price_toman, 'available_count': available})
    return jsonify({'status': 'error'})