"""seed catalog_countries

Revision ID: 005_seed_catalog_countries
Revises: 004_wallet_ledger
Create Date: 2026-06-01

Alembic migration 002 seeded catalog_services but never seeded
catalog_countries, leaving the admin "Catalog → Countries" screen empty.
This migration seeds the canonical country list (idempotent via ON CONFLICT)
so the catalog is complete on a fresh database. The customer buy-flow country
list is driven by data/service_countries.py and is unaffected either way.
"""
from typing import Sequence, Union

from alembic import op

revision: str = '005_seed_catalog_countries'
down_revision: Union[str, None] = '004_wallet_ledger'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_COUNTRIES = [
    ('cyprus', 'Cyprus', 1),
    ('poland', 'Poland', 2),
    ('philippines', 'Philippines', 3),
    ('netherlands', 'Netherlands', 4),
    ('estonia', 'Estonia', 5),
    ('vietnam', 'Vietnam', 6),
    ('georgia', 'Georgia', 7),
    ('cameroon', 'Cameroon', 8),
    ('laos', 'Laos', 9),
    ('benin', 'Benin', 10),
    ('canada', 'Canada', 11),
    ('indonesia', 'Indonesia', 12),
    ('ethiopia', 'Ethiopia', 13),
    ('russia', 'Russia', 14),
    ('paraguay', 'Paraguay', 15),
    ('maldives', 'Maldives', 16),
    ('suriname', 'Suriname', 17),
    ('slovenia', 'Slovenia', 18),
    ('cambodia', 'Cambodia', 19),
    ('dominican_republic', 'Dominican Republic', 20),
]


def upgrade() -> None:
    conn = op.get_bind()
    for code, name, order in _COUNTRIES:
        conn.exec_driver_sql(
            "INSERT INTO catalog_countries (country_code, country_name, is_active, display_order) "
            "VALUES (%s, %s, 1, %s) ON CONFLICT (country_code) DO NOTHING",
            (code, name, order),
        )


def downgrade() -> None:
    op.execute(
        "DELETE FROM catalog_countries WHERE country_code IN ("
        + ",".join("'%s'" % c[0] for c in _COUNTRIES)
        + ")"
    )
