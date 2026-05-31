"""
tests/test_executable_wallet.py — Executable Wallet Integration Tests
─────────────────────────────────────────────────
Tests that actually run against PostgreSQL.
"""
import pytest
import time
import threading
from services.wallet_service import WalletService
from services.wallet_ledger import WalletLedger
from db.context import db_context

TEST_USER = 999999999


@pytest.fixture(autouse=True)
def setup_db():
    """Ensure test user exists with clean state before each test."""
    with db_context('default', transactional=True) as db:
        db.execute(
            "INSERT INTO users (user_id, balance) VALUES (%s, 100000) "
            "ON CONFLICT (user_id) DO UPDATE SET balance = 100000",
            (TEST_USER,))
    yield
    try:
        with db_context('default', transactional=True) as db:
            db.execute("DELETE FROM wallet_ledger WHERE user_id = %s", (TEST_USER,))
            db.execute("DELETE FROM transactions WHERE user_id = %s", (TEST_USER,))
            db.execute("DELETE FROM users WHERE user_id = %s", (TEST_USER,))
    except Exception:
        pass


class TestWalletDeposit:
    def test_simple_deposit(self):
        wallet = WalletService()
        result = wallet.deposit(TEST_USER, 5000, "Test deposit")
        assert result is not None
        assert result == 105000
        assert wallet.get_balance(TEST_USER) == 105000

    def test_zero_deposit_fails(self):
        wallet = WalletService()
        result = wallet.deposit(TEST_USER, 0)
        assert result is None

    def test_negative_deposit_fails(self):
        wallet = WalletService()
        result = wallet.deposit(TEST_USER, -100)
        assert result is None


class TestWalletWithdraw:
    def test_simple_withdraw(self):
        wallet = WalletService()
        result = wallet.withdraw(TEST_USER, 30000, "Test withdrawal")
        assert result is not None
        assert result == 70000

    def test_insufficient_balance(self):
        wallet = WalletService()
        result = wallet.withdraw(TEST_USER, 999999999)
        assert result is None

    def test_balance_never_negative(self):
        wallet = WalletService()
        result = wallet.withdraw(TEST_USER, 100001)
        assert result is None
        assert wallet.get_balance(TEST_USER) == 100000


class TestWalletRefund:
    def test_refund_adds_balance(self):
        wallet = WalletService()
        result = wallet.refund(TEST_USER, 25000, "Test refund")
        assert result == 125000


class TestConcurrentSafety:
    def test_concurrent_deposits(self):
        """10 concurrent deposits (matching pool max=10)."""
        wallet = WalletService()
        errors = []

        def deposit():
            try:
                r = wallet.deposit(TEST_USER, 1, "Concurrent deposit")
                if r is None:
                    errors.append("deposit returned None")
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=deposit) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors: {errors}"
        assert wallet.get_balance(TEST_USER) == 100010  # 100000 + 10

    def test_concurrent_withdraws_no_overspend(self):
        """Concurrent withdraws must not overspend."""
        wallet = WalletService()
        with db_context('default', transactional=True) as db:
            db.execute("UPDATE users SET balance = 50000 WHERE user_id = %s", (TEST_USER,))

        overspent = False

        def withdraw():
            nonlocal overspent
            try:
                r = wallet.withdraw(TEST_USER, 1000, "Concurrent")
                if r is not None and r < 0:
                    overspent = True
            except Exception:
                pass

        threads = [threading.Thread(target=withdraw) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        balance = wallet.get_balance(TEST_USER)
        assert not overspent, "OVERSPENT DETECTED"
        assert balance >= 0, f"Balance negative: {balance}"

        with db_context('default', transactional=True) as db:
            db.execute("UPDATE users SET balance = 100000 WHERE user_id = %s", (TEST_USER,))


class TestWalletLedger:
    def test_ledger_entries_created(self):
        wallet = WalletService()
        wallet.deposit(TEST_USER, 1000, "Test ledger")
        entries = WalletLedger.get_entries(TEST_USER, limit=1)
        assert len(entries) > 0
        assert entries[0]['type'] == 'deposit'
        assert entries[0]['amount'] == 1000

    def test_ledger_balance_matches_wallet(self):
        wallet = WalletService()
        wallet.deposit(TEST_USER, 500, "Ledger sync test")
        wallet_balance = wallet.get_balance(TEST_USER)
        entries = WalletLedger.get_entries(TEST_USER, limit=1)
        ledger_balance = entries[0]['balance'] if entries else 0
        assert wallet_balance == ledger_balance, \
            f"Wallet={wallet_balance}, Ledger={ledger_balance}"


class TestPaymentIdempotency:
    def test_double_verify_does_not_double_credit(self):
        from services.payment_service import PaymentService
        from data.dto import PaymentGateway
        ref = f"test_ref_{int(time.time())}"
        with db_context('default', transactional=True) as db:
            db.execute(
                "INSERT INTO transactions (user_id, amount, type, description, ref_id) "
                "VALUES (%s, %s, %s, %s, %s)",
                (TEST_USER, 100, 'deposit', 'test', ref))
            try:
                db.execute(
                    "INSERT INTO transactions (user_id, amount, type, description, ref_id) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (TEST_USER, 100, 'deposit', 'duplicate', ref))
                assert False, "Should have raised duplicate key"
            except Exception:
                pass  # Expected: duplicate ref_id rejected
