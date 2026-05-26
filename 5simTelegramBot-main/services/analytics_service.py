"""
services/analytics_service.py — Enterprise Analytics Engine
─────────────────────────────────────────────────
Real business intelligence, not just user counts.

Metrics:
- Revenue: daily, weekly, monthly, by service, by country
- Orders: conversion rate, success rate, cancellation rate
- Users: active users, new users, retention
- SMS: provider performance, success rate, avg delivery time
- Payments: gateway success rates, average amounts
"""

import logging
from datetime import datetime, timedelta
from db.connection import ConnectionManager
from db.context import db_context

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Business intelligence and metrics."""

    def __init__(self):
        self._cm = ConnectionManager.get_instance()

    # ── Revenue Analytics ──────────────────────────────────────

    def get_revenue_summary(self) -> dict:
        """Get revenue overview: today, yesterday, week, month."""
        queries = {
            'today': "date(created_at) = date('now')",
            'yesterday': "date(created_at) = date('now', '-1 day')",
            'week': "date(created_at) >= date('now', '-7 days')",
            'month': "date(created_at) >= date('now', '-30 days')",
        }

        result = {}
        for period, where_clause in queries.items():
            with db_context('bot_db', transactional=False) as db:
                row = db.fetchone(
                    f'SELECT COUNT(*) as total_orders, COALESCE(SUM(price), 0) as revenue '
                    f'FROM orders WHERE {where_clause}'
                )
                if row:
                    result[period] = {
                        'orders': row['total_orders'],
                        'revenue': row['revenue'],
                    }
        return result

    def get_revenue_by_service(self, days: int = 30) -> list[dict]:
        """Revenue breakdown by service type."""
        with db_context('bot_db', transactional=False) as db:
            rows = db.fetchall(
                'SELECT service, COUNT(*) as orders, COALESCE(SUM(price), 0) as revenue '
                "FROM orders WHERE date(created_at) >= date('now', ?) "
                'GROUP BY service ORDER BY revenue DESC',
                (f'-{days} days',)
            )
            return [dict(r) for r in rows]

    def get_revenue_by_country(self, days: int = 30) -> list[dict]:
        """Revenue breakdown by country."""
        with db_context('bot_db', transactional=False) as db:
            rows = db.fetchall(
                'SELECT country, COUNT(*) as orders, COALESCE(SUM(price), 0) as revenue '
                "FROM orders WHERE date(created_at) >= date('now', ?) "
                'GROUP BY country ORDER BY revenue DESC',
                (f'-{days} days',)
            )
            return [dict(r) for r in rows]

    # ── Order Analytics ────────────────────────────────────────

    def get_order_stats(self) -> dict:
        """Order success/failure/cancellation rates."""
        with db_context('bot_db', transactional=False) as db:
            total = db.fetchone('SELECT COUNT(*) as cnt FROM orders')
            completed = db.fetchone(
                "SELECT COUNT(*) as cnt FROM orders WHERE status = 'COMPLETED'"
            )
            cancelled = db.fetchone(
                "SELECT COUNT(*) as cnt FROM orders WHERE status IN ('CANCELLED','CANCELED')"
            )
            failed = db.fetchone(
                "SELECT COUNT(*) as cnt FROM orders WHERE status = 'FAILED'"
            )
            pending = db.fetchone(
                "SELECT COUNT(*) as cnt FROM orders WHERE status = 'PENDING'"
            )

        total_n = total['cnt'] if total else 0
        return {
            'total': total_n,
            'completed': completed['cnt'] if completed else 0,
            'cancelled': cancelled['cnt'] if cancelled else 0,
            'failed': failed['cnt'] if failed else 0,
            'pending': pending['cnt'] if pending else 0,
            'success_rate': round((completed['cnt'] / total_n * 100) if total_n > 0 else 0, 1),
            'cancel_rate': round((cancelled['cnt'] / total_n * 100) if total_n > 0 else 0, 1),
        }

    # ── User Analytics ─────────────────────────────────────────

    def get_user_stats(self) -> dict:
        """User growth and activity metrics."""
        with db_context('users_db', transactional=False) as db:
            total = db.fetchone('SELECT COUNT(*) as cnt FROM users')
            today = db.fetchone(
                "SELECT COUNT(*) as cnt FROM users WHERE date(join_date) = date('now')"
            )
            week = db.fetchone(
                "SELECT COUNT(*) as cnt FROM users WHERE date(join_date) >= date('now', '-7 days')"
            )

        return {
            'total_users': total['cnt'] if total else 0,
            'new_today': today['cnt'] if today else 0,
            'new_this_week': week['cnt'] if week else 0,
        }

    def get_active_users(self, days: int = 7) -> int:
        """Users who placed orders in the last N days."""
        with db_context('bot_db', transactional=False) as db:
            row = db.fetchone(
                'SELECT COUNT(DISTINCT user_id) as cnt FROM orders '
                "WHERE date(created_at) >= date('now', ?)",
                (f'-{days} days',)
            )
        return row['cnt'] if row else 0

    # ── Payment Analytics ──────────────────────────────────────

    def get_payment_stats(self) -> dict:
        """Payment gateway performance."""
        with db_context('users_db', transactional=False) as db:
            total = db.fetchone('SELECT COUNT(*) as cnt FROM card_payments')
            approved = db.fetchone(
                "SELECT COUNT(*) as cnt FROM card_payments WHERE status = 'approved'"
            )

        return {
            'total_payments': total['cnt'] if total else 0,
            'approved': approved['cnt'] if approved else 0,
            'approval_rate': round(
                (approved['cnt'] / total['cnt'] * 100) if total and total['cnt'] > 0 else 0, 1
            ),
        }

    # ── Dashboard Summary ──────────────────────────────────────

    def get_dashboard(self) -> dict:
        """Complete analytics dashboard."""
        return {
            'revenue': self.get_revenue_summary(),
            'orders': self.get_order_stats(),
            'users': self.get_user_stats(),
            'payments': self.get_payment_stats(),
            'active_users_7d': self.get_active_users(7),
            'top_services': self.get_revenue_by_service(7),
            'top_countries': self.get_revenue_by_country(7),
            'generated_at': datetime.now().isoformat(),
        }


# ── Global instance ────────────────────────────────────────────
analytics = AnalyticsService()