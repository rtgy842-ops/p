"""
services/payment_service.py — Payment Gateway Service
─────────────────────────────────────────────────
Gateway-based architecture for payment processing.
Zero Telegram dependencies — pure business logic.

Architecture:
    BasePaymentGateway (abstract)
    ├── ZarinPalGateway (online payment)
    ├── CardToCardGateway (manual card payment)
    └── Future gateways (Crypto, etc.)
"""

import logging
from abc import ABC, abstractmethod

import requests

from config import PAYMENT_CONFIG
from data.dto import PaymentGateway, PaymentResultDTO
from db.repositories.card_payment_repository import CardPaymentRepository
from db.repositories.transaction_repository import TransactionRepository
from db.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# BASE PAYMENT GATEWAY (Abstract)
# ═══════════════════════════════════════════════════════════════

class BasePaymentGateway(ABC):
    """Abstract base for all payment gateways."""

    gateway: PaymentGateway

    @abstractmethod
    def create_payment(self, user_id: int, amount: int,
                       description: str = '') -> PaymentResultDTO:
        """Initiate a payment. Returns payment_url for redirect."""
        ...

    @abstractmethod
    def verify_payment(self, authority: str, amount: int) -> PaymentResultDTO:
        """Verify a completed payment."""
        ...


# ═══════════════════════════════════════════════════════════════
# ZARINPAL GATEWAY
# ═══════════════════════════════════════════════════════════════

class ZarinPalGateway(BasePaymentGateway):
    """ZarinPal online payment gateway (v4 API)."""

    gateway = PaymentGateway.ZARINPAL

    def __init__(self):
        self.merchant_id = PAYMENT_CONFIG['zarinpal_merchant']
        self.sandbox = PAYMENT_CONFIG['sandbox_mode']
        self.callback_base = PAYMENT_CONFIG['callback_url']

        if self.sandbox:
            self._request_url = "https://sandbox.zarinpal.com/pg/v4/payment/request.json"
            self._payment_url = "https://sandbox.zarinpal.com/pg/StartPay/"
            self._verify_url = "https://sandbox.zarinpal.com/pg/v4/payment/verify.json"
        else:
            self._request_url = "https://payment.zarinpal.com/pg/v4/payment/request.json"
            self._payment_url = "https://payment.zarinpal.com/pg/StartPay/"
            self._verify_url = "https://payment.zarinpal.com/pg/v4/payment/verify.json"

    def create_payment(self, user_id: int, amount: int,
                       description: str = '', state_token: str = '') -> PaymentResultDTO:
        """Create a ZarinPal payment request. Pass state_token for CSRF protection."""
        try:
            callback = f"{self.callback_base}?user_id={user_id}&amount={amount}"
            if state_token:
                callback += f"&state={state_token}"
            data = {
                "merchant_id": self.merchant_id,
                "amount": amount * 10,  # Toman to Rial
                "description": description or f"شارژ حساب کاربر {user_id}",
                "callback_url": callback,
                "metadata": {
                    "mobile": str(user_id),
                    "email": "",
                    "order_id": f"charge_{user_id}"
                }
            }

            headers = {
                "accept": "application/json",
                "content-type": "application/json"
            }

            response = requests.post(
                self._request_url, json=data, headers=headers, timeout=15
            )
            result = response.json()

            if result.get('data', {}).get('code') == 100:
                authority = result['data']['authority']
                payment_url = f"{self._payment_url}{authority}"
                logger.info(f"ZarinPal payment created: {payment_url}")
                return PaymentResultDTO(
                    success=True,
                    gateway=self.gateway,
                    payment_url=payment_url,
                    authority=authority,
                )
            else:
                error = result.get('errors', {}).get('message', 'Unknown error')
                logger.error(f"ZarinPal payment creation failed: {error}")
                return PaymentResultDTO(
                    success=False,
                    gateway=self.gateway,
                    error_message=error,
                )

        except requests.exceptions.RequestException as e:
            logger.error(f"ZarinPal network error: {e}")
            return PaymentResultDTO(
                success=False,
                gateway=self.gateway,
                error_message=f"Network error: {e}"
            )
        except Exception as e:
            logger.error(f"ZarinPal unexpected error: {e}", exc_info=True)
            return PaymentResultDTO(
                success=False,
                gateway=self.gateway,
                error_message=str(e)
            )

    def verify_payment(self, authority: str, amount: int) -> PaymentResultDTO:
        """Verify a ZarinPal payment."""
        try:
            data = {
                "merchant_id": self.merchant_id,
                "amount": amount * 10,
                "authority": authority,
            }

            headers = {
                "accept": "application/json",
                "content-type": "application/json"
            }

            response = requests.post(
                self._verify_url, json=data, headers=headers, timeout=15
            )
            result = response.json()

            code = result.get('data', {}).get('code')
            if code in [100, 101]:  # 100=success, 101=already verified
                ref_id = result['data'].get('ref_id', '')
                logger.info(f"ZarinPal payment verified: ref_id={ref_id}")
                return PaymentResultDTO(
                    success=True,
                    gateway=self.gateway,
                    ref_id=str(ref_id),
                )
            else:
                error = result.get('errors', {}).get('message',
                          result.get('data', {}).get('message', 'Verification failed'))
                logger.error(f"ZarinPal verification failed: {error}")
                return PaymentResultDTO(
                    success=False,
                    gateway=self.gateway,
                    error_message=error,
                )

        except Exception as e:
            logger.error(f"ZarinPal verify error: {e}", exc_info=True)
            return PaymentResultDTO(
                success=False,
                gateway=self.gateway,
                error_message=str(e)
            )


