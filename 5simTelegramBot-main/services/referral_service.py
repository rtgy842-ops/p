"""
services/referral_service.py — Anti-Fraud Referral System
─────────────────────────────────────────────────
Referral program with DB-persisted tracking and fraud prevention.
"""

import hashlib
import logging
import time

logger = logging.getLogger(__name__)


class ReferralService:
    """
    Referral system with database-persisted tracking and anti-fraud measures.
    """

    # ── Anti-fraud limits ──────────────────────────────────────
    MAX_REFERRALS_PER_USER = 50
    MIN_DAYS_BETWEEN_SELF_REFERRAL = 7
    REFERRAL_BONUS_AMOUNT = 5000  # Toman
    REFERRER_COMMISSION_PCT = 10  # % of referee's first purchase

    def __init__(self):
        self._cache: dict[int, str] = {}  # transient code cache

    def generate_code(self, user_id: int) -> str:
        """Generate a unique referral code for a user, persisted to DB."""
        code = hashlib.sha256(
            f"{user_id}:{int(time.time())}:referral".encode()
        ).hexdigest()[:10].upper()

        try:
            from db.context import db_context
            with db_context('default', transactional=True) as db:
                db.execute(
                    """INSERT INTO referral_codes (user_id, code, is_active)
                       VALUES (%s, %s, 1)
                       ON CONFLICT (user_id) DO UPDATE SET code = %s, is_active = 1""",
                    (user_id, code, code)
                )
            self._cache[user_id] = code
            logger.info(f"Referral code generated: {code} for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to persist referral code: {e}")
            return ''
        return code

    def get_code(self, user_id: int) -> str:
        """Get existing referral code or generate new one (DB-backed)."""
        # Check cache first
        if user_id in self._cache:
            return self._cache[user_id]

        # Check database
        try:
            from db.context import db_context
            with db_context('default', transactional=False) as db:
                row = db.fetchone(
                    "SELECT code FROM referral_codes WHERE user_id = %s AND is_active = 1",
                    (user_id,)
                )
                if row:
                    code = row[0] if not isinstance(row, dict) else row.get('code')
                    self._cache[user_id] = code
                    return code
        except Exception as e:
            logger.error(f"Failed to read referral code: {e}")

        # Generate new
        return self.generate_code(user_id)

    def validate_referral(self, referrer_code: str, new_user_id: int,
                          ip_address: str = '') -> tuple[bool, str]:
        """
        Validate a referral attempt against DB.
        Returns (is_valid, reason).
        """
        # Anti-self-referral: cannot refer yourself
        try:
            from db.context import db_context
            with db_context('default', transactional=False) as db:
                row = db.fetchone(
                    "SELECT user_id FROM referral_codes WHERE code = %s AND is_active = 1",
                    (referrer_code,)
                )
                if not row:
                    return False, "Invalid referral code"

                referrer_id = row[0] if not isinstance(row, dict) else row.get('user_id')

                if referrer_id == new_user_id:
                    return False, "Cannot refer yourself"

                # Check if user already has a referrer
                existing = db.fetchone(
                    "SELECT 1 FROM referrals WHERE referred_id = %s",
                    (new_user_id,)
                )
                if existing:
                    return False, "Already referred by another user"

                # IP-based abuse check
                if ip_address:
                    # Check for same-IP patterns (anti-fraud)
                    recent = db.fetchone(
                        "SELECT COUNT(*) as cnt FROM fraud_log WHERE ip_address = %s AND created_at > CURRENT_TIMESTAMP - INTERVAL '1 hour'",
                        (ip_address,)
                    )
                    ip_count = recent[0] if recent and not isinstance(recent, dict) else 0
                    if ip_count > 10:
                        logger.warning(f"High-activity IP detected: {ip_address}, user={new_user_id}")
                        return False, "Suspicious activity detected"

            return True, str(referrer_id)
        except Exception as e:
            logger.error(f"Referral validation error: {e}")
            return False, "System error"

    def get_referrer(self, new_user_id: int) -> int | None:
        """Get the referrer for a user from database."""
        try:
            from db.context import db_context
            with db_context('default', transactional=False) as db:
                row = db.fetchone(
                    "SELECT referrer_id FROM referrals WHERE referred_id = %s AND status = 'active'",
                    (new_user_id,)
                )
                if row:
                    return row[0] if not isinstance(row, dict) else row.get('referrer_id')
        except Exception as e:
            logger.error(f"Failed to get referrer: {e}")
        return None

    def get_referral_count(self, user_id: int) -> int:
        """Get number of successful referrals from database."""
        try:
            from db.context import db_context
            with db_context('default', transactional=False) as db:
                row = db.fetchone(
                    "SELECT COUNT(*) as cnt FROM referrals WHERE referrer_id = %s AND status = 'active'",
                    (user_id,)
                )
                if row:
                    return row[0] if not isinstance(row, dict) else row.get('cnt', 0)
        except Exception as e:
            logger.error(f"Failed to count referrals: {e}")
        return 0

    def get_referral_earnings(self, user_id: int) -> int:
        """Get total referral earnings from database."""
        try:
            from db.context import db_context
            with db_context('default', transactional=False) as db:
                row = db.fetchone(
                    "SELECT COALESCE(SUM(total_earned), 0) as total FROM referrals WHERE referrer_id = %s",
                    (user_id,)
                )
                if row:
                    return row[0] if not isinstance(row, dict) else row.get('total', 0)
        except Exception as e:
            logger.error(f"Failed to get referral earnings: {e}")
        return 0

    def can_receive_bonus(self, user_id: int) -> bool:
        """Check if a user hasn't exceeded referral bonus limits."""
        return self.get_referral_count(user_id) < self.MAX_REFERRALS_PER_USER

    def record_referral(self, referrer_id: int, new_user_id: int) -> bool:
        """
        Record a successful referral in the database.
        Awards bonus to referrer via wallet.
        """
        try:
            code = self.get_code(referrer_id)
            if not code:
                return False

            from db.context import db_context
            with db_context('default', transactional=True) as db:
                db.execute(
                    """INSERT INTO referrals (referrer_id, referred_id, code, status, commission_pct)
                       VALUES (%s, %s, %s, 'active', %s)""",
                    (referrer_id, new_user_id, code, self.REFERRER_COMMISSION_PCT)
                )

            # Award referral bonus
            try:
                from services.wallet_service import WalletService
                wallet = WalletService()
                wallet.deposit(
                    referrer_id,
                    self.REFERRAL_BONUS_AMOUNT,
                    f'Referral bonus: invited user {new_user_id}',
                    f'ref_{new_user_id}'
                )
            except Exception as e:
                logger.warning(f"Failed to credit referral bonus: {e}")

            logger.info(f"Referral recorded: {referrer_id} → {new_user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to record referral: {e}")
            return False

    def get_referral_stats(self, user_id: int) -> dict:
        """Get comprehensive referral statistics for a user."""
        return {
            'code': self.get_code(user_id),
            'total_referrals': self.get_referral_count(user_id),
            'total_earned': self.get_referral_earnings(user_id),
            'bonus_amount': self.REFERRAL_BONUS_AMOUNT,
            'commission_pct': self.REFERRER_COMMISSION_PCT,
        }

    def add_commission(self, referrer_id: int, amount: int) -> bool:
        """Add commission to referrer when their referral makes a purchase."""
        try:
            commission = int(amount * self.REFERRER_COMMISSION_PCT / 100)
            if commission <= 0:
                return False

            from db.context import db_context
            with db_context('default', transactional=True) as db:
                db.execute(
                    "UPDATE referrals SET total_earned = total_earned + %s WHERE referrer_id = %s",
                    (commission, referrer_id)
                )

            from services.wallet_service import WalletService
            wallet = WalletService()
            wallet.deposit(referrer_id, commission, f'Referral commission: {amount} purchase', 'ref_comm')
            return True
        except Exception as e:
            logger.error(f"Failed to add referral commission: {e}")
            return False


    def get_or_create_code(self, user_id: int) -> str:
        """Get existing referral code or create one."""
        try:
            from db.context import db_context
            with db_context('default', transactional=False) as db:
                row = db.fetchone(
                    "SELECT code FROM referral_codes WHERE user_id = %s AND is_active = 1",
                    (user_id,))
                if row:
                    code = row[0] if not isinstance(row, dict) else row.get('code')
                    if code:
                        return code
            # Create new code
            return self.generate_code(user_id)
        except Exception as e:
            logger.error(f"get_or_create_code error: {e}")
            return ''

    def get_referred_users(self, user_id: int) -> list[dict]:
        """Get list of users referred by this user."""
        try:
            from db.context import db_context
            with db_context('default', transactional=False) as db:
                rows = db.fetchall(
                    """SELECT r.referred_id, r.status, r.total_earned, r.created_at,
                       u.first_name
                       FROM referrals r
                       LEFT JOIN users u ON r.referred_id = u.user_id
                       WHERE r.referrer_id = %s
                       ORDER BY r.created_at DESC""",
                    (user_id,))
                return [
                    {'referred_id': row[0] if not isinstance(row, dict) else row.get('referred_id'),
                     'status': row[1] if not isinstance(row, dict) else row.get('status'),
                     'total_earned': row[2] if not isinstance(row, dict) else row.get('total_earned', 0),
                     'created_at': str(row[3]) if not isinstance(row, dict) else str(row.get('created_at', '')),
                     'name': row[4] if not isinstance(row, dict) else row.get('first_name', '')}
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"get_referred_users error: {e}")
            return []


# ── Global instance ────────────────────────────────────────────
referrals = ReferralService()
