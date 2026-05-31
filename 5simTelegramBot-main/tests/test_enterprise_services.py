"""
tests/test_enterprise_services.py — Enterprise Service Integration Tests
─────────────────────────────────────────────────
Tests all newly created enterprise services.
"""

import os
import sys

# Ensure the project root is on the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestCurrencyEngine:
    """Tests for the multi-currency engine."""

    def test_base_currency_is_usd(self):
        from services.currency_engine import CurrencyEngine
        engine = CurrencyEngine()
        assert engine.BASE_CURRENCY == 'USD'

    def test_convert_usd_to_usd(self):
        from services.currency_engine import CurrencyEngine
        engine = CurrencyEngine()
        result = engine.convert_from_usd(100.0, 'USD')
        assert result == 100.0

    def test_convert_to_usd_is_identity(self):
        from services.currency_engine import CurrencyEngine
        engine = CurrencyEngine()
        result = engine.convert_to_usd(100.0, 'USD')
        assert result == 100.0

    def test_format_amount(self):
        from services.currency_engine import CurrencyEngine
        engine = CurrencyEngine()
        formatted = engine.format_amount(1500, 'USD')
        assert '$' in formatted

    def test_get_active_currencies(self):
        from services.currency_engine import CurrencyEngine
        engine = CurrencyEngine()
        currencies = engine.get_active_currencies()
        assert isinstance(currencies, list)

    def test_default_currency(self):
        from services.currency_engine import CurrencyEngine
        engine = CurrencyEngine()
        default = engine.get_default_currency()
        assert default in ('USD', 'IRR')


class TestSubscriptionService:
    """Tests for the subscription tier system."""

    def test_all_tiers_defined(self):
        from services.subscription_service import TIER_CONFIG, SubscriptionTier
        for tier in SubscriptionTier:
            assert tier in TIER_CONFIG, f"{tier} missing from TIER_CONFIG"

    def test_free_has_no_api_access(self):
        from services.subscription_service import TIER_CONFIG, SubscriptionTier
        assert TIER_CONFIG[SubscriptionTier.FREE].api_access is False

    def test_enterprise_has_api_access(self):
        from services.subscription_service import TIER_CONFIG, SubscriptionTier
        assert TIER_CONFIG[SubscriptionTier.ENTERPRISE].api_access is True

    def test_reseller_has_white_label(self):
        from services.subscription_service import TIER_CONFIG, SubscriptionTier
        assert TIER_CONFIG[SubscriptionTier.RESELLER].white_label is True

    def test_discounts_increase_with_tier(self):
        from services.subscription_service import TIER_CONFIG, SubscriptionTier
        free_disc = TIER_CONFIG[SubscriptionTier.FREE].price_discount_pct
        premium_disc = TIER_CONFIG[SubscriptionTier.PREMIUM].price_discount_pct
        enterprise_disc = TIER_CONFIG[SubscriptionTier.ENTERPRISE].price_discount_pct
        assert enterprise_disc > premium_disc
        assert premium_disc >= free_disc


class TestReferralService:
    """Tests for the referral system."""

    def test_constants_defined(self):
        from services.referral_service import ReferralService
        svc = ReferralService()
        assert svc.REFERRAL_BONUS_AMOUNT > 0
        assert 0 < svc.REFERRER_COMMISSION_PCT <= 100
        assert svc.MAX_REFERRALS_PER_USER > 0

    def test_generate_code_returns_string(self):
        from services.referral_service import ReferralService
        svc = ReferralService()
        code = svc.generate_code(123456)
        assert isinstance(code, str)
        assert len(code) == 10

    def test_get_code_consistency(self):
        from services.referral_service import ReferralService
        svc = ReferralService()
        code1 = svc.get_code(99999)
        code2 = svc.get_code(99999)
        assert code1 == code2, "get_code should return same code for same user"