# ═══════════════════════════════════════════════════════════════
# CARD-TO-CARD GATEWAY
# ═══════════════════════════════════════════════════════════════

class CardToCardGateway(BasePaymentGateway):
    """
    Card-to-card manual payment gateway.
    Creates a pending payment record. Admin approves/rejects later.
    """

    gateway = PaymentGateway.CARD_TO_CARD

    def __init__(self):
        self._card_payment_repo = CardPaymentRepository()

    def create_payment(self, user_id: int, amount: int,
                       description: str = '') -> PaymentResultDTO:
        """Create a pending card-to-card payment request."""
        try:
            payment_id = self._card_payment_repo.create(user_id, amount)
            if payment_id:
                logger.info(f"Card payment request created: {payment_id}")
                return PaymentResultDTO(
                    success=True,
                    gateway=self.gateway,
                    payment_id=payment_id,
                )
            else:
                return PaymentResultDTO(
                    success=False,
                    gateway=self.gateway,
                    error_message="Failed to create payment record"
                )
        except Exception as e:
            logger.error(f"Card payment creation error: {e}")
            return PaymentResultDTO(
                success=False,
                gateway=self.gateway,
                error_message=str(e)
            )

    def verify_payment(self, authority: str, amount: int) -> PaymentResultDTO:
        """Card-to-card verification is manual — always needs admin."""
        return PaymentResultDTO(
            success=False,
            gateway=self.gateway,
            error_message="Card-to-card requires manual admin verification"
        )


# ═══════════════════════════════════════════════════════════════
# PAYMENT SERVICE (Orchestrator)
# ═══════════════════════════════════════════════════════════════

