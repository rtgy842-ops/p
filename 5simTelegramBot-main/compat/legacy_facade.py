"""
compat/legacy_facade.py — Balance Operations Facade
─────────────────────────────────────────────────────
TEMPORARY module — deleted in Phase G (Legacy Shutdown).

Routes balance operations to either legacy or new code based on
feature flags. During migration, uses DUAL-WRITE to verify parity.
After migration, feature flags switch to new-only.
"""

import logging
from services.feature_flags import is_migration_enabled

logger = logging.getLogger(__name__)

# Lazy imports to avoid circular dependencies
_wallet_service = None
_user_repo = None
_txn_repo = None


def _get_wallet_service():
    global _wallet_service
    if _wallet_service is None:
        from services.wallet_service import WalletService
        _wallet_service = WalletService()
    return _wallet_service


def _get_user_repo():
    global _user_repo
    if _user_repo is None:
        from db.repositories.user_repository import UserRepository
        _user_repo = UserRepository()
    return _user_repo


def _get_txn_repo():
    global _txn_repo
    if _txn_repo is None:
        from db.repositories.transaction_repository import TransactionRepository
        _txn_repo = TransactionRepository()
    return _txn_repo


# ── Dual-Write Helpers ─────────────────────────────────────────

def _dual_write_verify(user_id: int, legacy_result, new_result,
                       operation: str) -> None:
    """
    Compare legacy and new results. Log mismatches.
    During migration, new_result wins but we alert on discrepancies.
    """
    if legacy_result is None and new_result is None:
        return  # Both failed — OK
    if legacy_result != new_result:
        logger.error(
            f"BALANCE MISMATCH [{operation}]: user={user_id}, "
            f"legacy_result={legacy_result}, new_result={new_result}"
        )


# ── Public API (used by bot.py during migration) ───────────────

def get_balance(user_id: int) -> int:
    """Get user balance. Routes to WalletService if flag is enabled."""
    if is_migration_enabled('use_new_wallet_service'):
        try:
            return _get_wallet_service().get_balance(user_id)
        except Exception as e:
            logger.error(f"WalletService.get_balance failed: {e}, falling back to legacy")
            # Fall back to legacy
            from database import get_user_balance as legacy_get_balance
            return legacy_get_balance(user_id)
    else:
        from database import get_user_balance as legacy_get_balance
        return legacy_get_balance(user_id)


def add_balance(user_id: int, amount: int,
                description: str = '',
                ref_id: str | None = None,
                admin_id: int | None = None) -> int | None:
    """
    Add balance. During dual-write phase, writes to BOTH legacy and new.
    Retains all transaction recording in both systems for verification.
    """
    # Always write to legacy first (existing production code path)
    from database import add_balance as legacy_add_balance
    from database import save_transaction as legacy_save_txn

    legacy_result = legacy_add_balance(user_id, amount)
    if legacy_result is not None:
        legacy_save_txn(user_id, amount, 'deposit', description or 'افزایش موجودی', ref_id)

    # If new wallet flag enabled, also write through new service
    if is_migration_enabled('use_new_wallet_service'):
        try:
            wallet = _get_wallet_service()
            if admin_id is not None:
                new_result = wallet.admin_add_balance(user_id, amount, admin_id)
            else:
                new_result = wallet.deposit(user_id, amount, description, ref_id)
            _dual_write_verify(user_id, legacy_result, new_result, 'add_balance')
        except Exception as e:
            logger.error(f"WalletService deposit failed during dual-write: {e}")

    return legacy_result


def deduct_balance(user_id: int, amount: int,
                   description: str = '') -> int | None:
    """
    Deduct balance for a purchase.
    During dual-write, both systems are updated.
    """
    # Legacy path
    from database import add_balance as legacy_add_balance
    from database import save_transaction as legacy_save_txn

    legacy_result = legacy_add_balance(user_id, -amount)
    if legacy_result is not None:
        legacy_save_txn(user_id, amount, 'purchase', description or 'خرید شماره مجازی')

    # New path
    if is_migration_enabled('use_new_wallet_service'):
        try:
            wallet = _get_wallet_service()
            new_result = wallet.withdraw(user_id, amount, description)
            _dual_write_verify(user_id, legacy_result, new_result, 'deduct_balance')
        except Exception as e:
            logger.error(f"WalletService withdraw failed during dual-write: {e}")

    return legacy_result


