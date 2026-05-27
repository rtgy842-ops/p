"""
web/routes/admin_api.py — Admin API + Test Endpoints
──────────────────────────────────────────────────────
Consolidates all /test_*, /api/*, /check_database, /backup_* routes.
All protected by @_require_admin decorator.
"""

import logging, sqlite3, os, json, time
from flask import Blueprint, request, jsonify, render_template
from functools import wraps
from config import BOT_CONFIG, DB_CONFIG

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
        conn = sqlite3.connect(DB_CONFIG['users_db']); conn.execute('SELECT 1'); conn.close()
        return jsonify({'success': True, 'message': '✅ اتصال به دیتابیس موفق'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'❌ خطا: {str(e)}'})

@admin_api_bp.route('/test_create_user', methods=['POST'])
@_require_admin
def test_create_user():
    try:
        data = request.get_json(); user_id = int(data['user_id'])
        conn = sqlite3.connect(DB_CONFIG['users_db']); conn.execute('INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0)', (user_id,)); conn.commit(); conn.close()
        return jsonify({'success': True, 'message': f'✅ کاربر {user_id} ایجاد شد'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@admin_api_bp.route('/test_add_balance', methods=['POST'])
@_require_admin
def test_add_balance():
    from compat.legacy_facade import add_balance as _add
    data = request.get_json()
    new_balance = _add(int(data['user_id']), int(data['amount']), description='تراکنش تست')
    if new_balance is not None: return jsonify({'success': True, 'message': f'✅ موجودی: {new_balance:,}'})
    return jsonify({'success': False, 'message': '❌ خطا'})

@admin_api_bp.route('/test_transaction', methods=['POST'])
@_require_admin
def test_transaction():
    from compat.legacy_facade import add_balance as _add
    data = request.get_json(); user_id = int(data['user_id']); amount = int(data['amount'])
    new_balance = _add(user_id, amount, description='تراکنش تست')
    if new_balance is None: return jsonify({'success': False, 'message': '❌ خطا'})
    return jsonify({'success': True, 'message': f'✅ موجودی جدید: {new_balance:,}'})

@admin_api_bp.route('/test_check_balance', methods=['POST'])
@_require_admin
def test_check_balance():
    data = request.get_json(); user_id = int(data['user_id'])
    from compat.legacy_facade import get_balance as _get
    balance = _get(user_id)
    return jsonify({'success': True, 'message': f'💰 موجودی: {balance:,}'})

@admin_api_bp.route('/test_payment')
@_require_admin
def test_payment_page():
    return render_template('test_payment.html')

@admin_api_bp.route('/recreate_transactions_table')
@_require_admin
def recreate_transactions_table():
    from database import setup_users_database
    if setup_users_database(): return jsonify({'success': True, 'message': '✅ جدول بازسازی شد'})
    return jsonify({'success': False, 'message': '❌ خطا'})

@admin_api_bp.route('/test_backup')
@_require_admin
def test_backup_page():
    return render_template('test_backup.html')

@admin_api_bp.route('/create_backup')
@_require_admin
def create_backup():
    from backup_manager import BackupManager
    bm = BackupManager(backup_interval=5)
    if bm.create_backup(): return jsonify({'success': True, 'message': '✅ پشتیبان ایجاد شد'})
    return jsonify({'success': False, 'message': '❌ خطا'})

@admin_api_bp.route('/restore_backup')
@_require_admin
def restore_backup():
    from backup_manager import BackupManager
    bm = BackupManager(backup_interval=5)
    if bm.restore_backup(): return jsonify({'success': True, 'message': '✅ بازیابی شد'})
    return jsonify({'success': False, 'message': '❌ خطا'})

@admin_api_bp.route('/backup_content')
@_require_admin
def backup_content():
    try:
        with open('data/users_backup.json', 'r', encoding='utf-8') as f: content = json.load(f)
        return jsonify({'success': True, 'content': content})
    except FileNotFoundError: return jsonify({'success': False, 'message': '❌ فایل یافت نشد'})
    except Exception as e: return jsonify({'success': False, 'message': str(e)})

@admin_api_bp.route('/backup_status')
@_require_admin
def backup_status():
    return jsonify({'success': True, 'message': '✅ سرویس فعال است'})

@admin_api_bp.route('/check_database')
@_require_admin
def check_database():
    conn = sqlite3.connect(DB_CONFIG['users_db']); cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*), SUM(balance) FROM users'); users_count, total_balance = cursor.fetchone()
    cursor.execute('SELECT user_id, balance FROM users ORDER BY user_id DESC LIMIT 5'); recent = cursor.fetchall()
    conn.close()
    return jsonify({'success': True, 'stats': {'total_users': users_count or 0, 'total_balance': total_balance or 0,
        'recent_users': [{'user_id': uid, 'balance': bal} for uid, bal in recent]}})

@admin_api_bp.route('/test_purchase')
@_require_admin
def test_purchase_page():
    return render_template('test_purchase.html')

@admin_api_bp.route('/test_purchase_number', methods=['POST'])
@_require_admin
def test_purchase_number():
    from compat.legacy_facade import deduct_balance as _deduct
    data = request.get_json(); service = data['service']; country = data['country']; number = data['number']
    test_user_id = 1457637832; price = 50000
    new_balance = _deduct(test_user_id, price, description='خرید تست')
    if new_balance is None: return jsonify({'success': False, 'message': 'خطا در بروزرسانی موجودی'})
    order_id = f'TEST{int(time.time())}'
    conn = sqlite3.connect(DB_CONFIG['users_db']); conn.execute('INSERT INTO orders (user_id, service, country, phone_number, price, status, order_id) VALUES (?, ?, ?, ?, ?, ?, ?)', (test_user_id, service, country, number, price, 'active', order_id)); conn.commit(); conn.close()
    return jsonify({'success': True, 'order_id': order_id, 'number': number, 'price': price, 'balance': new_balance})

@admin_api_bp.route('/price_calculator')
@_require_admin
def price_calculator():
    conn = sqlite3.connect('bot.db'); cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key='usd_rate'"); usd_rate = cursor.fetchone()[0]
    cursor.execute("SELECT value FROM settings WHERE key='profit_percentage'"); profit = cursor.fetchone()[0]
    conn.close()
    return render_template('price_calculator.html', usd_rate=usd_rate, profit_percentage=profit)

@admin_api_bp.route('/test_api_key')
@_require_admin
def test_api_key():
    from compat.legacy_facade import sms_get_balance
    balance = sms_get_balance()
    if balance is not None: return jsonify({'status': 'success', 'message': f'کلید معتبر — موجودی: {balance}'})
    return jsonify({'status': 'error', 'message': 'خطا'})

@admin_api_bp.route('/api/get_telegram_price/<country>')
@_require_admin
def get_telegram_price(country):
    import requests
    from config import COUNTRY_ID_MAP, SERVICE_CODE_MAP, HEROSMS_CONFIG
    country_id = COUNTRY_ID_MAP.get(country, country); service_code = SERVICE_CODE_MAP.get('telegram', 'tg')
    params = {'api_key': HEROSMS_CONFIG['api_key'], 'action': 'getPrices', 'country': country_id, 'service': service_code}
    response = requests.get(HEROSMS_CONFIG['api_url'], params=params, timeout=10)
    if response.status_code == 200:
        data = response.json()
        if country_id in data and service_code in data[country_id]:
            operators = data[country_id][service_code]; min_price = float('inf'); available = 0
            for od in operators.values():
                if od['count'] > 0 and od['cost'] < min_price: min_price = od['cost']; available = od['count']
            if min_price != float('inf'):
                conn = sqlite3.connect('admin.db'); cursor = conn.cursor()
                cursor.execute('SELECT value FROM settings WHERE key = "usd_rate"'); usd_rate = float(cursor.fetchone()[0] or 0)
                cursor.execute('SELECT value FROM settings WHERE key = "profit_percentage"'); profit = float(cursor.fetchone()[0] or 0)
                conn.close()
                price_toman = round(min_price * usd_rate * (1 + profit / 100))
                return jsonify({'status': 'موجود', 'price_usd': min_price, 'price_toman': price_toman, 'available_count': available})
    return jsonify({'status': 'خطا'})