class TestRBACService:
    """Tests for the role-based access control."""

    def test_all_roles_defined(self):
        from services.rbac_service import Role
        assert len(list(Role)) == 6

    def test_super_admin_has_all_permissions(self):
        from services.rbac_service import ROLE_PERMISSIONS, Permission, Role
        super_admin_perms = ROLE_PERMISSIONS[Role.SUPER_ADMIN]
        assert len(super_admin_perms) == len(list(Permission))

    def test_analyst_cannot_edit_users(self):
        from services.rbac_service import ROLE_PERMISSIONS, Permission, Role
        analyst_perms = ROLE_PERMISSIONS[Role.ANALYST]
        assert Permission.USERS_EDIT not in analyst_perms

    def test_finance_can_manage_payments(self):
        from services.rbac_service import ROLE_PERMISSIONS, Permission, Role
        finance_perms = ROLE_PERMISSIONS[Role.FINANCE]
        assert Permission.PAYMENTS_APPROVE in finance_perms

    def test_support_is_read_only(self):
        from services.rbac_service import ROLE_PERMISSIONS, Role
        support_perms = ROLE_PERMISSIONS[Role.SUPPORT]
        for perm in support_perms:
            assert ':view' in perm.value, f"Support has write permission: {perm}"


class TestSmartRouter:
    """Tests for the smart routing engine."""

    def test_strategies_defined(self):
        from services.smart_router import RoutingStrategy
        strategies = list(RoutingStrategy)
        assert len(strategies) >= 3

    def test_default_strategy_is_best_price(self):
        from services.smart_router import SmartRouter
        router = SmartRouter()
        strategy = router.get_strategy()
        from services.smart_router import RoutingStrategy
        assert strategy == RoutingStrategy.BEST_PRICE

    def test_set_strategy(self):
        from services.smart_router import RoutingStrategy, SmartRouter
        router = SmartRouter()
        router.set_strategy(RoutingStrategy.HIGHEST_AVAILABILITY)
        assert router.get_strategy() == RoutingStrategy.HIGHEST_AVAILABILITY


class TestAntiFraudEngine:
    """Tests for the anti-fraud detection system."""

    def test_risk_levels_exist(self):
        from services.anti_fraud import RiskLevel
        levels = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        assert len(levels) == 4

    def test_evaluate_returns_dict(self):
        from services.anti_fraud import AntiFraudEngine
        engine = AntiFraudEngine()
        result = engine.evaluate(12345, 'order', '127.0.0.1', '', 50000)
        assert isinstance(result, dict)
        assert 'risk_score' in result
        assert 'risk_level' in result
        assert 'action' in result
        assert 'checks' in result

    def test_localhost_ip_is_low_risk(self):
        from services.anti_fraud import AntiFraudEngine
        engine = AntiFraudEngine()
        result = engine.evaluate(12345, 'order', '127.0.0.1', '', 50000)
        assert result['risk_level'] in (RiskLevel.LOW, 'low')

    def test_zero_amount_is_high_risk(self):
        from services.anti_fraud import AntiFraudEngine
        engine = AntiFraudEngine()
        result = engine.evaluate(12345, 'order', '192.168.1.1', '', 0)
        # Zero amounts should score high
        assert result['risk_score'] >= 50

    def test_negative_amount_is_high_risk(self):
        from services.anti_fraud import AntiFraudEngine
        engine = AntiFraudEngine()
        result = engine.evaluate(12345, 'deposit', '10.0.0.1', '', -100)
        assert result['risk_score'] >= 50


class TestProviderRegistry:
    """Tests for the provider registry."""

    def test_singleton_pattern(self):
        from services.provider_registry import ProviderRegistry
        r1 = ProviderRegistry.get_instance()
        r2 = ProviderRegistry.get_instance()
        assert r1 is r2

    def test_active_providers_returns_list(self):
        from services.provider_registry import provider_registry
        active = provider_registry.active_providers
        assert isinstance(active, list)

    def test_health_check_returns_dict(self):
        from services.provider_registry import provider_registry
        result = provider_registry.health_check_all()
        assert isinstance(result, dict)

    def test_stats(self):
        from services.provider_registry import provider_registry
        stats = provider_registry.get_stats()
        assert 'total_providers' in stats
        assert 'active_providers' in stats
        assert 'health' in stats


