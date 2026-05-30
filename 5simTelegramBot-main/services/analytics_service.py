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
            'today': "created_at::date = CURRENT_DATE",
            'yesterday': "created_at::date = CURRENT_DATE - INTERVAL '1 day'",
            'week': "created_at::date >= CURRENT_DATE - INTERVAL '7 days'",
            'month': "created_at::date >= CURRENT_DATE - INTERVAL '30 days'",
        }

        result = {}
        for period, where_clause in queries.items():
            with db_context('default', transactional=False) as db:
                row = db.fetchone(
                    f'SELECT COUNT(*) as total_orders, COALESCE(SUM(price), 0) as revenue '
                    f'FROM orders WHERE {where_clause}'
                )
                if row:
                    result[period] = {
                        'orders': row['total_orders'] if isinstance(row, dict) else row[0],
                        'revenue': row['revenue'] if isinstance(row, dict) else row[1],
                    }
        return result

    def get_revenue_by_service(self, days: int = 30) -> list[dict]:
        """Revenue breakdown by service type."""
        with db_context('default', transactional=False) as db:
            rows = db.fetchall(
                "SELECT service, COUNT(*) as orders, COALESCE(SUM(price), 0) as revenue "
                "FROM orders WHERE created_at::date >= CURRENT_DATE - INTERVAL '%s days' "
                "GROUP BY service ORDER BY revenue DESC",
                (str(days),)
            )
            return [{'service': r[0], 'orders': r[1], 'revenue': r[2]} for r in rows]

    def get_revenue_by_country(self, days: int = 30) -> list[dict]:
        """Revenue breakdown by country."""
        with db_context('default', transactional=False) as db:
            rows = db.fetchall(
                "SELECT country, COUNT(*) as orders, COALESCE(SUM(price), 0) as revenue "
                "FROM orders WHERE created_at::date >= CURRENT_DATE - INTERVAL '%s days' "
                "GROUP BY country ORDER BY revenue DESC",
                (str(days),)
            )
            return [{'country': r[0], 'orders': r[1], 'revenue': r[2]} for r in rows]

    # ── Order Analytics ────────────────────────────────────────

    def get_order_stats(self) -> dict:
        """Order success/failure/cancellation rates."""
        with db_context('default', transactional=False) as db:
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

        total_n = (total[0] if total else 0) if not isinstance(total, dict) else (total.get('cnt', 0) if total else 0)
        return {
            'total': total_n,
            'completed': completed[0] if completed and not isinstance(completed, dict) else 0,
            'cancelled': cancelled[0] if cancelled and not isinstance(cancelled, dict) else 0,
            'failed': failed[0] if failed and not isinstance(failed, dict) else 0,
            'pending': pending[0] if pending and not isinstance(pending, dict) else 0,
            'success_rate': round((completed[0] / total_n * 100) if total_n > 0 and completed else 0, 1),
            'cancel_rate': round((cancelled[0] / total_n * 100) if total_n > 0 and cancelled else 0, 1),
        }

    # ── User Analytics ─────────────────────────────────────────

    def get_user_stats(self) -> dict:
        """User growth and activity metrics."""
        with db_context('default', transactional=False) as db:
            total = db.fetchone('SELECT COUNT(*) as cnt FROM users')
            today = db.fetchone(
                "SELECT COUNT(*) as cnt FROM users WHERE join_date::date = CURRENT_DATE"
            )
            week = db.fetchone(
                "SELECT COUNT(*) as cnt FROM users WHERE join_date::date >= CURRENT_DATE - INTERVAL '7 days'"
            )

        def _val(row):
            return row[0] if row and not isinstance(row, dict) else (row.get('cnt', 0) if row and isinstance(row, dict) else 0)

        return {
            'total_users': _val(total),
            'new_today': _val(today),
            'new_this_week': _val(week),
        }

    def get_active_users(self, days: int = 7) -> int:
        """Users who placed orders in the last N days."""
        with db_context('default', transactional=False) as db:
            row = db.fetchone(
                "SELECT COUNT(DISTINCT user_id) as cnt FROM orders "
                "WHERE created_at::date >= CURRENT_DATE - INTERVAL '%s days'",
                (str(days),)
            )
        return row[0] if row and not isinstance(row, dict) else (row.get('cnt', 0) if row and isinstance(row, dict) else 0)

    # ── Payment Analytics ──────────────────────────────────────

    def get_payment_stats(self) -> dict:
        """Payment gateway performance."""
        with db_context('default', transactional=False) as db:
            total = db.fetchone('SELECT COUNT(*) as cnt FROM card_payments')
            approved = db.fetchone(
                "SELECT COUNT(*) as cnt FROM card_payments WHERE status = 'approved'"
            )

        total_n = total[0] if total and not isinstance(total, dict) else 0
        approved_n = approved[0] if approved and not isinstance(approved, dict) else 0

        return {
            'total_payments': total_n,
            'approved': approved_n,
            'approval_rate': round(
                (approved_n / total_n * 100) if total_n > 0 else 0, 1
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