"""
compat/legacy_facade.py — Direct Enterprise Service Delegation (Post-Migration)
─────────────────────────────────────────────────
ALL operations now route directly to enterprise services.
Zero legacy code. Zero sqlite3.connect().
Kept for backward-compatible function signatures.
"""

import logging

from data.dto import PaymentGateway
from db.repositories.order_repository import OrderRepository
from services.order_service import OrderService
from services.payment_service import PaymentService
from services.sms_service import SMSService
from services.wallet_service import WalletService

logger = logging.getLogger(__name__)

_wallet = WalletService()
_sms = SMSService()
_order = OrderService()
_payment = PaymentService()
_order_repo = OrderRepository()


# ═══════════════════════════════════════════════════════════════
# Wallet Operations
# ═══════════════════════════════════════════════════════════════

def get_balance(user_id: int) -> int:
    return _wallet.get_balance(user_id)

def add_balance(user_id: int, amount: int, description: str = '', ref_id: str | None = None, admin_id: int | None = None) -> int | None:
    if admin_id:
        return _wallet.admin_add_balance(user_id, amount, admin_id)
    return _wallet.deposit(user_id, amount, description, ref_id)

def deduct_balance(user_id: int, amount: int, description: str = '') -> int | None:
    return _wallet.withdraw(user_id, amount, description)

def refund_balance(user_id: int, amount: int, description: str = '', ref_id: str | None = None) -> int | None:
    return _wallet.refund(user_id, amount, description, ref_id)

def admin_add_balance(user_id: int, amount: int, admin_id: int) -> int | None:
    return _wallet.admin_add_balance(user_id, amount, admin_id)

def admin_deduct_balance(user_id: int, amount: int, admin_id: int) -> int | None:
    return _wallet.admin_deduct_balance(user_id, amount, admin_id)

def get_wallet_info(user_id: int) -> dict | None:
    return _wallet.get_wallet_info(user_id)


# ═══════════════════════════════════════════════════════════════
# SMS Operations
# ═══════════════════════════════════════════════════════════════

def sms_get_prices(product: str):
    return _sms.get_price_info(product, 'any')

def sms_get_products(country: str = 'any', operator: str = 'any'):
    result = _sms.provider.get_numbers_status(country)
    if result and result.success:
        import json
        return json.loads(result.raw_response) if result.raw_response else None
    return None

def sms_buy_number(country: str, operator: str, product: str, **kwargs):
    result = _sms.buy_number(product, country, operator)
    if result and result.success and result.data:
        return {
            'success': True,
            'data': {
                'order_id': result.data.get('activation_id'),
                'phone': result.data.get('phone'),
                'operator': operator, 'product': product,
                'price': 0, 'status': 'PENDING', 'expires': '',
                'created_at': '', 'country': country
            }
        }
    return {'success': False, 'error': result.error if result else 'Unknown error'}

def sms_check_status(activation_id: int) -> dict:
    result = _sms.check_sms(activation_id)
    if result.success and result.data:
        return result.data
    return {'status': result.error or 'ERROR'}

def sms_cancel_number(activation_id: int) -> dict:
    result = _sms.cancel_number(activation_id)
    return {'success': result.success, 'error': result.error}

def sms_get_balance() -> float | None:
    return _sms.get_balance()


# ═══════════════════════════════════════════════════════════════
# Order Operations
# ═══════════════════════════════════════════════════════════════

def order_save(order_data: dict) -> int | None:
    return _order_repo.create(order_data)

def order_save_code(order_id: int, code: str) -> bool:
    return _order_repo.save_activation_code(order_id, code)

def order_update_status(order_id: int, status: str) -> bool:
    return _order_repo.update_status(order_id, status)

def order_cancel(activation_id: int) -> dict:
    order = _order_repo.find_by_activation_id(int(activation_id))
    if order:
        uid = order['user_id'] if isinstance(order, dict) else order[1]
        price = order['price'] if isinstance(order, dict) else order[7]
        st = order['status'] if isinstance(order, dict) else order[8]
        if (st or '').upper() != 'CANCELED':
            _order_repo.cancel_by_activation_id(int(activation_id))
            refund_balance(uid, price, 'Order cancellation refund', str(activation_id))
            return {'success': True}
    return {'success': False, 'error': 'Order not found or already cancelled'}


# ═══════════════════════════════════════════════════════════════
# Payment Operations
# ═══════════════════════════════════════════════════════════════

def payment_create_zarinpal(user_id: int, amount: int, description: str = '') -> tuple:
    result = _payment.initiate_payment(PaymentGateway.ZARINPAL, user_id, amount, description)
    if result.success:
        return True, result.payment_url, result.authority
    return False, None, None

def payment_verify_zarinpal(authority: str, amount: int, user_id: int = 0) -> tuple:
    """Verify ZarinPal payment and credit user. user_id is required."""
    result = _payment.verify_and_credit(PaymentGateway.ZARINPAL, authority, user_id, amount)
    if result.success:
        return True, result.ref_id
    return False, None