class TestCatalogManager:
    """Tests for the catalog management system."""

    def test_get_active_countries_returns_list(self):
        from services.catalog_manager import catalog
        countries = catalog.get_active_countries()
        assert isinstance(countries, list)

    def test_get_active_services_returns_list(self):
        from services.catalog_manager import catalog
        services = catalog.get_active_services()
        assert isinstance(services, list)

    def test_get_stats_returns_dict(self):
        from services.catalog_manager import catalog
        stats = catalog.get_stats()
        assert 'active_countries' in stats
        assert 'active_services' in stats
        assert 'active_prices' in stats

    def test_get_customer_catalog(self):
        from services.catalog_manager import catalog
        cat = catalog.get_customer_catalog()
        assert 'services' in cat
        assert 'countries' in cat


class TestOrderStateMachine:
    """Tests for the order state machine."""

    def test_active_states(self):
        from data.dto import OrderStatus
        active = OrderStatus.active_states()
        assert OrderStatus.CREATED in active
        assert OrderStatus.COMPLETED not in active

    def test_terminal_states(self):
        from data.dto import OrderStatus
        terminal = OrderStatus.terminal_states()
        assert OrderStatus.COMPLETED in terminal
        assert OrderStatus.CREATED not in terminal

    def test_is_active(self):
        from data.dto import OrderStatus
        assert OrderStatus.CREATED.is_active()
        assert not OrderStatus.COMPLETED.is_active()

    def test_transitions(self):
        from services.order_service import OrderService, OrderStatus
        svc = OrderService()
        assert svc.can_transition(OrderStatus.CREATED, OrderStatus.PAID)
        assert svc.can_transition(OrderStatus.WAITING_SMS, OrderStatus.COMPLETED)
        assert not svc.can_transition(OrderStatus.COMPLETED, OrderStatus.CREATED)


class TestPaymentGateway:
    """Tests for payment gateway DTOs and service."""

    def test_payment_gateways_exist(self):
        from data.dto import PaymentGateway
        assert PaymentGateway.ZARINPAL.value == 'zarinpal'
        assert PaymentGateway.CARD_TO_CARD.value == 'card_to_card'

    def test_payment_result_dto(self):
        from data.dto import PaymentGateway, PaymentResultDTO
        result = PaymentResultDTO(
            success=True,
            gateway=PaymentGateway.ZARINPAL,
            payment_url='https://payment.example.com',
            authority='AUTH123'
        )
        assert result.success is True
        assert result.authority == 'AUTH123'


class TestConfigSecurity:
    """Tests for configuration security hardening."""

    def test_no_hardcoded_secrets(self):
        """Verify config.py has no hardcoded API keys/tokens."""
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'config.py'
        )
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # These represent hardcoded secrets that should NOT be in the file
        hardcoded_patterns = [
            '8867840427',  # Old bot token
            'cb28fe1389',  # Old Herosms key
            '1344b5d4-0048-11e8',  # Old ZarinPal merchant
        ]
        for pattern in hardcoded_patterns:
            assert pattern not in content, f"Hardcoded secret found: {pattern}"

    def test_require_function_exists(self):
        """Verify _require function is defined."""
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'config.py'
        )
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()
        assert 'def _require(' in content, "_require() function not found"
        assert 'RuntimeError' in content, "RuntimeError not raised for missing secrets"


class TestEventBus:
    """Tests for the internal event bus."""

    def test_subscribe_and_emit(self):
        from services.event_bus import EventBus
        bus = EventBus()
        received = []

        @bus.on('test:event')
        def handler(data):
            received.append(data)

        bus.emit('test:event', {'value': 42})
        assert len(received) == 1
        assert received[0]['value'] == 42

    def test_multiple_subscribers(self):
        from services.event_bus import EventBus
        bus = EventBus()
        count = [0]

        @bus.on('test:multi')
        def handler1(data):
            count[0] += 1

        @bus.on('test:multi')
        def handler2(data):
            count[0] += 1

        bus.emit('test:multi', {})
        assert count[0] == 2

    def test_error_isolation(self):
        from services.event_bus import EventBus
        bus = EventBus()
        received = []

        @bus.on('test:error_isolation')
        def failing_handler(data):
            raise ValueError("Intentional test error")

        @bus.on('test:error_isolation')
        def working_handler(data):
            received.append('ok')

        # Should not raise—error is caught internally
        bus.emit('test:error_isolation', {})
        assert len(received) == 1
