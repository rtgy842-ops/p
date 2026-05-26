"""
monitoring/metrics.py — Prometheus Metrics
─────────────────────────────────────────────────
Exposes application metrics for monitoring.
Integrates with Prometheus + Grafana.

Metrics:
- request_count, request_latency
- orders_total, orders_failed
- payments_total, payments_failed
- sms_provider_status
- active_users
- queue_size
- db_connections
- cache_hit_rate
"""

import time
import logging
from functools import wraps
from threading import Lock

logger = logging.getLogger(__name__)


class MetricsRegistry:
    """
    Simple in-process metrics registry.
    Designed to be replaced with prometheus_client later.
    """

    def __init__(self):
        self._counters: dict[str, int] = {}
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = {}
        self._lock = Lock()

    # ── Counter ────────────────────────────────────────────────

    def increment(self, name: str, value: int = 1) -> None:
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + value

    def get_counter(self, name: str) -> int:
        return self._counters.get(name, 0)

    # ── Gauge ──────────────────────────────────────────────────

    def set_gauge(self, name: str, value: float) -> None:
        with self._lock:
            self._gauges[name] = value

    def get_gauge(self, name: str) -> float:
        return self._gauges.get(name, 0.0)

    # ── Histogram ──────────────────────────────────────────────

    def observe(self, name: str, value: float) -> None:
        with self._lock:
            if name not in self._histograms:
                self._histograms[name] = []
            self._histograms[name].append(value)
            # Keep last 1000 observations
            if len(self._histograms[name]) > 1000:
                self._histograms[name] = self._histograms[name][-1000:]

    def get_histogram_stats(self, name: str) -> dict:
        values = self._histograms.get(name, [])
        if not values:
            return {'count': 0, 'avg': 0, 'min': 0, 'max': 0}
        return {
            'count': len(values),
            'avg': sum(values) / len(values),
            'min': min(values),
            'max': max(values),
            'p50': sorted(values)[len(values) // 2] if values else 0,
        }

    # ── All metrics snapshot ───────────────────────────────────

    def get_all(self) -> dict:
        """Return all metrics for /metrics endpoint."""
        with self._lock:
            return {
                'counters': dict(self._counters),
                'gauges': dict(self._gauges),
                'histograms': {
                    name: self.get_histogram_stats(name)
                    for name in self._histograms
                },
            }


# ── Global registry ────────────────────────────────────────────
metrics = MetricsRegistry()


# ── Decorators ─────────────────────────────────────────────────

def track_request(handler_name: str):
    """Decorator to track request count and latency."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            metrics.increment(f'requests:{handler_name}')
            try:
                result = func(*args, **kwargs)
                metrics.increment(f'requests:{handler_name}:success')
                return result
            except Exception:
                metrics.increment(f'requests:{handler_name}:error')
                raise
            finally:
                metrics.observe(f'latency:{handler_name}', time.time() - start)
        return wrapper
    return decorator


# ── Built-in metric trackers ───────────────────────────────────

def track_order_created() -> None:
    metrics.increment('orders:created')

def track_order_completed() -> None:
    metrics.increment('orders:completed')

def track_order_failed() -> None:
    metrics.increment('orders:failed')

def track_payment_verified() -> None:
    metrics.increment('payments:verified')

def track_payment_failed() -> None:
    metrics.increment('payments:failed')

def track_sms_success() -> None:
    metrics.increment('sms:success')

def track_sms_failure() -> None:
    metrics.increment('sms:failure')

def update_active_users(count: int) -> None:
    metrics.set_gauge('users:active', count)

def update_db_connections(count: int) -> None:
    metrics.set_gauge('db:connections', count)

def update_cache_hit_rate(rate: float) -> None:
    metrics.set_gauge('cache:hit_rate', rate)