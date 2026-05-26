"""
services/sms_service.py — SMS Provider Service
─────────────────────────────────────────────────
Provider-based architecture for virtual number services.
Zero Telegram dependencies — pure business logic.

Architecture:
    BaseSMSProvider (abstract)
    ├── HeroSMSProvider (hero-sms.com via SMS-Activate protocol)
    ├── SMSActivateProvider (future)
    └── FiveSimProvider (future)

Usage:
    from services.sms_service import SMSService
    sms = SMSService()
    result = sms.get_prices('telegram', 'cyprus')
"""

import logging
import time
import requests
from abc import ABC, abstractmethod
from typing import Optional
from config import HEROSMS_CONFIG, COUNTRY_ID_MAP, SERVICE_CODE_MAP
from data.dto import SMSProviderResponse, PriceInfoDTO, PurchaseResultDTO
from data.service_countries import SERVICE_COUNTRIES
from services.cache_service import CacheService, CacheKeys
from services.settings_service import SettingsService

logger = logging.getLogger(__name__)

# ── Retry Configuration ────────────────────────────────────────
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds
REQUEST_TIMEOUT = 15  # seconds


# ═══════════════════════════════════════════════════════════════
# BASE PROVIDER (Abstract)
# ═══════════════════════════════════════════════════════════════

class BaseSMSProvider(ABC):
    """Abstract base for all SMS/number providers."""

    provider_name: str = 'base'

    @abstractmethod
    def get_balance(self) -> SMSProviderResponse:
        """Get account balance from provider."""
        ...

    @abstractmethod
    def get_prices(self, service: str, country: str) -> SMSProviderResponse:
        """Get prices for a service+country combination."""
        ...

    @abstractmethod
    def get_numbers_status(self, country: str = 'any') -> SMSProviderResponse:
        """Get available numbers count per service."""
        ...

    @abstractmethod
    def buy_number(self, service: str, country: str,
                   operator: str = 'any') -> SMSProviderResponse:
        """Purchase a virtual number."""
        ...

    @abstractmethod
    def get_sms(self, activation_id: int) -> SMSProviderResponse:
        """Check for received SMS code."""
        ...

    @abstractmethod
    def cancel_number(self, activation_id: int) -> SMSProviderResponse:
        """Cancel an active number."""
        ...

    def _retry_request(self, url: str, params: dict,
                       timeout: int = REQUEST_TIMEOUT) -> SMSProviderResponse:
        """Execute an HTTP request with exponential backoff retry."""
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.get(url, params=params, timeout=timeout)
                return SMSProviderResponse(
                    success=True,
                    provider=self.provider_name,
                    raw_response=response.text,
                    data={'status_code': response.status_code, 'text': response.text}
                )
            except requests.exceptions.Timeout:
                last_error = f"Timeout after {timeout}s"
            except requests.exceptions.ConnectionError as e:
                last_error = f"Connection error: {e}"
            except Exception as e:
                last_error = str(e)

            if attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    f"{self.provider_name} retry {attempt + 1}/{MAX_RETRIES} "
                    f"after {delay:.1f}s: {last_error}"
                )
                time.sleep(delay)

        return SMSProviderResponse(
            success=False,
            provider=self.provider_name,
            error=f"Failed after {MAX_RETRIES} attempts: {last_error}"
        )


# ═══════════════════════════════════════════════════════════════
# HEROSMS PROVIDER (hero-sms.com via SMS-Activate Protocol)
# ═══════════════════════════════════════════════════════════════

class HeroSMSProvider(BaseSMSProvider):
    """
    HeroSMS provider using SMS-Activate compatible protocol.
    Endpoints: getBalance, getNumbersStatus, getPrices, getNumber,
               getStatus, setStatus
    """

    provider_name = 'herosms'

    def __init__(self):
        self.api_key = HEROSMS_CONFIG['api_key']
        self.api_url = HEROSMS_CONFIG['api_url']

    def _call(self, action: str, extra_params: dict = None) -> SMSProviderResponse:
        """Make an API call to HeroSMS."""
        params = {'api_key': self.api_key, 'action': action}
        if extra_params:
            params.update(extra_params)
        logger.info(f"HeroSMS API: {action} with params: {dict(params) if params else 'none'}")
        return self._retry_request(self.api_url, params)

    def get_balance(self) -> SMSProviderResponse:
        return self._call('getBalance')

    def get_prices(self, service: str, country: str) -> SMSProviderResponse:
        country_id = COUNTRY_ID_MAP.get(country, country)
        service_code = SERVICE_CODE_MAP.get(service, service)
        return self._call('getPrices', {
            'country': country_id,
            'service': service_code
        })

    def get_numbers_status(self, country: str = 'any') -> SMSProviderResponse:
        extra = {}
        if country != 'any':
            country_id = COUNTRY_ID_MAP.get(country, country)
            extra['country'] = country_id
        return self._call('getNumbersStatus', extra)

    def buy_number(self, service: str, country: str,
                   operator: str = 'any') -> SMSProviderResponse:
        country_id = COUNTRY_ID_MAP.get(country, country)
        service_code = SERVICE_CODE_MAP.get(service, service)
        params = {
            'service': service_code,
            'country': country_id,
        }
        if operator and operator != 'any':
            params['operator'] = operator
        return self._call('getNumber', params)

    def get_sms(self, activation_id: int) -> SMSProviderResponse:
        return self._call('getStatus', {'id': activation_id})

    def cancel_number(self, activation_id: int) -> SMSProviderResponse:
        """Cancel with status=8 (SMS-Activate cancel code)."""
        return self._call('setStatus', {'id': activation_id, 'status': '8'})


