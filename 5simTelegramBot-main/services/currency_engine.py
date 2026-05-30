"""
services/currency_engine.py — Enterprise Multi-Currency Engine
─────────────────────────────────────────────────
Base currency: USD (stored in all DB records).
Admin can add any currency and define its rate vs 1 USD.
All customer-facing amounts are auto-converted to the user's preferred currency.

Features:
- Add/remove/edit currencies
- Set exchange rate vs USD
- Auto-convert for display
- Historical rate tracking
- Currency-aware wallet display
"""

import logging
from datetime import datetime
from typing import Optional

from db.context import db_context

logger = logging.getLogger(__name__)


class CurrencyEngine:
    """
    Multi-currency conversion engine.
    All internal amounts are in USD; conversion happens at display time.
    """

    BASE_CURRENCY = 'USD'

    def __init__(self):
        self._rate_cache: dict[str, float] = {}
        self._cache_time: float = 0

    # ═══════════════════════════════════════════════════════════
    # ADMIN: Currency Management
    # ═══════════════════════════════════════════════════════════

    def add_currency(self, code: str, name: str, symbol: str = '',
                     rate_to_usd: float = 1.0, is_default: bool = False) -> bool:
        """Add a new currency to the system."""
        try:
            with db_context('default', transactional=True) as db:
                if is_default:
                    db.execute("UPDATE currencies SET is_default = 0 WHERE is_default = 1")
                db.execute(
                    """INSERT INTO currencies (code, name, symbol, rate_to_usd, is_active, is_default)
                       VALUES (%s, %s, %s, %s, 1, %s)
                       ON CONFLICT (code) DO UPDATE SET
                       name = %s, symbol = %s, rate_to_usd = %s, is_default = %s, updated_at = CURRENT_TIMESTAMP""",
                    (code.upper(), name, symbol, rate_to_usd, 1 if is_default else 0,
                     name, symbol, rate_to_usd, 1 if is_default else 0)
                )
            self._invalidate_cache()
            logger.info(f"Currency added/updated: {code} = {rate_to_usd} per USD")
            return True
        except Exception as e:
            logger.error(f"Failed to add currency: {e}")
            return False

    def remove_currency(self, code: str) -> bool:
        """Deactivate a currency (never delete — data integrity)."""
        try:
            with db_context('default', transactional=True) as db:
                db.execute(
                    "UPDATE currencies SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE code = %s",
                    (code.upper(),)
                )
            return True
        except Exception:
            return False

    def set_rate(self, code: str, rate_to_usd: float) -> bool:
        """Update exchange rate for a currency."""
        try:
            with db_context('default', transactional=True) as db:
                db.execute(
                    "UPDATE currencies SET rate_to_usd = %s, updated_at = CURRENT_TIMESTAMP WHERE code = %s",
                    (rate_to_usd, code.upper())
                )
            self._invalidate_cache()
            logger.info(f"Rate updated: 1 USD = {rate_to_usd} {code}")
            return True
        except Exception as e:
            logger.error(f"Failed to set rate: {e}")
            return False

    # ═══════════════════════════════════════════════════════════
    # ACTIVE CURRENCIES
    # ═══════════════════════════════════════════════════════════

    def get_active_currencies(self) -> list[dict]:
        """Get all active currencies for display/selection."""
        try:
            with db_context('default', transactional=False) as db:
                rows = db.fetchall(
                    "SELECT code, name, symbol, rate_to_usd, is_default FROM currencies WHERE is_active = 1 ORDER BY code"
                )
                return [
                    {'code': r[0] if not isinstance(r, dict) else r.get('code'),
                     'name': r[1] if not isinstance(r, dict) else r.get('name'),
                     'symbol': r[2] if not isinstance(r, dict) else r.get('symbol'),
                     'rate': float(r[3]) if not isinstance(r, dict) else float(r.get('rate_to_usd', 0)),
                     'is_default': bool(r[4]) if not isinstance(r, dict) else bool(r.get('is_default'))}
                    for r in rows
                ]
        except Exception:
            return [{'code': 'USD', 'name': 'US Dollar', 'symbol': '$', 'rate': 1.0, 'is_default': True}]

    def get_all_currencies(self) -> list[dict]:
        """Get all currencies including inactive (for admin panel)."""
        try:
            with db_context('default', transactional=False) as db:
                rows = db.fetchall(
                    "SELECT id, code, name, symbol, rate_to_usd, is_active, is_default, created_at FROM currencies ORDER BY code"
                )
                return [
                    {'id': r[0], 'code': r[1], 'name': r[2], 'symbol': r[3],
                     'rate_to_usd': float(r[4]), 'is_active': bool(r[5]),
                     'is_default': bool(r[6]), 'created_at': str(r[7])}
                    for r in rows
                ]
        except Exception:
            return []

    def get_default_currency(self) -> str:
        """Get the default currency code."""
        try:
            with db_context('default', transactional=False) as db:
                row = db.fetchone(
                    "SELECT code FROM currencies WHERE is_default = 1 AND is_active = 1 LIMIT 1"
                )
                if row:
                    return row[0] if not isinstance(row, dict) else row.get('code', 'USD')
        except Exception:
            pass
        return 'USD'

    # ═══════════════════════════════════════════════════════════
    # CONVERSION
    # ═══════════════════════════════════════════════════════════

    def convert_from_usd(self, amount_usd: float, to_currency: str) -> float:
        """Convert USD amount to target currency."""
        if to_currency.upper() == 'USD':
            return amount_usd

        rate = self._get_rate(to_currency)
        if rate <= 0:
            return amount_usd

        return round(amount_usd * rate, 2)

    def convert_to_usd(self, amount: float, from_currency: str) -> float:
        """Convert from any currency to USD."""
        if from_currency.upper() == 'USD':
            return amount

        rate = self._get_rate(from_currency)
        if rate <= 0:
            return amount

        return round(amount / rate, 6)

    def format_amount(self, amount_usd: float, currency_code: str = 'USD') -> str:
        """Format an amount for display in the given currency."""
        converted = self.convert_from_usd(amount_usd, currency_code)
        currencies = {c['code']: c for c in self.get_active_currencies()}
        currency = currencies.get(currency_code.upper(), {})
        symbol = currency.get('symbol', '$')

        if converted >= 1000:
            return f"{symbol}{converted:,.0f}"
        return f"{symbol}{converted:.2f}"

    def _get_rate(self, code: str) -> float:
        """Get exchange rate with caching."""
        import time
        code = code.upper()

        # Cache for 5 minutes
        if time.time() - self._cache_time < 300 and code in self._rate_cache:
            return self._rate_cache[code]

        try:
            with db_context('default', transactional=False) as db:
                row = db.fetchone(
                    "SELECT rate_to_usd FROM currencies WHERE code = %s AND is_active = 1",
                    (code,)
                )
                if row:
                    rate = float(row[0] if not isinstance(row, dict) else row.get('rate_to_usd', 0))
                    self._rate_cache[code] = rate
                    self._cache_time = time.time()
                    return rate
        except Exception:
            pass

        return 0.0

    def _invalidate_cache(self) -> None:
        """Clear the rate cache."""
        self._rate_cache.clear()
        self._cache_time = 0


# ── Global instance ────────────────────────────────────────────
currency_engine = CurrencyEngine()
