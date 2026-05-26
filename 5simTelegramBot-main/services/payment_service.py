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
import requests
from abc import ABC, abstractmethod
from config import PAYMENT_CONFIG, BOT_CONFIG, DB_CONFIG
from data.dto import PaymentResultDTO, PaymentGateway
from db.repositories.user_repository import UserRepository
from db.repositories.transaction_repository import TransactionRepository
from db.repositories.card_payment_repository import CardPaymentRepository

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
                       description: str = '') -> PaymentResultDTO:
        """Create a ZarinPal payment request."""
        try:
            data = {
                "merchant_id": self.merchant_id,
                "amount": amount * 10,  # Toman to Rial
                "description": description or f"شارژ حساب کاربر {user_id}",
                "callback_url": f"{self.callback_base}?user_id={user_id}&amount={amount}",
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
                         amount: int, description: str = '') -> PaymentResultDTO:
        """Initiate a payment through the specified gateway."""
        gw = self.get_gateway(gateway)
        if gw is None:
            return PaymentResultDTO(
                success=False,
                gateway=gateway,
                error_message=f"Unknown gateway: {gateway}"
            )
        return gw.create_payment(user_id, amount, description)

    def verify_and_credit(self, gateway: PaymentGateway, authority: str,
                          user_id: int, amount: int) -> PaymentResultDTO:
        """
        Verify payment AND credit user balance atomically.
        This ensures payment verification and balance update are coupled.
        """
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

        # Credit user balance
        new_balance = self._user_repo.add_balance(user_id, amount)
        if new_balance is None:
            logger.error(f"Failed to credit balance after successful payment: user={user_id}, amount={amount}")
            return PaymentResultDTO(
                success=False,
                gateway=gateway,
                error_message="Payment verified but balance update failed"
            )

        # Record transaction
        self._txn_repo.create(
            user_id=user_id,
            amount=amount,
            type_trans='deposit',
            description=f'شارژ حساب از طریق {gateway.value}',
            ref_id=result.ref_id or result.payment_id
        )

        logger.info(f"Payment complete: user={user_id}, amount={amount}, gateway={gateway.value}")
        return result

    def approve_card_payment(self, payment_id: str, admin_id: int) -> tuple[bool, int]:
        """
        Approve a card-to-card payment and credit user.
        Returns (success, user_id_for_notification).
        """
        payment = self._card_repo.find_by_id(payment_id)
        if payment is None:
            return False, 0

        user_id = payment['user_id']
        amount = payment['amount']

        # Approve the payment record
        if not self._card_repo.approve(payment_id, admin_id):
            return False, user_id

        # Credit user
        new_balance = self._user_repo.add_balance(user_id, amount)
        if new_balance is None:
            logger.error(f"Balance update failed after card payment approval: {payment_id}")
            return False, user_id

        # Record transaction
        self._txn_repo.create(
            user_id=user_id,
            amount=amount,
            type_trans='deposit',
            description='شارژ حساب از طریق کارت به کارت',
            ref_id=payment_id
        )

        logger.info(f"Card payment approved: {payment_id}, user={user_id}, amount={amount}")
        return True, user_id

    def reject_card_payment(self, payment_id: str, reason: str) -> tuple[bool, int]:
        """Reject a card-to-card payment."""
        payment = self._card_repo.find_by_id(payment_id)
        if payment is None:
            return False, 0

        if self._card_repo.reject(payment_id, reason):
            logger.info(f"Card payment rejected: {payment_id}, reason={reason}")
            return True, payment['user_id']
        return False, 0
