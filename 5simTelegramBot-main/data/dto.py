"""
data/dto.py — Data Transfer Objects / Typed Schemas
─────────────────────────────────────────────────
Typed dataclasses for all core entities.
MANDATORY: Services must use these, NOT raw dicts.

Eliminates arbitrary dict passing between layers.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


# ── Order State Machine ────────────────────────────────────────
class OrderStatus(str, Enum):
    """Unified order status — the SINGLE source of truth."""
    CREATED = 'CREATED'
    PENDING = 'PENDING'
    PAID = 'PAID'
    PROCESSING = 'PROCESSING'
    WAITING_SMS = 'WAITING_SMS'
    COMPLETED = 'COMPLETED'
    CANCELLED = 'CANCELLED'
    REFUNDED = 'REFUNDED'
    FAILED = 'FAILED'

    @classmethod
    def active_states(cls) -> list['OrderStatus']:
        return [cls.CREATED, cls.PENDING, cls.PAID, cls.PROCESSING, cls.WAITING_SMS]

    @classmethod
    def terminal_states(cls) -> list['OrderStatus']:
        return [cls.COMPLETED, cls.CANCELLED, cls.REFUNDED, cls.FAILED]

    def is_active(self) -> bool:
        return self in self.active_states()

    def is_terminal(self) -> bool:
        return self in self.terminal_states()


# ── User DTO ───────────────────────────────────────────────────
@dataclass
class UserDTO:
    user_id: int
    balance: int = 0
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    language: str = 'fa'
    is_blocked: bool = False
    join_date: Optional[str] = None

    @classmethod
    def from_row(cls, row) -> 'UserDTO':
        """Create from sqlite3.Row or dict."""
        if row is None:
            return None
        return cls(
            user_id=row['user_id'],
            balance=row.get('balance', 0),
            username=row.get('username'),
            first_name=row.get('first_name'),
            last_name=row.get('last_name'),
            language=row.get('language', 'fa'),
            is_blocked=bool(row.get('is_blocked', 0)),
            join_date=row.get('join_date'),
        )


# ── Order DTO ──────────────────────────────────────────────────
@dataclass
class OrderDTO:
    id: Optional[int] = None
    user_id: int = 0
    activation_id: Optional[int] = None
    service: str = ''
    country: str = ''
    operator: str = ''
    phone: str = ''
    price: int = 0
    status: OrderStatus = OrderStatus.CREATED
    created_at: Optional[str] = None

    @classmethod
    def from_row(cls, row) -> 'OrderDTO':
        if row is None:
            return None
        status_raw = row.get('status', 'CREATED') or 'CREATED'
        try:
            status = OrderStatus(status_raw.upper())
        except ValueError:
            status = OrderStatus.CREATED
        return cls(
            id=row.get('id'),
            user_id=row.get('user_id', 0),
            activation_id=row.get('activation_id'),
            service=row.get('service', ''),
            country=row.get('country', ''),
            operator=row.get('operator', ''),
            phone=row.get('phone', ''),
            price=row.get('price', 0),
            status=status,
            created_at=row.get('created_at'),
        )


# ── Transaction DTO ────────────────────────────────────────────
class TransactionType(str, Enum):
    DEPOSIT = 'deposit'
    PURCHASE = 'purchase'
    REFUND = 'refund'
    ADMIN_ADD = 'admin_add'
    ADMIN_DEDUCT = 'admin_deduct'


@dataclass
class TransactionDTO:
    id: Optional[int] = None
    user_id: int = 0
    amount: int = 0
    type: TransactionType = TransactionType.DEPOSIT
    description: str = ''
    ref_id: Optional[str] = None
    timestamp: Optional[str] = None


# ── Payment DTO ────────────────────────────────────────────────
class PaymentStatus(str, Enum):
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'


@dataclass
class PaymentRequestDTO:
    """Card-to-card payment request."""
    payment_id: Optional[str] = None
    user_id: int = 0
    amount: int = 0
    status: PaymentStatus = PaymentStatus.PENDING
    receipt: Optional[str] = None
    admin_response: Optional[str] = None
    created_at: Optional[str] = None


class PaymentGateway(str, Enum):
    ZARINPAL = 'zarinpal'
    CARD_TO_CARD = 'card_to_card'


@dataclass
class PaymentResultDTO:
    """Result of a payment operation."""
    success: bool
    gateway: PaymentGateway
    payment_url: Optional[str] = None
    authority: Optional[str] = None  # ZarinPal authority
    ref_id: Optional[str] = None
    payment_id: Optional[str] = None  # Card-to-card payment_id
    error_message: Optional[str] = None


# ── SMS / Number Purchase DTO ──────────────────────────────────
@dataclass
class SMSProviderResponse:
    """Normalized response from any SMS provider."""
    success: bool
    provider: str = ''
    data: Optional[dict] = None
    error: Optional[str] = None
    raw_response: Optional[str] = None


@dataclass
class PriceInfoDTO:
    """Price information for a service+country combo."""
    service: str = ''
    country: str = ''
    country_name: str = ''
    operator: str = ''
    price_usd: float = 0.0
    price_toman: int = 0
    available_count: int = 0


@dataclass
class PurchaseResultDTO:
    """Result of a number purchase operation."""
    success: bool
    order_id: Optional[int] = None       # local DB id
    activation_id: Optional[int] = None  # provider's id
    phone: Optional[str] = None
    service: str = ''
    country: str = ''
    operator: str = ''
    price: int = 0
    error: Optional[str] = None
