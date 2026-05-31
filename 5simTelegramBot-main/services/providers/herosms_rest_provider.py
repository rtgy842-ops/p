"""
services/providers/herosms_rest_provider.py — HeroSMS REST API Provider Plugin
─────────────────────────────────────────────────
Official HeroSMS REST API integration.
Endpoints: /api/getCountries, /api/getServices, /api/getPrices,
           /api/getNumber, /api/getStatus, /api/setStatus

This is an ALTERNATIVE provider implementation using the REST API.
It coexists with the SMS-Activate protocol implementation in sms_service.py.
"""
import logging
import requests
from typing import Optional

from config import HEROSMS_CONFIG

logger = logging.getLogger(__name__)

# ── Custom exception for HeroSMS API errors ────────────────────
class HeroSMSAPIError(Exception):
    """Raised when HeroSMS API returns an error."""
    pass


class HeroSMSRESTProvider:
    """
    HeroSMS provider using the official REST API (JSON).

    Base URL: https://hero-sms.com/api
    All endpoints accept ?api_key= as query parameter.

    Endpoints:
        GET /api/getCountries       → list of available countries
        GET /api/getServices        → list of available services
        GET /api/getPrices          → prices (optional ?country=&service=)
        GET /api/getNumber          → buy a number (?service=&country=)
        GET /api/getStatus          → check SMS status (?id=activation_id)
        GET /api/setStatus          → cancel/complete (?id=&status=)
    """

    BASE_URL = "https://hero-sms.com/api"
    TIMEOUT = 30  # seconds

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or HEROSMS_CONFIG.get('api_key', '')
        if not self.api_key:
            logger.warning("HeroSMSRESTProvider initialized without API key")

    # ── Low-level HTTP helper ──────────────────────────────────

    def _get(self, endpoint: str, params: dict | None = None) -> dict:
        """
        Execute a GET request against the HeroSMS REST API.

        Args:
            endpoint: API endpoint path (e.g., 'getCountries')
            params: Additional query parameters

        Returns:
            Parsed JSON response dictionary

        Raises:
            HeroSMSAPIError: On non-200 response or API-level error
            requests.RequestException: On network errors
        """
        url = f"{self.BASE_URL}/{endpoint}"
        _params = {"api_key": self.api_key}
        if params:
            _params.update(params)

        logger.debug(f"HeroSMS REST: GET {url} with {_params}")
        response = requests.get(url, params=_params, timeout=self.TIMEOUT)
        response.raise_for_status()

        data = response.json()

        # Check for API-level errors
        if isinstance(data, dict) and data.get("error"):
            error_msg = data.get("error", "Unknown API error")
            logger.error(f"HeroSMS API error on {endpoint}: {error_msg}")
            raise HeroSMSAPIError(error_msg)

        return data

    # ── Public API methods ─────────────────────────────────────

    def get_countries(self) -> dict:
        """
        Get list of all available countries.

        Returns:
            {
                "0": {"name": "Russia", "code": "ru", ...},
                "4": {"name": "Philippines", "code": "ph", ...},
                ...
            }
        """
        return self._get("getCountries")

    def get_services(self) -> dict:
        """
        Get list of all available services.

        Returns:
            {
                "tg": {"name": "Telegram", ...},
                "wa": {"name": "WhatsApp", ...},
                ...
            }
        """
        return self._get("getServices")

    def get_prices(self, country: str | None = None,
                   service: str | None = None) -> dict:
        """
        Get prices for all or filtered country/service combinations.

        Args:
            country: Optional country code filter
            service: Optional service code filter

        Returns:
            {
                "0": {"tg": {"cost": 10.5, "count": 150}, ...},
                ...
            }
        """
        params = {}
        if country:
            params["country"] = country
        if service:
            params["service"] = service
        return self._get("getPrices", params=params if params else None)

    def buy_number(self, service: str, country: str) -> dict:
        """
        Purchase a virtual number.

        Args:
            service: Service code (e.g., 'tg', 'wa')
            country: Country code (e.g., '0' for Russia)

        Returns:
            {
                "activation_id": 123456,
                "phone": "79123456789",
                "status": "PENDING"
            }
        """
        params = {"service": service, "country": country}
        return self._get("getNumber", params=params)

    def check_sms(self, activation_id: int) -> dict:
        """
        Check for received SMS code.

        Args:
            activation_id: Order/activation ID from buy_number

        Returns:
            {
                "status": "RECEIVED",  # or "WAITING", "CANCELED"
                "code": "12345"         # present only when status=RECEIVED
            }
        """
        params = {"id": activation_id}
        return self._get("getStatus", params=params)

    def cancel_order(self, activation_id: int) -> dict:
        """
        Cancel an active number order.

        Args:
            activation_id: Order/activation ID from buy_number

        Returns:
            {"status": "CANCELED"}
        """
        params = {"id": activation_id, "status": "CANCEL"}
        return self._get("setStatus", params=params)

    def set_status(self, activation_id: int, status: str) -> dict:
        """
        Set custom status on an order.

        Args:
            activation_id: Order/activation ID
            status: Status code (e.g., 'CANCEL', 'COMPLETE')

        Returns:
            API response dict
        """
        params = {"id": activation_id, "status": status}
        return self._get("setStatus", params=params)

    # ── Health check ───────────────────────────────────────────

    def health_check(self) -> dict:
        """
        Verify API key is valid by calling getCountries.

        Returns:
            {"healthy": True/False, "error": "..."}
        """
        try:
            self.get_countries()
            return {"healthy": True, "error": None}
        except Exception as e:
            return {"healthy": False, "error": str(e)}