def refund_balance(user_id: int, amount: int,
                   description: str = '',
                   ref_id: str | None = None) -> int | None:
    """
    Refund money to user (order cancellation).
    Dual-write to both systems.
    """
    # Legacy path
    from database import add_balance as legacy_add_balance
    from database import save_transaction as legacy_save_txn

    legacy_result = legacy_add_balance(user_id, amount)
    if legacy_result is not None:
        legacy_save_txn(user_id, amount, 'refund', description or 'بازگشت وجه', ref_id)

    # New path
    if is_migration_enabled('use_new_wallet_service'):
        try:
            wallet = _get_wallet_service()
            new_result = wallet.refund(user_id, amount, description, ref_id)
            _dual_write_verify(user_id, legacy_result, new_result, 'refund_balance')
        except Exception as e:
            logger.error(f"WalletService refund failed during dual-write: {e}")

    return legacy_result


def admin_add_balance(user_id: int, amount: int, admin_id: int) -> int | None:
    """Admin manually adds balance. Audited operation."""
    return add_balance(user_id, amount,
                       description=f'Admin {admin_id} added balance',
                       admin_id=admin_id)


def admin_deduct_balance(user_id: int, amount: int, admin_id: int) -> int | None:
    """Admin manually deducts balance. Audited operation."""
    from database import add_balance as legacy_add_balance
    from database import save_transaction as legacy_save_txn

    legacy_result = legacy_add_balance(user_id, -amount)
    if legacy_result is not None:
        legacy_save_txn(user_id, amount, 'admin_deduct',
                        f'Admin {admin_id} deducted balance')

    if is_migration_enabled('use_new_wallet_service'):
        try:
            wallet = _get_wallet_service()
            new_result = wallet.admin_deduct_balance(user_id, amount, admin_id)
            _dual_write_verify(user_id, legacy_result, new_result, 'admin_deduct')
        except Exception as e:
            logger.error(f"WalletService admin_deduct failed: {e}")

    return legacy_result


def get_wallet_info(user_id: int) -> dict | None:
    """Get full wallet info: balance, deposits, spent, last transaction."""
    if is_migration_enabled('use_new_wallet_service'):
        try:
            return _get_wallet_service().get_wallet_info(user_id)
        except Exception as e:
            logger.error(f"WalletService.get_wallet_info failed: {e}")

    # Fall back to legacy
    from wallet import Wallet
    w = Wallet()
    return w.get_wallet_info(user_id)


# ═══════════════════════════════════════════════════════════════
# SMS SERVICE COMPAT LAYER (Phase B)
# ═══════════════════════════════════════════════════════════════

_sms_service = None


def _get_sms_service():
    global _sms_service
    if _sms_service is None:
        from services.sms_service import SMSService
        _sms_service = SMSService()
    return _sms_service


