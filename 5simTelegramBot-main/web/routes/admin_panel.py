"""
web/routes/admin_panel.py — Professional Web Admin Panel
─────────────────────────────────────────────────
Flask Blueprint serving the admin dashboard.
Accessible via secure link from Admin Bot.
"""

import os
from functools import wraps

from flask import Blueprint, jsonify, render_template, request, session

admin_panel_bp = Blueprint('admin_panel', __name__, template_folder='../../templates')

ADMIN_API_TOKEN = os.getenv('ADMIN_API_TOKEN', '')


def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.args.get('token') or session.get('admin_token')
        if not ADMIN_API_TOKEN or token != ADMIN_API_TOKEN:
            return jsonify({'error': 'Unauthorized'}), 401
        session['admin_token'] = token
        return f(*args, **kwargs)
    return decorated


# ── Dashboard ─────────────────────────────────────────────

@admin_panel_bp.route('/admin')
@require_admin
def dashboard():
    return render_template('admin/dashboard.html')


@admin_panel_bp.route('/admin/api/dashboard')
@require_admin
def api_dashboard():
    from services.admin_service import AdminService
    from services.analytics_service import analytics
    from services.catalog_manager import catalog as cat
    from services.provider_registry import provider_registry

    admin = AdminService()
    stats = admin.get_stats()
    analytics_d = analytics.get_dashboard()
    providers = provider_registry.get_stats()
    cat_stats = cat.get_stats()

    return jsonify({
        'users': {'total': stats['total_users']},
        'revenue': analytics_d.get('revenue', {}),
        'orders': analytics_d.get('orders', {}),
        'providers': providers,
        'catalog': cat_stats,
        'active_users_7d': analytics_d.get('active_users_7d', 0),
    })


# ── Users ─────────────────────────────────────────────────

@admin_panel_bp.route('/admin/api/users')
@require_admin
def api_users():
    from services.subscription_service import subscriptions
    from services.user_service import UserService

    user_svc = UserService()
    users = user_svc.list_recent(100)
    result = []
    for u in users:
        uid = u.user_id if hasattr(u, 'user_id') else u[0]
        tier = subscriptions.get_tier(uid)
        result.append({
            'user_id': uid,
            'balance': u.balance if hasattr(u, 'balance') else 0,
            'language': u.language if hasattr(u, 'language') else 'fa',
            'is_blocked': u.is_blocked if hasattr(u, 'is_blocked') else False,
            'subscription': tier.value,
            'join_date': str(u.join_date) if hasattr(u, 'join_date') else '',
        })
    return jsonify({'users': result})


# ── Orders ────────────────────────────────────────────────

@admin_panel_bp.route('/admin/api/orders')
@require_admin
def api_orders():
    from db.context import db_context
    with db_context('default', transactional=False) as db:
        rows = db.fetchall(
            "SELECT id, user_id, activation_id, service, country, operator, phone, price, status, created_at "
            "FROM orders ORDER BY created_at DESC LIMIT 100"
        )
    result = [
        {'id': r[0], 'user_id': r[1], 'activation_id': r[2], 'service': r[3],
         'country': r[4], 'operator': r[5], 'phone': r[6], 'price': r[7],
         'status': r[8], 'created_at': str(r[9])}
        for r in rows
    ]
    return jsonify({'orders': result})


# ── Payments ──────────────────────────────────────────────

@admin_panel_bp.route('/admin/api/payments')
@require_admin
def api_payments():
    from db.repositories.card_payment_repository import CardPaymentRepository
    repo = CardPaymentRepository()
    payments = repo.list_paginated(0, 100)
    result = [
        {'payment_id': p[0], 'user_id': p[1], 'amount': p[2], 'status': p[3], 'created_at': str(p[4])}
        for p in payments
    ]
    return jsonify({'payments': result})


# ── Audit Log ─────────────────────────────────────────────

@admin_panel_bp.route('/admin/api/audit')
@require_admin
def api_audit():
    from services.admin_service import AdminService
    admin = AdminService()
    entries = admin.get_audit_log(100)
    return jsonify({'audit': entries})


# ── System Health ─────────────────────────────────────────

@admin_panel_bp.route('/admin/api/health')
@require_admin
def api_health():
    import time

    from services.provider_registry import provider_registry

    health_data = {
        'status': 'ok',
        'timestamp': time.time(),
        'database': 'connected',
        'providers': provider_registry.get_all_health(),
    }

    try:
        from db.connection import ConnectionManager
        cm = ConnectionManager.get_instance()
        conn = cm.get_connection('default')
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        cm.put_connection(conn)
    except Exception as e:
        health_data['database'] = f'error: {e}'
        health_data['status'] = 'degraded'

    return jsonify(health_data)


# ── Providers ─────────────────────────────────────────────

@admin_panel_bp.route('/admin/api/providers')
@require_admin
def api_providers():
    from services.provider_registry import provider_registry
    from services.provider_sync import provider_sync

    return jsonify({
        'providers': provider_registry.get_all_health(),
        'sync_status': provider_sync.get_sync_status(),
    })


# ── Currencies ────────────────────────────────────────────

@admin_panel_bp.route('/admin/api/currencies')
@require_admin
def api_currencies():
    from db.context import db_context
    with db_context('default', transactional=False) as db:
        rows = db.fetchall(
            "SELECT id, code, name, symbol, rate_to_usd, is_active, is_default FROM currencies ORDER BY code"
        )
    result = [
        {'id': r[0], 'code': r[1], 'name': r[2], 'symbol': r[3],
         'rate_to_usd': float(r[4]), 'is_active': bool(r[5]), 'is_default': bool(r[6])}
        for r in rows
    ]
    return jsonify({'currencies': result})


@admin_panel_bp.route('/admin/api/currencies/update', methods=['POST'])
@require_admin
def api_currency_update():
    data = request.json
    code = data.get('code')
    rate = data.get('rate_to_usd')
    active = data.get('is_active')

    if not code or rate is None:
        return jsonify({'error': 'Missing code or rate'}), 400

    from db.context import db_context
    try:
        with db_context('default', transactional=True) as db:
            db.execute(
                "UPDATE currencies SET rate_to_usd = %s, is_active = %s, updated_at = CURRENT_TIMESTAMP WHERE code = %s",
                (rate, 1 if active else 0, code)
            )
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
