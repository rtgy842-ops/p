"""
services/smart_router.py — Smart Routing Engine
─────────────────────────────────────────────────
Compares ALL active providers and selects the best one using:
- Price-based routing (cheapest first)
- Availability-based routing (most available first)
- Priority-weighted routing (admin-defined priority)
- Admin-defined policy selection

Usage:
    from services.smart_router import SmartRouter
    router = SmartRouter()
    result = router.find_best(service='telegram', country='cyprus', strategy='best_price')
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from services.provider_registry import provider_registry
from services.settings_service import SettingsService
from services.sms_service import BaseSMSProvider, HeroSMSProvider

logger = logging.getLogger(__name__)


class RoutingStrategy(str, Enum):
    BEST_PRICE = 'best_price'           # Cheapest price among all providers
    HIGHEST_AVAILABILITY = 'highest_availability'  # Most available numbers
    PRIORITY_WEIGHTED = 'priority_weighted'       # Admin-defined priority
    FIRST_AVAILABLE = 'first_available'           # First provider with stock


@dataclass
class ProviderQuote:
    """Price quote from a single provider."""
    provider_name: str
    provider: BaseSMSProvider
    price_usd: float
    price_toman: int
    available_count: int
    operator: str
    country: str
    service: str
    error: Optional[str] = None
    is_available: bool = field(default=False)

    def __post_init__(self):
        self.is_available = self.available_count > 0 and self.error is None


@dataclass
class RoutingResult:
    """Result from the smart routing engine."""
    success: bool
    best_quote: Optional[ProviderQuote] = None
    all_quotes: list[ProviderQuote] = field(default_factory=list)
    strategy_used: str = ''
    error_message: Optional[str] = None


class SmartRouter:
    """
    Multi-provider comparison engine.
    Queries all active providers and selects the best match
    based on the configured routing strategy.
    """

    def __init__(self):
        self._settings = SettingsService()
        self._default_strategy = RoutingStrategy.BEST_PRICE

    def get_strategy(self) -> RoutingStrategy:
        """Get the current routing strategy from settings."""
        strategy_str = self._settings.get('routing_strategy', self._default_strategy.value)
        try:
            return RoutingStrategy(strategy_str)
        except ValueError:
            return self._default_strategy

    def set_strategy(self, strategy: RoutingStrategy) -> bool:
        """Update the routing strategy in settings."""
        return self._settings.set('routing_strategy', strategy.value)

    def find_best(self, service: str, country: str,
                  operator: str = 'any',
                  strategy: RoutingStrategy | None = None) -> RoutingResult:
        """
        Query ALL active providers and find the best match.

        Args:
            service: Service code (telegram, whatsapp, etc.)
            country: Country code (cyprus, poland, etc.)
            operator: Specific operator or 'any'
            strategy: Override default routing strategy

        Returns:
            RoutingResult with best quote and all quotes for comparison
        """
        if strategy is None:
            strategy = self.get_strategy()

        providers = provider_registry.active_providers

        # Fallback: if no providers registered, use the default HeroSMS
        if not providers:
            hero = HeroSMSProvider()
            providers = [hero]

        all_quotes: list[ProviderQuote] = []

        for provider in providers:
            quote = self._get_quote(provider, service, country, operator)
            all_quotes.append(quote)

        if not all_quotes:
            return RoutingResult(
                success=False,
                all_quotes=[],
                strategy_used=strategy.value,
                error_message="No providers available"
            )

        # Filter to available only
        available = [q for q in all_quotes if q.is_available]

        if not available:
            # Return cheapest even if unavailable (for error display)
            available_fallback = sorted(all_quotes, key=lambda q: q.price_toman)
            return RoutingResult(
                success=False,
                best_quote=available_fallback[0] if available_fallback else None,
                all_quotes=all_quotes,
                strategy_used=strategy.value,
                error_message="No provider has available numbers"
            )

        # Select best based on strategy
        best = self._select_best(available, strategy)

        logger.info(
            f"SmartRouter: service={service}, country={country}, "
            f"strategy={strategy.value}, selected={best.provider_name}, "
            f"price={best.price_toman}T, available={best.available_count}"
        )

        return RoutingResult(
            success=True,
            best_quote=best,
            all_quotes=all_quotes,
            strategy_used=strategy.value,
        )

    def _get_quote(self, provider: BaseSMSProvider, service: str,
                   country: str, operator: str) -> ProviderQuote:
        """Get price and availability from a single provider."""
        try:
            from config import COUNTRY_ID_MAP, SERVICE_CODE_MAP

            # Get prices
            price_result = provider.get_prices(service, country)
            if not price_result.success:
                return ProviderQuote(
                    provider_name=provider.provider_name,
                    provider=provider, price_usd=0, price_toman=999999,
                    available_count=0, operator=operator,
                    country=country, service=service,
                    error=price_result.error or 'Price fetch failed'
                )

            # Parse price data
            import json
            resp_text = price_result.raw_response or ''
            price_data = json.loads(resp_text)

            country_id = COUNTRY_ID_MAP.get(country, country)
            service_code = SERVICE_CODE_MAP.get(service, service)

            if country_id not in price_data or service_code not in price_data.get(country_id, {}):
                return ProviderQuote(
                    provider_name=provider.provider_name,
                    provider=provider, price_usd=0, price_toman=999999,
                    available_count=0, operator=operator,
                    country=country, service=service,
                    error='Country/service not available'
                )

            operators = price_data[country_id][service_code]

            # Find best operator
            min_price = float('inf')
            best_op = ''
            available = 0

            for op_name, op_data in operators.items():
                count = op_data.get('count', 0)
                cost = op_data.get('cost', float('inf'))
                if operator != 'any' and op_name != operator:
                    continue
                if count > 0 and cost < min_price:
                    min_price = cost
                    best_op = op_name
                    available = count

            if min_price == float('inf'):
                return ProviderQuote(
                    provider_name=provider.provider_name,
                    provider=provider, price_usd=0, price_toman=999999,
                    available_count=0, operator=operator,
                    country=country, service=service,
                    error='No operators available'
                )

            # Calculate final price with profit margin
            usd_rate = self._settings.get_float('usd_rate', 0)
            profit_pct = self._settings.get_float('profit_percentage', 30)
            price_toman = round(min_price * usd_rate * (1 + profit_pct / 100))

            return ProviderQuote(
                provider_name=provider.provider_name,
                provider=provider,
                price_usd=min_price,
                price_toman=price_toman,
                available_count=available,
                operator=best_op,
                country=country,
                service=service,
            )

        except Exception as e:
            logger.error(f"Error getting quote from {provider.provider_name}: {e}")
            return ProviderQuote(
                provider_name=provider.provider_name,
                provider=provider, price_usd=0, price_toman=999999,
                available_count=0, operator=operator,
                country=country, service=service,
                error=str(e)
            )

    def _select_best(self, quotes: list[ProviderQuote],
                     strategy: RoutingStrategy) -> ProviderQuote:
        """Select the best quote based on strategy."""
        if strategy == RoutingStrategy.BEST_PRICE:
            return min(quotes, key=lambda q: q.price_toman)
        elif strategy == RoutingStrategy.HIGHEST_AVAILABILITY:
            return max(quotes, key=lambda q: q.available_count)
        elif strategy == RoutingStrategy.PRIORITY_WEIGHTED:
            # Combine price and availability with provider priority
            for q in quotes:
                info = provider_registry.get_info(q.provider_name)
                priority = info.priority if info else 0
                # Weighted score: lower price + higher availability + higher priority
                q._score = q.price_toman - (q.available_count * 10) - (priority * 1000)
            return min(quotes, key=lambda q: getattr(q, '_score', q.price_toman))
        else:  # FIRST_AVAILABLE
            return quotes[0]

    def compare_all(self, service: str, country: str,
                    operator: str = 'any') -> RoutingResult:
        """Get comparison of all providers (for admin display)."""
        return self.find_best(service, country, operator, strategy=RoutingStrategy.BEST_PRICE)


# ── Global instance ────────────────────────────────────────────
smart_router = SmartRouter()
