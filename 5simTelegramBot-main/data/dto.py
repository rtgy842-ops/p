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


def _row_to_mapping(row, columns: list[str]) -> dict:
    """Normalize a DB row to a dict.

    Repositories use psycopg2's default cursor which returns plain tuples,
    but several DTO.from_row() methods were written assuming dict-like rows
    (row['col'] / row.get('col')). This helper bridges both:
      - dict / RealDictRow → returned as-is (copied to plain dict)
      - tuple / list / sqlite3.Row → zipped against the provided column order
    """
    if row is None:
        return {}
    # Dict-like (psycopg2 RealDictRow, sqlite3.Row supports keys(), plain dict)
    if hasattr(row, 'keys') and not isinstance(row, (tuple, list)):
        try:
            return {k: row[k] for k in row.keys()}
        except Exception:
            pass
    if isinstance(row, dict):
        return dict(row)
    # Sequence (tuple/list) → map by known column order
    return {columns[i]: row[i] for i in range(min(len(columns), len(row)))}


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

    # Canonical column order produced by UserRepository.find_by_id()
    _COLUMNS = ['user_id', 'username', 'first_name', 'last_name',
                'balance', 'is_blocked', 'language', 'join_date']

    @classmethod
    def from_row(cls, row) -> 'UserDTO':
        """Create from a psycopg2 tuple, dict, or sqlite3.Row."""
        if row is None:
            return None
        d = _row_to_mapping(row, cls._COLUMNS)
        return cls(
            user_id=d['user_id'],
            balance=d.get('balance', 0) or 0,
            username=d.get('username'),
            first_name=d.get('first_name'),
            last_name=d.get('last_name'),
            language=d.get('language', 'fa') or 'fa',
            is_blocked=bool(d.get('is_blocked', 0)),
            join_date=d.get('join_date'),
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

    # Canonical column order produced by OrderRepository.find_by_id()
    _COLUMNS = ['id', 'user_id', 'activation_id', 'service', 'country',
                'operator', 'phone', 'price', 'status', 'created_at']

    @classmethod
    def from_row(cls, row) -> 'OrderDTO':
        if row is None:
            return None
        d = _row_to_mapping(row, cls._COLUMNS)
        status_raw = d.get('status', 'CREATED') or 'CREATED'
        try:
            status = OrderStatus(str(status_raw).upper())
        except ValueError:
            status = OrderStatus.CREATED
        return cls(
            id=d.get('id'),
            user_id=d.get('user_id', 0) or 0,
            activation_id=d.get('activation_id'),
            service=d.get('service', '') or '',
            country=d.get('country', '') or '',
            operator=d.get('operator', '') or '',
            phone=d.get('phone', '') or '',
            price=d.get('price', 0) or 0,
            status=status,
            created_at=d.get('created_at'),
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
    new_balance: Optional[int] = None  # Balance after credit (avoids second DB read)


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
