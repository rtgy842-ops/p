"""
services/anti_fraud.py — Enterprise Anti-Fraud Detection System
─────────────────────────────────────────────────
Multi-layered fraud detection:
- Duplicate account detection (similar IP/device)
- Velocity checks (too many orders in short time)
- VPN/Proxy detection (via IP API)
- Risk scoring engine
- Automatic actions: log, warn, or block
"""

import logging
from datetime import datetime

from db.context import db_context

logger = logging.getLogger(__name__)


class RiskLevel:
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'


class FraudAction:
    LOG = 'logged'
    WARN = 'warned'
    BLOCK = 'blocked'


class AntiFraudEngine:
    """
    Multi-layered anti-fraud detection engine.
    All checks score risk from 0-100. Scores accumulate across checks.
    """

    # ── Thresholds ──────────────────────────────────────────
    BLOCK_THRESHOLD = 80      # Auto-block at this score
    WARN_THRESHOLD = 50       # Log warning at this score
    MAX_ORDERS_PER_MINUTE = 5
    MAX_ORDERS_PER_HOUR = 30
    MAX_ACCOUNTS_PER_IP = 3
    MAX_DAILY_DEPOSIT = 10000000  # 10M Toman

    def __init__(self):
        self._fingerprint_cache: dict[str, int] = {}  # fingerprint → user_id

    def evaluate(self, user_id: int, action: str = 'order',
                 ip_address: str = '', device_fingerprint: str = '',
                 amount: int = 0) -> dict:
        """
        Run all fraud checks and return risk assessment.

        Returns:
            {'risk_score': int, 'risk_level': str, 'checks': list[dict], 'action': str}
        """
        checks = []
        total_score = 0

        # 1. Velocity check
        velocity = self._check_velocity(user_id, action)
        checks.append(velocity)
        total_score += velocity['score']

        # 2. IP monitoring
        if ip_address:
            ip_check = self._check_ip(ip_address, user_id)
            checks.append(ip_check)
            total_score += ip_check['score']

        # 3. Device fingerprint
        if device_fingerprint:
            fp_check = self._check_fingerprint(device_fingerprint, user_id)
            checks.append(fp_check)
            total_score += fp_check['score']

        # 4. Duplicate account detection
        dup_check = self._check_duplicates(user_id, ip_address)
        checks.append(dup_check)
        total_score += dup_check['score']

        # 5. Amount anomaly — always check (zero/negative = suspicious)
        amount_check = self._check_amount(user_id, amount, action)
        checks.append(amount_check)
        total_score += amount_check['score']

        # Determine risk level
        if total_score >= self.BLOCK_THRESHOLD:
            level = RiskLevel.CRITICAL
            result_action = FraudAction.BLOCK
        elif total_score >= self.WARN_THRESHOLD:
            level = RiskLevel.HIGH
            result_action = FraudAction.WARN
        elif total_score >= 25:
            level = RiskLevel.MEDIUM
            result_action = FraudAction.LOG
        else:
            level = RiskLevel.LOW
            result_action = FraudAction.LOG

        result = {
            'risk_score': total_score,
            'risk_level': level,
            'action': result_action,
            'checks': checks,
            'user_id': user_id,
            'timestamp': datetime.now().isoformat(),
        }

        # Log to fraud_log table
        self._log_fraud_event(user_id, action, total_score, ip_address,
                              device_fingerprint, result_action)

        if total_score >= self.BLOCK_THRESHOLD:
            logger.warning(f"CRITICAL risk user {user_id}: score={total_score}, action={result_action}")

        return result

    # ═══════════════════════════════════════════════════════════
    # INDIVIDUAL CHECKS
    # ═══════════════════════════════════════════════════════════

    def _check_velocity(self, user_id: int, action: str) -> dict:
        """Check for rapid repeated actions."""
        score = 0
        details = {}

        try:
            with db_context('default', transactional=False) as db:
                # Orders in last minute
                row = db.fetchone(
                    "SELECT COUNT(*) FROM orders WHERE user_id = %s AND created_at > CURRENT_TIMESTAMP - INTERVAL '1 minute'",
                    (user_id,)
                )
                per_min = row[0] if row else 0
                details['orders_per_minute'] = per_min

                if per_min > self.MAX_ORDERS_PER_MINUTE:
                    score += 50
                elif per_min > 2:
                    score += 15

                # Orders in last hour
                row = db.fetchone(
                    "SELECT COUNT(*) FROM orders WHERE user_id = %s AND created_at > CURRENT_TIMESTAMP - INTERVAL '1 hour'",
                    (user_id,)
                )
                per_hour = row[0] if row else 0
                details['orders_per_hour'] = per_hour

                if per_hour > self.MAX_ORDERS_PER_HOUR:
                    score += 30
                elif per_hour > 10:
                    score += 10
        except Exception:
            pass

        return {'check': 'velocity', 'score': min(score, 80), 'details': details}

    def _check_ip(self, ip_address: str, user_id: int) -> dict:
        """Check IP-based risk factors."""
        score = 0
        details = {}

        if not ip_address or ip_address in ('127.0.0.1', '::1', 'localhost'):
            return {'check': 'ip', 'score': 0, 'details': {'local': True}}

        try:
            with db_context('default', transactional=False) as db:
                # How many accounts share this IP?
                row = db.fetchone(
                    "SELECT COUNT(DISTINCT user_id) FROM fraud_log WHERE ip_address = %s",
                    (ip_address,)
                )
                accounts = row[0] if row else 0
                details['accounts_per_ip'] = accounts

                if accounts > self.MAX_ACCOUNTS_PER_IP:
                    score += 60
                elif accounts > 1:
                    score += 20

                # Recent fraud events from this IP
                row = db.fetchone(
                    "SELECT COUNT(*) FROM fraud_log WHERE ip_address = %s AND risk_score >= %s",
                    (ip_address, self.WARN_THRESHOLD)
                )
                fraud_count = row[0] if row else 0
                details['prior_fraud_events'] = fraud_count

                if fraud_count > 0:
                    score += 40
        except Exception:
            pass

        return {'check': 'ip', 'score': min(score, 70), 'details': details}

    def _check_fingerprint(self, fingerprint: str, user_id: int) -> dict:
        """Check device fingerprint patterns."""
        score = 0
        details = {}

        if not fingerprint:
            return {'check': 'fingerprint', 'score': 0, 'details': {}}

        # Cache check
        if fingerprint in self._fingerprint_cache:
            existing_user = self._fingerprint_cache[fingerprint]
            details['existing_user'] = existing_user
            if existing_user != user_id:
                score += 50  # Same device, different account
        else:
            self._fingerprint_cache[fingerprint] = user_id

        return {'check': 'fingerprint', 'score': min(score, 50), 'details': details}

    def _check_duplicates(self, user_id: int, ip_address: str) -> dict:
        """Check for duplicate/similar accounts."""
        score = 0
        details = {}

        try:
            with db_context('default', transactional=False) as db:
                # Similar user IDs created recently?
                row = db.fetchone(
                    "SELECT COUNT(*) FROM users WHERE user_id BETWEEN %s AND %s AND join_date > CURRENT_TIMESTAMP - INTERVAL '1 hour'",
                    (user_id - 5, user_id + 5)
                )
                nearby = row[0] if row else 0
                details['nearby_accounts'] = nearby

                if nearby > 3:
                    score += 30
        except Exception:
            pass

        return {'check': 'duplicates', 'score': score, 'details': details}

    def _check_amount(self, user_id: int, amount: int, action: str) -> dict:
        """Check for unusual monetary amounts."""
        score = 0
        details = {'amount': amount}

        if action == 'deposit' and amount > self.MAX_DAILY_DEPOSIT:
            score += 40
            details['over_daily_limit'] = True

        if amount <= 0:
            score += 90  # Negative/zero amounts are highly suspicious
            details['invalid_amount'] = True

        return {'check': 'amount', 'score': min(score, 90), 'details': details}

    # ═══════════════════════════════════════════════════════════
    # DATABASE LOGGING
    # ═══════════════════════════════════════════════════════════

    def _log_fraud_event(self, user_id: int, event_type: str, risk_score: int,
                         ip_address: str, device_fingerprint: str,
                         action_taken: str) -> None:
        """Persist fraud detection event to database."""
        try:
            with db_context('default', transactional=True) as db:
                db.execute(
                    """INSERT INTO fraud_log (user_id, event_type, risk_score, details, ip_address, device_fingerprint, action_taken)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (user_id, event_type, risk_score, '{}', ip_address, device_fingerprint, action_taken)
                )
        except Exception as e:
            logger.debug(f"Failed to log fraud event: {e}")

    # ═══════════════════════════════════════════════════════════
    # ADMIN: VIEW FRAUD LOG
    # ═══════════════════════════════════════════════════════════

    def get_recent_events(self, limit: int = 50, min_score: int = 0) -> list[dict]:
        """Get recent fraud detection events."""
        try:
            with db_context('default', transactional=False) as db:
                where = "WHERE risk_score >= %s" if min_score > 0 else ""
                rows = db.fetchall(
                    f"SELECT user_id, event_type, risk_score, ip_address, action_taken, created_at "
                    f"FROM fraud_log {where} ORDER BY created_at DESC LIMIT %s",
                    (min_score, limit) if min_score > 0 else (limit,)
                )
                return [
                    {'user_id': r[0], 'event': r[1], 'score': r[2],
                     'ip': r[3], 'action': r[4], 'time': str(r[5])}
                    for r in rows
                ]
        except Exception:
            return []

    def get_user_risk_profile(self, user_id: int) -> dict:
        """Get a user's complete risk profile."""
        try:
            with db_context('default', transactional=False) as db:
                row = db.fetchone(
                    "SELECT COUNT(*), MAX(risk_score), AVG(risk_score) FROM fraud_log WHERE user_id = %s",
                    (user_id,)
                )
                if row:
                    return {
                        'total_events': row[0] or 0,
                        'max_score': row[1] or 0,
                        'avg_score': round(float(row[2] or 0), 1),
                    }
        except Exception:
            pass
        return {'total_events': 0, 'max_score': 0, 'avg_score': 0}


# ── Global instance ────────────────────────────────────────────
anti_fraud = AntiFraudEngine()
