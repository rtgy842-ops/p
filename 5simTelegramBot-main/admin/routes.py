"""
admin/routes.py — Admin API Blueprint
─────────────────────────────────────────────────
RESTful admin API for:
- Dashboard analytics
- User management
- Order management
- Payment approval
- Settings
- Audit log

All endpoints require admin authentication (via X-Admin-Token or admin_id).
"""

from flask import Blueprint, jsonify, request
import logging

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin_api', __name__, url_prefix='/api/admin')


# ── Auth Helper ────────────────────────────────────────────────
def _require_admin():
    """Check admin authentication and return admin_id or error."""
    from config import BOT_CONFIG

    admin_token = request.headers.get('X-Admin-Token', '')
    admin_id_str = request.args.get('admin_id', '')

    if admin_token == BOT_CONFIG['token']:
        return BOT_CONFIG['admin_ids'][0] if BOT_CONFIG['admin_ids'] else 0

    if admin_id_str.isdigit() and int(admin_id_str) in BOT_CONFIG['admin_ids']:
        return int(admin_id_str)

    return None


# ── Dashboard ──────────────────────────────────────────────────

@admin_bp.route('/dashboard')
def dashboard():
    """Get the admin dashboard with all analytics."""
    admin_id = _require_admin()
    if admin_id is None:
        return jsonify({'error': 'Unauthorized'}), 403

    from services.analytics_service import analytics
    data = analytics.get_dashboard()
    return jsonify({'success': True, 'data': data})


# ── Users ──────────────────────────────────────────────────────

@admin_bp.route('/users')
def list_users():
    admin_id = _require_admin()
    if admin_id is None:
        return jsonify({'error': 'Unauthorized'}), 403

    from services.user_service import UserService
    us = UserService()
    limit = request.args.get('limit', 20, type=int)
    users = us.list_recent(limit)
    return jsonify({
        'success': True,
        'users': [
            {'user_id': u.user_id, 'balance': u.balance, 'language': u.language}
            for u in users
        ]
    })


@admin_bp.route('/users/<int:user_id>')
def get_user(user_id: int):
    admin_id = _require_admin()
    if admin_id is None:
        return jsonify({'error': 'Unauthorized'}), 403

    from services.user_service import UserService
    us = UserService()
    user = us.get_user(user_id)
    if user is None:
        return jsonify({'error': 'User not found'}), 404

    return jsonify({
        'success': True,
        'user': {
            'user_id': user.user_id,
            'balance': user.balance,
            'language': user.language,
            'is_blocked': user.is_blocked,
        }
    })


# ── Orders ─────────────────────────────────────────────────────

@admin_bp.route('/orders')
def list_orders():
    admin_id = _require_admin()
    if admin_id is None:
        return jsonify({'error': 'Unauthorized'}), 403

    from services.order_service import OrderService
    os_service = OrderService()
    user_id = request.args.get('user_id', type=int)
    limit = request.args.get('limit', 20, type=int)

    if user_id:
        orders = os_service.get_user_orders(user_id, limit)
    else:
        orders = os_service.get_user_orders(0, limit)

    return jsonify({
        'success': True,
        'orders': [
            {
                'id': o.id, 'user_id': o.user_id,
                'service': o.service, 'country': o.country,
                'phone': o.phone, 'price': o.price,
                'status': o.status.value,
            }
            for o in orders
        ]
    })


# ── Payments ───────────────────────────────────────────────────

@admin_bp.route('/payments')
def list_payments():
    admin_id = _require_admin()
    if admin_id is None:
        return jsonify({'error': 'Unauthorized'}), 403

    from services.admin_service import AdminService
    as_service = AdminService()
    offset = request.args.get('offset', 0, type=int)
    limit = request.args.get('limit', 10, type=int)
    payments = as_service.get_card_payments(offset, limit)

    return jsonify({
        'success': True,
        'payments': [dict(p) for p in payments] if payments else [],
    })


# ── Settings ───────────────────────────────────────────────────

@admin_bp.route('/settings')
def get_settings():
    admin_id = _require_admin()
    if admin_id is None:
        return jsonify({'error': 'Unauthorized'}), 403

    from services.admin_service import AdminService
    as_service = AdminService()
    return jsonify({
        'success': True,
        'usd_rate': as_service.get_usd_rate(),
        'profit_percentage': as_service.get_profit_percentage(),
    })


# ── Audit ──────────────────────────────────────────────────────

@admin_bp.route('/audit')
def get_audit():
    admin_id = _require_admin()
    if admin_id is None:
        return jsonify({'error': 'Unauthorized'}), 403

    from services.admin_service import AdminService
    as_service = AdminService()
    limit = request.args.get('limit', 50, type=int)
    logs = as_service.get_audit_log(limit)

    return jsonify({'success': True, 'audit_log': logs})


# ── Health ─────────────────────────────────────────────────────

@admin_bp.route('/health')
def admin_health():
    admin_id = _require_admin()
    if admin_id is None:
        return jsonify({'error': 'Unauthorized'}), 403

    from web.health import health_check
    return health_check()