class PaymentService:
    """
    High-level payment service.
    Routes to the correct gateway and handles balance updates.
    """

    def __init__(self):
        self._user_repo = UserRepository()
        self._txn_repo = TransactionRepository()
        self._card_repo = CardPaymentRepository()

        # Gateway registry
        self._gateways: dict[PaymentGateway, BasePaymentGateway] = {
            PaymentGateway.ZARINPAL: ZarinPalGateway(),
            PaymentGateway.CARD_TO_CARD: CardToCardGateway(),
        }

    def get_gateway(self, gateway: PaymentGateway) -> BasePaymentGateway:
        return self._gateways.get(gateway)

    def initiate_payment(self, gateway: PaymentGateway, user_id: int,
                         amount: int, description: str = '',
                         state_token: str = '') -> PaymentResultDTO:
        """Initiate a payment through the specified gateway. Pass state_token for CSRF."""
        gw = self.get_gateway(gateway)
        if gw is None:
            return PaymentResultDTO(
                success=False,
                gateway=gateway,
                error_message=f"Unknown gateway: {gateway}"
            )
        return gw.create_payment(user_id, amount, description, state_token=state_token)

    def verify_and_credit(self, gateway: PaymentGateway, authority: str,
                          user_id: int, amount: int) -> PaymentResultDTO:
        """
        Verify payment AND credit user balance atomically.
        
        IDEMPOTENT: Checks if authority already exists in transactions
        (double-callback protection). If already processed, returns success
        without modifying balance.
        """
        from db.context import db_context

        # ── IDEMPOTENCY GUARD: Check if this authority was already processed ──
        try:
            with db_context('default', transactional=False) as db:
                existing = db.fetchone(
                    "SELECT 1 FROM transactions WHERE ref_id = %s AND type = 'deposit'",
                    (authority,))
                if existing:
                    logger.info(
                        f"Idempotent: authority {authority} already processed — skipping")
                    return PaymentResultDTO(
                        success=True,
                        gateway=gateway,
                        ref_id=authority,
                        error_message=None,
                    )
        except Exception as e:
            logger.warning(f"Idempotency check failed: {e}")

        # ── Verify with gateway ──
        gw = self.get_gateway(gateway)
        if gw is None:
            return PaymentResultDTO(
                success=False,
                gateway=gateway,
                error_message=f"Unknown gateway: {gateway}"
            )

        result = gw.verify_payment(authority, amount)
        if not result.success:
            return result

        # ── ATOMIC: Lock row + update balance + record transaction ──
        ref_id = result.ref_id or result.payment_id or authority
        try:
            with db_context('default', transactional=True) as db:
                # Second idempotency check inside the transaction (belt + suspenders)
                existing = db.fetchone(
                    "SELECT 1 FROM transactions WHERE ref_id = %s AND type = 'deposit' FOR UPDATE",
                    (ref_id,))
                if existing:
                    logger.info(
                        f"Idempotent (in-txn): ref_id {ref_id} already credited")
                    # Fetch current balance for the already-credited case
                    balance_row = db.fetchone(
                        'SELECT balance FROM users WHERE user_id = %s', (user_id,))
                    bal = int(balance_row[0]) if balance_row else 0
                    return PaymentResultDTO(
                        success=True, gateway=gateway, ref_id=ref_id, new_balance=bal)

                # Lock user row for update
                row = db.fetchone(
                    'SELECT balance FROM users WHERE user_id = %s FOR UPDATE',
                    (user_id,))
                if row is None:
                    db.execute(
                        'INSERT INTO users (user_id, balance) VALUES (%s, %s) ON CONFLICT (user_id) DO NOTHING',
                        (user_id, amount))
                    new_balance = amount
                else:
                    new_balance = int(row[0]) + amount
                    db.execute(
                        'UPDATE users SET balance = %s WHERE user_id = %s',
                        (new_balance, user_id))

                # Record transaction in same DB transaction
                db.execute(
                    """INSERT INTO transactions (user_id, amount, type, description, ref_id)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (user_id, amount, 'deposit',
                     f'شارژ حساب از طریق {gateway.value}', ref_id))

            logger.info(
                f"Payment complete: user={user_id}, amount={amount}, gateway={gateway.value}, ref={ref_id}")
            return PaymentResultDTO(
                success=True, gateway=gateway, ref_id=ref_id, new_balance=new_balance)
        except Exception as e:
            logger.error(
                f"Balance credit failed after successful payment: user={user_id}, amount={amount}: {e}")
            return PaymentResultDTO(
                success=False,
                gateway=gateway,
                error_message="Payment verified but balance update failed"
            )

    def approve_card_payment(self, payment_id: str, admin_id: int) -> tuple[bool, int]:
        """
        Approve a card-to-card payment and credit user atomically.
        Returns (success, user_id_for_notification).
        """
        from db.context import db_context

        payment = self._card_repo.find_by_id(payment_id)
        if payment is None:
            return False, 0

        user_id = payment['user_id']
        amount = payment['amount']

        try:
            with db_context('default', transactional=True) as db:
                # Check if already approved (idempotency)
                status_row = db.fetchone(
                    "SELECT status FROM card_payments WHERE payment_id = %s FOR UPDATE",
                    (payment_id,))
                if status_row and status_row[0] == 'approved':
                    logger.warning(
                        f"Card payment {payment_id} already approved — idempotent skip")
                    return True, user_id

                # Approve the payment record
                db.execute(
                    """UPDATE card_payments
                       SET status = 'approved', admin_response = %s
                       WHERE payment_id = %s""",
                    (f'Approved by admin {admin_id}', payment_id))

                # Lock user row and credit
                row = db.fetchone(
                    'SELECT balance FROM users WHERE user_id = %s FOR UPDATE',
                    (user_id,))
                if row is None:
                    db.execute(
                        'INSERT INTO users (user_id, balance) VALUES (%s, %s) ON CONFLICT (user_id) DO NOTHING',
                        (user_id, amount))
                else:
                    new_balance = int(row[0]) + amount
                    db.execute(
                        'UPDATE users SET balance = %s WHERE user_id = %s',
                        (new_balance, user_id))

                # Record transaction
                db.execute(
                    """INSERT INTO transactions (user_id, amount, type, description, ref_id)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (user_id, amount, 'deposit',
                     'شارژ حساب از طریق کارت به کارت', payment_id))

                # Audit log
                db.execute(
                    """INSERT INTO audit_log (admin_id, action, target, details, created_at)
                       VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)""",
                    (admin_id, 'approve_card_payment', str(user_id),
                     f'Approved card payment {payment_id} for {amount}'))

            logger.info(
                f"Card payment approved: {payment_id}, user={user_id}, amount={amount}")
            return True, user_id
        except Exception as e:
            logger.error(f"Card payment approval failed: {payment_id}: {e}")
            return False, user_id

    def reject_card_payment(self, payment_id: str, reason: str) -> tuple[bool, int]:
        """Reject a card-to-card payment."""
        payment = self._card_repo.find_by_id(payment_id)
        if payment is None:
            return False, 0

        if self._card_repo.reject(payment_id, reason):
            logger.info(
                f"Card payment rejected: {payment_id}, reason={reason}")
            return True, payment['user_id']
        return False, 0
