"""
services/catalog_manager.py — Admin-Curated Catalog Management
─────────────────────────────────────────────────
Implements the "Catalog" layer between raw provider data and customer display.
Admins control:
- Which countries are visible to customers
- Which services are visible to customers
- Which providers are allowed
- Display ordering
- Pricing rules (profit %, fixed, min, max)

No raw provider data reaches customers directly.
"""

import logging
from typing import Optional

from db.context import db_context
from services.settings_service import SettingsService

logger = logging.getLogger(__name__)


class CatalogManager:
    """
    Admin-curated catalog — the middle layer between providers and customers.
    Only items explicitly enabled by admin are visible.
    """

    def __init__(self):
        self._settings = SettingsService()

    # ═══════════════════════════════════════════════════════════
    # COUNTRIES
    # ═══════════════════════════════════════════════════════════

    def get_active_countries(self) -> list[dict]:
        """Get all countries visible to customers (admin-enabled)."""
        try:
            with db_context('default', transactional=False) as db:
                rows = db.fetchall(
                    "SELECT country_code, country_name, display_order FROM catalog_countries "
                    "WHERE is_active = 1 ORDER BY display_order ASC"
                )
                return [
                    {'code': r[0] if not isinstance(r, dict) else r.get('country_code'),
                     'name': r[1] if not isinstance(r, dict) else r.get('country_name'),
                     'order': r[2] if not isinstance(r, dict) else r.get('display_order')}
                    for r in rows
                ]
        except Exception as e:
            logger.error(f"Failed to get active countries: {e}")
            return []

    def get_all_countries(self) -> list[dict]:
        """Get all countries (including inactive) for admin panel."""
        try:
            with db_context('default', transactional=False) as db:
                rows = db.fetchall(
                    "SELECT id, country_code, country_name, is_active, display_order "
                    "FROM catalog_countries ORDER BY display_order ASC"
                )
                return [
                    {'id': r[0] if not isinstance(r, dict) else r.get('id'),
                     'code': r[1] if not isinstance(r, dict) else r.get('country_code'),
                     'name': r[2] if not isinstance(r, dict) else r.get('country_name'),
                     'active': bool(r[3]) if not isinstance(r, dict) else bool(r.get('is_active')),
                     'order': r[4] if not isinstance(r, dict) else r.get('display_order')}
                    for r in rows
                ]
        except Exception:
            return []

    def toggle_country(self, country_code: str, active: bool) -> bool:
        """Enable or disable a country for customer visibility."""
        try:
            with db_context('default', transactional=True) as db:
                db.execute(
                    "UPDATE catalog_countries SET is_active = %s, updated_at = CURRENT_TIMESTAMP WHERE country_code = %s",
                    (1 if active else 0, country_code)
                )
            return True
        except Exception as e:
            logger.error(f"Failed to toggle country: {e}")
            return False

    def set_country_order(self, country_code: str, order: int) -> bool:
        """Change display order for a country."""
        try:
            with db_context('default', transactional=True) as db:
                db.execute(
                    "UPDATE catalog_countries SET display_order = %s, updated_at = CURRENT_TIMESTAMP WHERE country_code = %s",
                    (order, country_code)
                )
            return True
        except Exception:
            return False

    # ═══════════════════════════════════════════════════════════
    # SERVICES
    # ═══════════════════════════════════════════════════════════

    def get_active_services(self) -> list[dict]:
        """Get all services visible to customers."""
        try:
            with db_context('default', transactional=False) as db:
                rows = db.fetchall(
                    "SELECT service_code, service_name, category, display_order FROM catalog_services "
                    "WHERE is_active = 1 ORDER BY display_order ASC"
                )
                return [
                    {'code': r[0] if not isinstance(r, dict) else r.get('service_code'),
                     'name': r[1] if not isinstance(r, dict) else r.get('service_name'),
                     'category': r[2] if not isinstance(r, dict) else r.get('category'),
                     'order': r[3] if not isinstance(r, dict) else r.get('display_order')}
                    for r in rows
                ]
        except Exception as e:
            logger.error(f"Failed to get active services: {e}")
            return []

    def get_all_services(self) -> list[dict]:
        """Get all services for admin panel."""
        try:
            with db_context('default', transactional=False) as db:
                rows = db.fetchall(
                    "SELECT id, service_code, service_name, category, is_active, display_order "
                    "FROM catalog_services ORDER BY display_order ASC"
                )
                return [
                    {'id': r[0] if not isinstance(r, dict) else r.get('id'),
                     'code': r[1] if not isinstance(r, dict) else r.get('service_code'),
                     'name': r[2] if not isinstance(r, dict) else r.get('service_name'),
                     'category': r[3] if not isinstance(r, dict) else r.get('category'),
                     'active': bool(r[4]) if not isinstance(r, dict) else bool(r.get('is_active')),
                     'order': r[5] if not isinstance(r, dict) else r.get('display_order')}
                    for r in rows
                ]
        except Exception:
            return []

    def toggle_service(self, service_code: str, active: bool) -> bool:
        """Enable or disable a service."""
        try:
            with db_context('default', transactional=True) as db:
                db.execute(
                    "UPDATE catalog_services SET is_active = %s, updated_at = CURRENT_TIMESTAMP WHERE service_code = %s",
                    (1 if active else 0, service_code)
                )
            return True
        except Exception:
            return False

    # ═══════════════════════════════════════════════════════════
    # PRICING (per country + service + provider)
    # ═══════════════════════════════════════════════════════════

    def get_pricing(self, country_code: str, service_code: str,
                    provider_id: Optional[int] = None) -> list[dict]:
        """Get pricing rules for a country+service combination."""
        try:
            where = "WHERE cp.country_code = %s AND cp.service_code = %s"
            params = [country_code, service_code]
            if provider_id:
                where += " AND cp.provider_id = %s"
                params.append(provider_id)

            with db_context('default', transactional=False) as db:
                rows = db.fetchall(
                    f"SELECT cp.id, cp.country_code, cp.service_code, p.name as provider_name, "
                    f"cp.base_price_usd, cp.profit_pct, cp.profit_fixed, "
                    f"cp.min_price, cp.max_price, cp.final_price, cp.is_active "
                    f"FROM catalog_prices cp "
                    f"JOIN providers p ON cp.provider_id = p.id "
                    f"{where}",
                    params
                )
                return [
                    {'id': r[0], 'country': r[1], 'service': r[2],
                     'provider': r[3], 'base_price': float(r[4] or 0),
                     'profit_pct': float(r[5] or 0), 'profit_fixed': float(r[6] or 0),
                     'min_price': float(r[7] or 0), 'max_price': float(r[8] or 0),
                     'final_price': float(r[9] or 0), 'active': bool(r[10])}
                    for r in rows
                ]
        except Exception as e:
            logger.error(f"Failed to get pricing: {e}")
            return []

    def set_pricing(self, country_code: str, service_code: str,
                    provider_id: int, base_price_usd: float,
                    profit_pct: float = 30, profit_fixed: float = 0,
                    min_price: float = 0, max_price: float = 0) -> bool:
        """Set or update pricing rules for a specific combination."""
        final_price = max(
            base_price_usd * (1 + profit_pct / 100) + profit_fixed,
            min_price
        )
        if max_price > 0:
            final_price = min(final_price, max_price)

        try:
            with db_context('default', transactional=True) as db:
                db.execute(
                    """INSERT INTO catalog_prices
                       (country_code, service_code, provider_id, base_price_usd, profit_pct,
                        profit_fixed, min_price, max_price, final_price, is_active)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
                       ON CONFLICT (country_code, service_code, provider_id) DO UPDATE SET
                       base_price_usd = %s, profit_pct = %s, profit_fixed = %s,
                       min_price = %s, max_price = %s, final_price = %s,
                       updated_at = CURRENT_TIMESTAMP""",
                    (country_code, service_code, provider_id, base_price_usd,
                     profit_pct, profit_fixed, min_price, max_price, final_price,
                     base_price_usd, profit_pct, profit_fixed, min_price, max_price, final_price)
                )
            return True
        except Exception as e:
            logger.error(f"Failed to set pricing: {e}")
            return False

    def toggle_pricing(self, pricing_id: int, active: bool) -> bool:
        """Enable/disable a pricing rule."""
        try:
            with db_context('default', transactional=True) as db:
                db.execute(
                    "UPDATE catalog_prices SET is_active = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (1 if active else 0, pricing_id)
                )
            return True
        except Exception:
            return False

    # ═══════════════════════════════════════════════════════════
    # FULL CATALOG (for customer display)
    # ═══════════════════════════════════════════════════════════

    def get_customer_catalog(self) -> dict:
        """
        Get the complete customer-facing catalog:
        Active services → Active countries → Best available prices.

        This is the ONLY data structure that reaches the customer bot.
        """
        services = self.get_active_services()
        countries = self.get_active_countries()

        catalog = {'services': [], 'countries': countries}

        for svc in services:
            svc_entry = {
                'code': svc['code'],
                'name': svc['name'],
                'category': svc['category'],
                'countries': []
            }
            for country in countries:
                pricing = self.get_pricing(country['code'], svc['code'])
                if pricing:
                    best = pricing[0]
                    svc_entry['countries'].append({
                        'code': country['code'],
                        'name': country['name'],
                        'price': best['final_price'],
                        'available': True,
                    })
            catalog['services'].append(svc_entry)

        return catalog

    # ═══════════════════════════════════════════════════════════
    # ADMIN STATS
    # ═══════════════════════════════════════════════════════════

    def get_stats(self) -> dict:
        """Get catalog statistics for admin dashboard."""
        try:
            with db_context('default', transactional=False) as db:
                countries = db.fetchone("SELECT COUNT(*) FROM catalog_countries WHERE is_active = 1")
                services = db.fetchone("SELECT COUNT(*) FROM catalog_services WHERE is_active = 1")
                prices = db.fetchone("SELECT COUNT(*) FROM catalog_prices WHERE is_active = 1")

            return {
                'active_countries': countries[0] if countries else 0,
                'active_services': services[0] if services else 0,
                'active_prices': prices[0] if prices else 0,
            }
        except Exception:
            return {'active_countries': 0, 'active_services': 0, 'active_prices': 0}


# ── Global instance ────────────────────────────────────────────
catalog = CatalogManager()