def sms_get_prices(product: str):
    """
    Compat wrapper for legacy get_prices(product).
    Maps to SMSService.get_price_info() when flag enabled.
    Returns dict format matching legacy expectation.
    """
    if is_migration_enabled('use_new_sms_service'):
        try:
            sms = _get_sms_service()
            # Legacy get_prices expects a dict response — SMSService returns PriceInfoDTO
            # We call get_numbers_status for broad availability
            result = sms.provider.get_numbers_status()
            if result.success:
                import json
                return json.loads(result.raw_response)
        except Exception as e:
            logger.error(f"SMSService.get_prices failed: {e}")

    # Fall back to legacy
    from config import HEROSMS_CONFIG, SERVICE_CODE_MAP
    import requests
    try:
        service_code = SERVICE_CODE_MAP.get(product, product)
        params = {
            'api_key': HEROSMS_CONFIG['api_key'],
            'action': 'getPrices',
            'service': service_code
        }
        response = requests.get(HEROSMS_CONFIG['api_url'], params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Legacy get_prices failed: {e}")
        return None


def sms_get_products(country: str = 'any', operator: str = 'any'):
    """
    Compat wrapper for legacy get_products(country, operator).
    """
    if is_migration_enabled('use_new_sms_service'):
        try:
            sms = _get_sms_service()
            result = sms.provider.get_numbers_status(country)
            if result.success:
                import json
                return json.loads(result.raw_response)
        except Exception as e:
            logger.error(f"SMSService.get_products failed: {e}")

    # Fall back to legacy
    from config import HEROSMS_CONFIG, COUNTRY_ID_MAP
    import requests
    try:
        params = {
            'api_key': HEROSMS_CONFIG['api_key'],
            'action': 'getNumbersStatus'
        }
        if country != 'any':
            country_id = COUNTRY_ID_MAP.get(country, country)
            params['country'] = country_id
        response = requests.get(HEROSMS_CONFIG['api_url'], params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Legacy get_products failed: {e}")
        return None


def sms_buy_number(country: str, operator: str, product: str,
                   forwarding=False, forwarding_number=None, reuse=None,
                   voice=None, ref=None, max_price=None) -> dict:
    """
    Compat wrapper for legacy buy_activation_number().
    Returns dict with 'success', 'data' (or 'error') keys — matching legacy format.
    """
    if is_migration_enabled('use_new_sms_service'):
        try:
            sms = _get_sms_service()
            result = sms.buy_number(product, country, operator)
            if result.success and result.data:
                return {
                    'success': True,
                    'data': {
                        'order_id': result.data.get('activation_id'),
                        'phone': result.data.get('phone'),
                        'operator': operator,
                        'product': product,
                        'price': 0,
                        'status': 'PENDING',
                        'expires': '',
                        'created_at': '',
                        'country': country
                    }
                }
            else:
                return {
                    'success': False,
                    'error': result.error or 'Unknown error'
                }
        except Exception as e:
            logger.error(f"SMSService.buy_number failed: {e}")

    # Fall back to legacy — inline the full legacy implementation
    from config import HEROSMS_CONFIG, COUNTRY_ID_MAP, SERVICE_CODE_MAP
    import requests
    try:
        country_id = COUNTRY_ID_MAP.get(country, country)
        service_code = SERVICE_CODE_MAP.get(product, product)
        params = {
            'api_key': HEROSMS_CONFIG['api_key'],
            'action': 'getNumber',
            'service': service_code,
            'country': country_id
        }
        if operator and operator != 'any':
            params['operator'] = operator
        response = requests.get(HEROSMS_CONFIG['api_url'], params=params, timeout=30)
        resp_text = response.text.strip()

        if resp_text == 'NO_NUMBERS':
            return {'success': False, 'error': 'NO_NUMBERS'}
        elif resp_text == 'NO_BALANCE':
            return {'success': False, 'error': 'NO_BALANCE'}
        elif resp_text.startswith('ERROR'):
            return {'success': False, 'error': resp_text}
        elif resp_text.startswith('ACCESS_NUMBER:'):
            parts = resp_text.split(':')
            return {
                'success': True,
                'data': {
                    'order_id': parts[1],
                    'phone': parts[2],
                    'operator': operator,
                    'product': product,
                    'price': 0,
                    'status': 'PENDING',
                    'expires': '',
                    'created_at': '',
                    'country': country
                }
            }
        else:
            return {'success': False, 'error': f'Unexpected: {resp_text}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def sms_check_status(activation_id: int) -> dict:
    """
    Compat wrapper for checking SMS status (legacy get_code flow).
    Returns dict with 'status' and optional 'code'.
    """
    if is_migration_enabled('use_new_sms_service'):
        try:
            sms = _get_sms_service()
            result = sms.check_sms(activation_id)
            if result.success and result.data:
                return result.data  # {'code': '...', 'status': 'RECEIVED'} or {'status': 'WAITING'}
            return {'status': 'ERROR', 'error': result.error}
        except Exception as e:
            logger.error(f"SMSService.check_sms failed: {e}")

    # Fall back to legacy
    from config import HEROSMS_CONFIG
    import requests
    try:
        params = {
            'api_key': HEROSMS_CONFIG['api_key'],
            'action': 'getStatus',
            'id': activation_id
        }
        response = requests.get(HEROSMS_CONFIG['api_url'], params=params, timeout=30)
        resp_text = response.text.strip()

        if resp_text.startswith('STATUS_OK:'):
            parts = resp_text.split(':')
            return {'status': 'RECEIVED', 'code': parts[1] if len(parts) > 1 else ''}
        elif resp_text in ('STATUS_WAIT_CODE', 'STATUS_WAIT_RETRY'):
            return {'status': 'WAITING'}
        elif resp_text == 'STATUS_CANCEL':
            return {'status': 'CANCELLED'}
        else:
            return {'status': resp_text}
    except Exception as e:
        return {'status': 'ERROR', 'error': str(e)}


def sms_cancel_number(activation_id: int) -> dict:
    """
    Compat wrapper for canceling a number.
    Returns dict with 'success' and optional 'error'.
    """
    if is_migration_enabled('use_new_sms_service'):
        try:
            sms = _get_sms_service()
            result = sms.cancel_number(activation_id)
            return {'success': result.success, 'error': result.error}
        except Exception as e:
            logger.error(f"SMSService.cancel_number failed: {e}")

    # Fall back to legacy
    from config import HEROSMS_CONFIG
    import requests
    try:
        params = {
            'api_key': HEROSMS_CONFIG['api_key'],
            'action': 'setStatus',
            'id': activation_id,
            'status': '8'
        }
        response = requests.get(HEROSMS_CONFIG['api_url'], params=params, timeout=30)
        if response.status_code == 200 and 'ACCESS_CANCEL' in response.text:
            return {'success': True}
        return {'success': False, 'error': response.text.strip()}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def sms_get_balance() -> float | None:
    """Get provider account balance."""
    if is_migration_enabled('use_new_sms_service'):
        try:
            return _get_sms_service().get_balance()
        except Exception as e:
            logger.error(f"SMSService.get_balance failed: {e}")

    from config import HEROSMS_CONFIG
    import requests
    try:
        params = {'api_key': HEROSMS_CONFIG['api_key'], 'action': 'getBalance'}
        response = requests.get(HEROSMS_CONFIG['api_url'], params=params, timeout=10)
        if 'ACCESS_BALANCE' in response.text:
            return float(response.text.strip().split(':')[1])
    except Exception as e:
        logger.error(f"Legacy get_balance failed: {e}")
    return None


# ═══════════════════════════════════════════════════════════════
# PAYMENT SERVICE COMPAT LAYER (Phase D)
# ═══════════════════════════════════════════════════════════════

_payment_service = None


def _get_payment_service():
    global _payment_service
    if _payment_service is None:
        from services.payment_service import PaymentService
        _payment_service = PaymentService()
    return _payment_service


def payment_create_zarinpal(user_id: int, amount: int,
                            description: str = '') -> tuple[bool, str | None, str | None]:
    """
    Create a ZarinPal payment. Returns (success, payment_url, authority).
    Compatible with legacy format: (True, url, auth) or (False, None, None)
    """
    if is_migration_enabled('use_new_payment_service'):
        try:
            from data.dto import PaymentGateway
            svc = _get_payment_service()
            result = svc.initiate_payment(PaymentGateway.ZARINPAL, user_id, amount, description)
            if result.success:
                return True, result.payment_url, result.authority
            return False, None, None
        except Exception as e:
            logger.error(f"PaymentService.zarinpal failed: {e}")

    # Legacy fallback — inline the full ZarinPal payment creation
    from config import PAYMENT_CONFIG
    import requests, time
    try:
        data = {
            "merchant_id": PAYMENT_CONFIG['zarinpal_merchant'],
            "amount": amount * 10,
            "description": description or f"شارژ حساب کاربر {user_id}",
            "callback_url": f"{PAYMENT_CONFIG['callback_url']}/{user_id}/{amount}",
            "metadata": {"mobile": str(user_id), "email": "", "order_id": f"charge_{user_id}_{int(time.time())}"}
        }
        base_url = "https://sandbox.zarinpal.com" if PAYMENT_CONFIG['sandbox_mode'] else "https://payment.zarinpal.com"
        response = requests.post(f"{base_url}/pg/v4/payment/request.json", json=data,
                                 headers={'accept': 'application/json', 'content-type': 'application/json'})
        result = response.json()
        if result.get('data', {}).get('code') == 100:
            authority = result['data']['authority']
            return True, f"{base_url}/pg/StartPay/{authority}", authority
        return False, None, None
    except Exception as e:
        logger.error(f"Legacy ZarinPal create failed: {e}")
        return False, None, None


def payment_verify_zarinpal(authority: str, amount: int) -> tuple[bool, str | None]:
    """
    Verify a ZarinPal payment. Returns (success, ref_id).
    """
    if is_migration_enabled('use_new_payment_service'):
        try:
            from data.dto import PaymentGateway
            svc = _get_payment_service()
            from compat.legacy_facade import _get_user_repo
            # verify_and_credit handles verify + balance in one call
            result = svc.verify_and_credit(PaymentGateway.ZARINPAL, authority, 0, amount)
            if result.success:
                # Credit was done inside verify_and_credit, but we need to also call our compat
                return True, result.ref_id
            return False, None
        except Exception as e:
            logger.error(f"PaymentService.verify failed: {e}")

    # Legacy fallback
    from config import PAYMENT_CONFIG
    import requests
    try:
        data = {"merchant_id": PAYMENT_CONFIG['zarinpal_merchant'], "amount": int(amount) * 10, "authority": authority}
        base_url = "https://sandbox.zarinpal.com" if PAYMENT_CONFIG['sandbox_mode'] else "https://payment.zarinpal.com"
        response = requests.post(f"{base_url}/pg/v4/payment/verify.json", json=data,
                                 headers={'accept': 'application/json', 'content-type': 'application/json'})
        result = response.json()
        if result.get('data', {}).get('code') in [100, 101]:
            return True, result['data'].get('ref_id', '')
        return False, None
    except Exception as e:
        logger.error(f"Legacy ZarinPal verify failed: {e}")
        return False, None


# ═══════════════════════════════════════════════════════════════
# ORDER SERVICE COMPAT LAYER (Phase C)
# ═══════════════════════════════════════════════════════════════

_order_service = None
_order_repo = None


def _get_order_service():
    global _order_service
    if _order_service is None:
        from services.order_service import OrderService
        _order_service = OrderService()
    return _order_service


def _get_order_repo():
    global _order_repo
    if _order_repo is None:
        from db.repositories.order_repository import OrderRepository
        _order_repo = OrderRepository()
    return _order_repo


def order_save(order_data: dict) -> int | None:
    """
    Save an order using OrderRepository (enterprise).
    Returns local order_id or None.
    """
    try:
        from db.repositories.order_repository import OrderRepository
        repo = OrderRepository()
        legacy_id = repo.create(order_data)
        return legacy_id
    except Exception as e:
        logger.error(f"Order save failed: {e}")
        return None


def order_save_code(order_id: int, code: str) -> bool:
    """Save activation code using OrderRepository."""
    try:
        from db.repositories.order_repository import OrderRepository
        repo = OrderRepository()
        return repo.save_activation_code(order_id, code)
    except Exception as e:
        logger.error(f"Save activation code failed: {e}")
        return False


def order_update_status(order_id: int, status: str) -> bool:
    """Update order status using OrderRepository."""
    try:
        from db.repositories.order_repository import OrderRepository
        repo = OrderRepository()
        return repo.update_status(order_id, status)
    except Exception as e:
        logger.error(f"Order status update failed: {e}")
        return False


def order_cancel(activation_id: int) -> dict:
    """
    Cancel order by activation_id. Returns {'success': bool, 'error': str}.
    Uses OrderRepository for cancel + WalletService for refund.
    """
    try:
        from db.repositories.order_repository import OrderRepository
        repo = OrderRepository()
        order = repo.find_by_activation_id(int(activation_id))
        if order:
            user_id = order['user_id'] if isinstance(order, dict) else order[1]
            price = order['price'] if isinstance(order, dict) else order[7]
            status = order['status'] if isinstance(order, dict) else order[8]
            if (status or '').upper() != 'CANCELED':
                repo.cancel_by_activation_id(int(activation_id))
                refund_balance(user_id, price, 'Order cancellation refund', str(activation_id))
                return {'success': True}
        return {'success': False, 'error': 'Order not found or already cancelled'}
    except Exception as e:
        logger.error(f"Order cancel failed: {e}")
        return {'success': False, 'error': str(e)}