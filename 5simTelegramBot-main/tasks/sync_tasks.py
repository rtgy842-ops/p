"""
tasks/sync_tasks.py — Celery Tasks for Provider Synchronization
─────────────────────────────────────────────────
Periodic tasks that sync countries, services, prices from
external SMS providers into the local database catalog.

Triggered by Celery Beat schedule (see celery_app.py).
"""
import logging
from celery import shared_task
from db.context import db_context

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# PROVIDER SYNC TASKS
# ═══════════════════════════════════════════════════════════════


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def sync_hero_countries(self):
    """
    Fetch active countries from HeroSMS REST API and upsert into
    provider_countries + catalog_countries tables.
    Run every 6 hours.
    """
    from services.providers.herosms_rest_provider import HeroSMSRESTProvider

    provider = HeroSMSRESTProvider()
    try:
        countries = provider.get_countries()
    except Exception as e:
        logger.error(f"sync_hero_countries failed: {e}")
        raise self.retry(exc=e)

    try:
        with db_context('default', transactional=True) as db:
            # Get HeroSMS provider ID
            provider_id = _ensure_provider(db, 'herosms', 'HeroSMS')
            if not provider_id:
                logger.warning("HeroSMS provider not registered, skipping sync")
                return {"status": "skipped", "reason": "provider not registered"}

            synced = 0
            for country_code, country_data in countries.items():
                country_name = (country_data.get('name', country_code)
                                if isinstance(country_data, dict)
                                else str(country_data))

                # Upsert into provider_countries
                db.execute(
                    """INSERT INTO provider_countries
                       (provider_id, country_code, country_name, is_active, last_sync_at)
                       VALUES (%s, %s, %s, 1, CURRENT_TIMESTAMP)
                       ON CONFLICT (provider_id, country_code) DO UPDATE SET
                       country_name = EXCLUDED.country_name,
                       last_sync_at = CURRENT_TIMESTAMP""",
                    (provider_id, str(country_code), country_name)
                )

                # Upsert into catalog_countries (if not exists)
                db.execute(
                    """INSERT INTO catalog_countries (country_code, country_name)
                       VALUES (%s, %s)
                       ON CONFLICT (country_code) DO NOTHING""",
                    (str(country_code), country_name)
                )
                synced += 1

            logger.info(f"sync_hero_countries: synced {synced} countries")

            # Deactivate countries no longer returned by provider
            _deactivate_missing(db, 'provider_countries', provider_id,
                                list(countries.keys()), 'country_code')

        return {"status": "success", "countries_synced": synced}
    except Exception as e:
        logger.error(f"sync_hero_countries DB error: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def sync_hero_services(self):
    """
    Fetch active services from HeroSMS REST API and upsert into
    provider_services + catalog_services tables.
    Run every 6 hours (offset 10 min from countries sync).
    """
    from services.providers.herosms_rest_provider import HeroSMSRESTProvider

    provider = HeroSMSRESTProvider()
    try:
        services = provider.get_services()
    except Exception as e:
        logger.error(f"sync_hero_services failed: {e}")
        raise self.retry(exc=e)

    try:
        with db_context('default', transactional=True) as db:
            provider_id = _ensure_provider(db, 'herosms', 'HeroSMS')
            if not provider_id:
                return {"status": "skipped", "reason": "provider not registered"}

            synced = 0
            for service_code, service_data in services.items():
                service_name = (service_data.get('name', service_code)
                                if isinstance(service_data, dict)
                                else str(service_data))

                # Upsert into provider_services
                db.execute(
                    """INSERT INTO provider_services
                       (provider_id, service_code, service_name, is_active, last_sync_at)
                       VALUES (%s, %s, %s, 1, CURRENT_TIMESTAMP)
                       ON CONFLICT (provider_id, service_code) DO UPDATE SET
                       service_name = EXCLUDED.service_name,
                       last_sync_at = CURRENT_TIMESTAMP""",
                    (provider_id, str(service_code), service_name)
                )

                # Upsert into catalog_services (if not exists)
                db.execute(
                    """INSERT INTO catalog_services (service_code, service_name)
                       VALUES (%s, %s)
                       ON CONFLICT (service_code) DO NOTHING""",
                    (str(service_code), service_name)
                )
                synced += 1

            logger.info(f"sync_hero_services: synced {synced} services")

            # Deactivate services no longer returned
            _deactivate_missing(db, 'provider_services', provider_id,
                                list(services.keys()), 'service_code')

        return {"status": "success", "services_synced": synced}
    except Exception as e:
        logger.error(f"sync_hero_services DB error: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def sync_hero_prices(self):
    """
    Fetch current prices from HeroSMS REST API and upsert into
    provider_prices + catalog_prices tables.
    Run every 3 hours.
    """
    from services.providers.herosms_rest_provider import HeroSMSRESTProvider

    provider = HeroSMSRESTProvider()
    try:
        prices = provider.get_prices()
    except Exception as e:
        logger.error(f"sync_hero_prices failed: {e}")
        raise self.retry(exc=e)

    try:
        with db_context('default', transactional=True) as db:
            provider_id = _ensure_provider(db, 'herosms', 'HeroSMS')
            if not provider_id:
                return {"status": "skipped", "reason": "provider not registered"}

            synced = 0
            for country_code, services_dict in prices.items():
                if not isinstance(services_dict, dict):
                    continue
                for service_code, operator_data in services_dict.items():
                    if isinstance(operator_data, dict):
                        # Multiple operators: iterate
                        for op_name, op_info in operator_data.items():
                            if not isinstance(op_info, dict):
                                continue
                            cost = float(op_info.get('cost', 0))
                            count = int(op_info.get('count', 0))
                            _upsert_price(db, provider_id, country_code,
                                          service_code, op_name, cost, count)
                            synced += 1
                    elif isinstance(operator_data, (int, float)):
                        # Single price value
                        _upsert_price(db, provider_id, country_code,
                                      service_code, 'any', float(operator_data), 0)
                        synced += 1

            logger.info(f"sync_hero_prices: synced {synced} price entries")
        return {"status": "success", "prices_synced": synced}
    except Exception as e:
        logger.error(f"sync_hero_prices DB error: {e}")
        raise self.retry(exc=e)


# ═══════════════════════════════════════════════════════════════
# SMS CODE FETCHING
# ═══════════════════════════════════════════════════════════════


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def fetch_pending_sms_codes(self):
    """
    Check all pending orders for received SMS codes.
    Run every 2 minutes.
    """
    from services.sms_service import SMSService

    sms = SMSService()
    try:
        with db_context('default', transactional=False) as db:
            rows = db.fetchall(
                "SELECT id, activation_id FROM orders WHERE status = 'PENDING' LIMIT 50"
            )
    except Exception as e:
        logger.error(f"fetch_pending_sms_codes query error: {e}")
        return {"status": "error", "error": str(e)}

    checked = 0
    received = 0

    for row in rows:
        order_id = row[0]
        activation_id = row[1]
        try:
            result = sms.check_sms(int(activation_id))
            if result.success and result.data:
                status = result.data.get('status', '')
                if status == 'RECEIVED':
                    code = result.data.get('code', '')
                    _save_received_code(order_id, int(activation_id), code)
                    received += 1
            checked += 1
        except Exception as e:
            logger.warning(f"Failed to check SMS for order {order_id}: {e}")

    logger.info(f"fetch_pending_sms_codes: checked={checked}, received={received}")
    return {"status": "success", "checked": checked, "received": received}


# ═══════════════════════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════════════════════


@shared_task(bind=True, max_retries=2, default_retry_delay=120)
def health_check_providers(self):
    """
    Run health checks on all registered providers.
    Run every hour.
    """
    from services.provider_registry import provider_registry

    results = provider_registry.health_check_all()
    healthy = all(v for v in results.values())

    if not healthy:
        unhealthy = [k for k, v in results.items() if not v]
        logger.warning(f"Unhealthy providers: {unhealthy}")

    logger.info(f"health_check_providers: {len(results)} checked, all_healthy={healthy}")
    return {"status": "success", "healthy": healthy, "details": results}


# ═══════════════════════════════════════════════════════════════
# CLEANUP
# ═══════════════════════════════════════════════════════════════


@shared_task(bind=True, max_retries=1)
def cleanup_expired_orders(self):
    """
    Cancel orders that have been PENDING too long (e.g., > 6 hours).
    Run every 2 hours.
    """
    try:
        with db_context('default', transactional=True) as db:
            rows = db.fetchall(
                """SELECT id, activation_id, user_id, price
                   FROM orders
                   WHERE status = 'PENDING'
                   AND created_at < CURRENT_TIMESTAMP - INTERVAL '6 hours'"""
            )

            cancelled = 0
            refunded = 0
            for row in rows:
                order_id, activation_id, user_id, price = row
                db.execute(
                    "UPDATE orders SET status = 'CANCELED' WHERE id = %s",
                    (order_id,))

                # Refund the amount
                db.execute(
                    'UPDATE users SET balance = balance + %s WHERE user_id = %s',
                    (price, user_id))
                db.execute(
                    """INSERT INTO transactions (user_id, amount, type, description)
                       VALUES (%s, %s, %s, %s)""",
                    (user_id, price, 'auto_refund',
                     f'Auto-refund for expired order #{order_id}'))
                refunded += 1
                cancelled += 1

            logger.info(
                f"cleanup_expired_orders: cancelled={cancelled}, refunded={refunded}")
        return {"status": "success", "cancelled": cancelled, "refunded": refunded}
    except Exception as e:
        logger.error(f"cleanup_expired_orders error: {e}")
        raise self.retry(exc=e)


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════


def _ensure_provider(db, name: str, display_name: str) -> int | None:
    """Get or create a provider row. Returns provider_id."""
    row = db.fetchone("SELECT id FROM providers WHERE name = %s", (name,))
    if row:
        return int(row[0])
    db.execute(
        """INSERT INTO providers (name, display_name) VALUES (%s, %s)
           ON CONFLICT (name) DO NOTHING""",
        (name, display_name))
    row = db.fetchone("SELECT id FROM providers WHERE name = %s", (name,))
    return int(row[0]) if row else None


def _deactivate_missing(db, table: str, provider_id: int,
                        active_codes: list[str], code_column: str):
    """Set is_active=0 for codes no longer in the active list."""
    if not active_codes:
        return
    placeholders = ','.join(['%s'] * len(active_codes))
    db.execute(
        f"""UPDATE {table}
            SET is_active = 0
            WHERE provider_id = %s
            AND {code_column} NOT IN ({placeholders})""",
        (provider_id, *active_codes))


def _upsert_price(db, provider_id: int, country_code: str,
                  service_code: str, operator_name: str,
                  price_usd: float, count: int):
    """Upsert a price row into provider_prices."""
    db.execute(
        """INSERT INTO provider_prices
           (provider_id, country_code, service_code, operator_name,
            price_usd, available_count, last_sync_at)
           VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
           ON CONFLICT (provider_id, country_code, service_code, operator_name)
           DO UPDATE SET
           price_usd = EXCLUDED.price_usd,
           available_count = EXCLUDED.available_count,
           last_sync_at = CURRENT_TIMESTAMP""",
        (provider_id, str(country_code), str(service_code),
         str(operator_name), price_usd, count))


def _save_received_code(order_id: int, activation_id: int, code: str):
    """Save a received SMS code and update order status."""
    try:
        with db_context('default', transactional=True) as db:
            db.execute(
                """INSERT INTO activation_codes (order_id, code, status)
                   VALUES (%s, %s, 'received')""",
                (order_id, code))
            db.execute(
                "UPDATE orders SET status = 'RECEIVED' WHERE id = %s",
                (order_id,))
            logger.info(f"Saved code '{code}' for order #{order_id}")
    except Exception as e:
        logger.error(f"Failed to save code for order #{order_id}: {e}")
