"""
services/provider_sync.py — Provider Auto-Sync Service
─────────────────────────────────────────────────
Periodically syncs countries, services, prices, and stock
from ALL active providers into the database.

Sync types:
- Full sync: Countries + Services + Prices (on demand)
- Price sync: Prices + Stock only (every 30s)
- Health check: Balance check (every 60s)

Usage:
    from services.provider_sync import ProviderSyncService
    syncer = ProviderSyncService()
    syncer.sync_all()
"""

import logging
import json
import time
from datetime import datetime
from typing import Optional

from services.sms_service import BaseSMSProvider, HeroSMSProvider
from services.provider_registry import provider_registry
from db.context import db_context

logger = logging.getLogger(__name__)


class ProviderSyncService:
    """
    Synchronizes provider data (countries, services, prices, stock)
    into the database for catalog management and smart routing.
    """

    def __init__(self):
        self._last_sync: dict[str, float] = {}
        self._sync_interval = 30  # seconds between price syncs

    def sync_all(self) -> dict[str, dict]:
        """
        Full synchronization for all active providers.
        Returns sync results per provider.
        """
        results = {}
        for provider in provider_registry.active_providers:
            name = provider.provider_name
            try:
                results[name] = self.sync_provider(provider)
                provider_registry.update_health(name, 'healthy')
            except Exception as e:
                logger.error(f"Sync failed for {name}: {e}")
                results[name] = {'success': False, 'error': str(e)}
                provider_registry.update_health(name, 'error', str(e))
        return results

    def sync_provider(self, provider: BaseSMSProvider) -> dict:
        """Sync a single provider's data into DB."""
        name = provider.provider_name
        provider_id = self._get_or_create_provider_id(name)
        if not provider_id:
            return {'success': False, 'error': 'Provider not found in DB'}

        result = {'success': True, 'countries': 0, 'services': 0, 'prices': 0}

        # 1. Sync countries (getNumbersStatus for 'any')
        try:
            countries_result = provider.get_numbers_status('any')
            if countries_result.success and countries_result.raw_response:
                data = json.loads(countries_result.raw_response)
                for country_code, services_data in data.items():
                    if not country_code.isdigit():
                        continue
                    total_available = sum(
                        s.get('count', 0) for s in services_data.values()
                        if isinstance(s, dict)
                    )
                    self._upsert_country(provider_id, country_code, total_available)
                    result['countries'] += 1
        except Exception as e:
            logger.warning(f"Country sync failed for {name}: {e}")

        # 2. Sync services
        services_seen = set()
        if countries_result and countries_result.success and countries_result.raw_response:
            try:
                data = json.loads(countries_result.raw_response)
                for country_code, services_data in data.items():
                    if not country_code.isdigit():
                        continue
                    for svc_code, svc_info in services_data.items():
                        if not isinstance(svc_info, dict):
                            continue
                        if svc_code not in services_seen:
                            self._upsert_service(provider_id, svc_code, svc_code)
                            services_seen.add(svc_code)
                            result['services'] += 1
            except Exception:
                pass

        # 3. Sync prices (per country+service from catalog)
        try:
            from data.service_countries import get_all_service_countries
            catalog_entries = get_all_service_countries()
            for svc, country, _, operator in catalog_entries:
                try:
                    price_result = provider.get_prices(svc, country)
                    if price_result.success and price_result.raw_response:
                        price_data = json.loads(price_result.raw_response)
                        from config import COUNTRY_ID_MAP, SERVICE_CODE_MAP
                        country_id = COUNTRY_ID_MAP.get(country, country)
                        svc_code = SERVICE_CODE_MAP.get(svc, svc)

                        if country_id in price_data and svc_code in price_data[country_id]:
                            operators = price_data[country_id][svc_code]
                            for op_name, op_data in operators.items():
                                cost = op_data.get('cost', 0)
                                count = op_data.get('count', 0)
                                self._upsert_price(provider_id, country, svc, op_name, cost, count)
                                result['prices'] += 1
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Price sync issue for {name}: {e}")

        # Update last sync timestamp
        self._last_sync[name] = time.time()
        try:
            with db_context('default', transactional=True) as db:
                db.execute(
                    "UPDATE providers SET last_sync_at = CURRENT_TIMESTAMP WHERE name = %s",
                    (name,)
                )
        except Exception:
            pass

        logger.info(f"Sync complete: {name} — {result['countries']} countries, "
                     f"{result['services']} services, {result['prices']} prices")
        return result

    def sync_prices_only(self, provider: BaseSMSProvider) -> dict:
        """Lightweight sync — prices and stock only."""
        name = provider.provider_name
        provider_id = self._get_or_create_provider_id(name)
        if not provider_id:
            return {'success': False, 'error': 'Provider not found'}

        result = {'success': True, 'prices': 0}
        try:
            from data.service_countries import get_all_service_countries
            for svc, country, _, operator in get_all_service_countries():
                price_result = provider.get_prices(svc, country)
                if price_result.success and price_result.raw_response:
                    price_data = json.loads(price_result.raw_response)
                    from config import COUNTRY_ID_MAP, SERVICE_CODE_MAP
                    country_id = COUNTRY_ID_MAP.get(country, country)
                    svc_code = SERVICE_CODE_MAP.get(svc, svc)
                    if country_id in price_data and svc_code in price_data[country_id]:
                        for op_name, op_data in price_data[country_id][svc_code].items():
                            self._upsert_price(
                                provider_id, country, svc, op_name,
                                op_data.get('cost', 0), op_data.get('count', 0)
                            )
                            result['prices'] += 1
        except Exception as e:
            logger.error(f"Price sync failed for {name}: {e}")
            result['success'] = False
            result['error'] = str(e)

        self._last_sync['prices:' + name] = time.time()
        return result

    def should_sync(self, name: str, sync_type: str = 'prices') -> bool:
        """Check if enough time has passed since last sync."""
        key = f'{sync_type}:{name}' if sync_type != 'full' else name
        elapsed = time.time() - self._last_sync.get(key, 0)
        return elapsed > self._sync_interval

    # ── DB Helpers ─────────────────────────────────────────

    def _get_or_create_provider_id(self, name: str) -> Optional[int]:
        """Get the provider ID from the providers table."""
        try:
            with db_context('default', transactional=False) as db:
                row = db.fetchone(
                    "SELECT id FROM providers WHERE name = %s", (name,)
                )
                if row:
                    return row['id'] if isinstance(row, dict) else row[0]
            return None
        except Exception as e:
            logger.error(f"Failed to get provider ID: {e}")
            return None

    def _upsert_country(self, provider_id: int, country_code: str,
                        available_count: int) -> None:
        """Insert or update country availability."""
        try:
            with db_context('default', transactional=True) as db:
                db.execute(
                    """INSERT INTO provider_countries (provider_id, country_code, country_name, available_count, last_sync_at)
                       VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                       ON CONFLICT (provider_id, country_code) DO UPDATE SET
                       available_count = %s, last_sync_at = CURRENT_TIMESTAMP""",
                    (provider_id, country_code, country_code, available_count, available_count)
                )
        except Exception as e:
            logger.debug(f"Country upsert error ({country_code}): {e}")

    def _upsert_service(self, provider_id: int, service_code: str,
                        service_name: str) -> None:
        """Insert or update service availability."""
        try:
            with db_context('default', transactional=True) as db:
                db.execute(
                    """INSERT INTO provider_services (provider_id, service_code, service_name, last_sync_at)
                       VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                       ON CONFLICT (provider_id, service_code) DO UPDATE SET
                       last_sync_at = CURRENT_TIMESTAMP""",
                    (provider_id, service_code, service_name)
                )
        except Exception as e:
            logger.debug(f"Service upsert error ({service_code}): {e}")

    def _upsert_price(self, provider_id: int, country_code: str,
                      service_code: str, operator_name: str,
                      price_usd: float, available_count: int) -> None:
        """Insert or update price data."""
        try:
            with db_context('default', transactional=True) as db:
                db.execute(
                    """INSERT INTO provider_prices
                       (provider_id, country_code, service_code, operator_name, price_usd, available_count, last_sync_at)
                       VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                       ON CONFLICT (provider_id, country_code, service_code, operator_name) DO UPDATE SET
                       price_usd = %s, available_count = %s, last_sync_at = CURRENT_TIMESTAMP""",
                    (provider_id, country_code, service_code, operator_name, price_usd, available_count,
                     price_usd, available_count)
                )
        except Exception as e:
            logger.debug(f"Price upsert error: {e}")

    # ── Stats ──────────────────────────────────────────────

    def get_sync_status(self) -> dict:
        """Get synchronization status for all providers."""
        status = {}
        for provider in provider_registry.active_providers:
            name = provider.provider_name
            last = self._last_sync.get(name, 0)
            status[name] = {
                'last_sync': datetime.fromtimestamp(last).isoformat() if last else 'never',
                'seconds_ago': time.time() - last if last else None,
                'needs_sync': self.should_sync(name, 'full'),
            }
        return status


# ── Global instance ────────────────────────────────────────────
provider_sync = ProviderSyncService()