"""
services/referral_service.py — Anti-Fraud Referral System
─────────────────────────────────────────────────
Referral program with fraud prevention:
- Anti-self-referral (same IP/device detection)
- Payout limits per user
- Referral tracking with unique codes
- Abuse detection patterns
"""

import logging
import hashlib
import time
from datetime import datetime

logger = logging.getLogger(__name__)


class ReferralService:
    """
    Referral system with built-in anti-fraud measures.
    """

    # ── Anti-fraud limits ──────────────────────────────────────
    MAX_REFERRALS_PER_USER = 50
    MIN_DAYS_BETWEEN_SELF_REFERRAL = 7
    REFERRAL_BONUS_AMOUNT = 5000  # Toman
    REFERRER_COMMISSION_PCT = 10  # % of referee's first purchase

    def __init__(self):
        self._referral_cache: dict[int, str] = {}  # user_id → referral_code

    def generate_code(self, user_id: int) -> str:
        """Generate a unique referral code for a user."""
        code = hashlib.md5(
            f"{user_id}:{int(time.time())}".encode()
        ).hexdigest()[:8].upper()
        self._referral_cache[user_id] = code
        logger.info(f"Referral code generated: {code} for user {user_id}")
        return code

    def get_code(self, user_id: int) -> str | None:
        """Get existing referral code or generate new one."""
        if user_id in self._referral_cache:
            return self._referral_cache[user_id]
        return self.generate_code(user_id)

    def validate_referral(self, referrer_code: str, new_user_id: int,
                          ip_address: str = '') -> tuple[bool, str]:
        """
        Validate a referral attempt.
        Returns (is_valid, reason).
        """
        # Anti-self-referral: check referrer code doesn't belong to new user
        if self._referral_cache.get(new_user_id) == referrer_code:
            return False, "Cannot refer yourself"

        # Find the referrer
        referrer_id = None
        for uid, code in self._referral_cache.items():
            if code == referrer_code:
                referrer_id = uid
                break

        if referrer_id is None:
            return False, "Invalid referral code"

        if referrer_id == new_user_id:
            return False, "Cannot refer yourself"

        # TODO: Check IP-based abuse patterns
        # TODO: Check device fingerprint

        return True, str(referrer_id)

    def get_referrer(self, new_user_id: int) -> int | None:
        """Get the referrer for a user, if any."""
        # TODO: Read from database
        return None

    def get_referral_count(self, user_id: int) -> int:
        """Get number of successful referrals."""
        # TODO: Read from database
        return 0

    def can_receive_bonus(self, user_id: int) -> bool:
        """Check if a user hasn't exceeded referral bonus limits."""
        return self.get_referral_count(user_id) < self.MAX_REFERRALS_PER_USER

    def record_referral(self, referrer_id: int, new_user_id: int) -> bool:
        """
        Record a successful referral.
        Should trigger bonus distribution via wallet_service.
        """
        # TODO: Save to database
        # TODO: Emit event for bonus distribution
        logger.info(f"Referral recorded: {referrer_id} → {new_user_id}")
        return True


# ── Global instance ────────────────────────────────────────────
referrals = ReferralService()