# ═══════════════════════════════════════════════════════════════
# SMS SERVICE (Orchestrator)
# ═══════════════════════════════════════════════════════════════

class SMSService:
    """
    High-level SMS service — uses providers underneath.
    Caches prices and availability.
    Handles price calculation with profit margin.
    """

    def __init__(self):
        self._provider: BaseSMSProvider = HeroSMSProvider()
        self._cache = CacheService.get_instance()
        self._settings = SettingsService()

    @property
    def provider(self) -> BaseSMSProvider:
        return self._provider

    def set_provider(self, provider: BaseSMSProvider) -> None:
        """Swap the SMS provider at runtime."""
        self._provider = provider
        self._cache.clear('prices:')
        self._cache.clear('countries:')
        logger.info(f"SMS provider changed to: {provider.provider_name}")

    def get_balance(self) -> float | None:
        """Get the provider account balance."""
        result = self._provider.get_balance()
        if result.success and result.raw_response:
            text = result.raw_response.strip()
            if 'ACCESS_BALANCE' in text:
                try:
                    return float(text.split(':')[1])
                except (IndexError, ValueError):
                    pass
        return None

    def get_price_info(self, service: str, country: str) -> PriceInfoDTO | None:
        """
        Get calculated price for a service+country.
        Includes profit margin from settings.
        Results cached for 30 seconds.
        """
        cache_key = CacheKeys.PRICES.format(service, country)

        def _fetch():
            return self._calculate_price(service, country)

        return self._cache.get_or_set(cache_key, _fetch, CacheKeys.TTL_PRICES)

    def _calculate_price(self, service: str, country: str) -> PriceInfoDTO | None:
        """Calculate final price with USD rate and profit margin."""
        result = self._provider.get_prices(service, country)

        if not result.success:
            return None

        try:
            data = result.data
            resp_text = data.get('text', '')
            import json
            price_data = json.loads(resp_text)

            country_id = COUNTRY_ID_MAP.get(country, country)
            service_code = SERVICE_CODE_MAP.get(service, service)

            if country_id not in price_data or service_code not in price_data[country_id]:
                return None

            operators = price_data[country_id][service_code]

            # Find cheapest available operator
            min_price = float('inf')
            best_op = ''
            available = 0

            for op_name, op_data in operators.items():
                if op_data.get('count', 0) > 0 and op_data.get('cost', float('inf')) < min_price:
                    min_price = op_data['cost']
                    best_op = op_name
                    available = op_data.get('count', 0)

            if min_price == float('inf'):
                return None

            usd_rate = self._settings.get_float('usd_rate', 0)
            profit_pct = self._settings.get_float('profit_percentage', 30)
            price_toman = round(min_price * usd_rate * (1 + profit_pct / 100))

            return PriceInfoDTO(
                service=service,
                country=country,
                country_name='',
                operator=best_op,
                price_usd=min_price,
                price_toman=price_toman,
                available_count=available,
            )
        except Exception as e:
            logger.error(f"Error calculating price for {service}/{country}: {e}")
            return None

    def buy_number(self, service: str, country: str,
                   operator: str = 'any') -> SMSProviderResponse:
        """
        Purchase a virtual number from the provider.
        Parses ACCESS_NUMBER:ID:PHONE response.
        """
        result = self._provider.buy_number(service, country, operator)
        if result.success and result.raw_response:
            text = result.raw_response.strip()
            if text.startswith('ACCESS_NUMBER:'):
                parts = text.split(':')
                result.data = {
                    'activation_id': int(parts[1]),
                    'phone': parts[2],
                }
                return result
            else:
                result.success = False
                result.error = text
        return result

    def check_sms(self, activation_id: int) -> SMSProviderResponse:
        """
        Check for received SMS code.
        Parses STATUS_OK:CODE response.
        """
        result = self._provider.get_sms(activation_id)
        if result.success and result.raw_response:
            text = result.raw_response.strip()
            if text.startswith('STATUS_OK:'):
                parts = text.split(':')
                result.data = {
                    'code': parts[1] if len(parts) > 1 else '',
                    'status': 'RECEIVED',
                }
            elif text == 'STATUS_WAIT_CODE' or text == 'STATUS_WAIT_RETRY':
                result.data = {'status': 'WAITING'}
            elif text == 'STATUS_CANCEL':
                result.data = {'status': 'CANCELLED'}
            else:
                result.data = {'status': text}
        return result

    def cancel_number(self, activation_id: int) -> SMSProviderResponse:
        """Cancel a number via the provider."""
        result = self._provider.cancel_number(activation_id)
        if result.success and result.raw_response:
            if 'ACCESS_CANCEL' in result.raw_response:
                result.data = {'cancelled': True}
            else:
                result.success = False
                result.error = result.raw_response.strip()
        return result
