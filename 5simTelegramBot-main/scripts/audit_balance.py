#!/usr/bin/env python3
"""
scripts/audit_balance.py — Balance Consistency Audit
──────────────────────────────────────────────────────
Compares legacy balance reads against new WalletService balances
for ALL users. Used during Phase A migration to verify dual-write
integrity.

Usage:
    python scripts/audit_balance.py          # Show discrepancies only
    python scripts/audit_balance.py --all    # Show all balances
    python scripts/audit_balance.py --fix    # Fix legacy from new
    python scripts/audit_balance.py --user 123456  # Check single user

Exit code 0 = all balances match, 1 = discrepancies found.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def audit_all(show_all: bool = False, fix: bool = False) -> tuple[int, int]:
    """Audit all users. Returns (total, discrepancies)."""
    from compat.legacy_facade import get_balance as new_get_balance
    from database import get_user_balance as legacy_get_balance
    from db.repositories.user_repository import UserRepository

    repo = UserRepository()
    all_users = repo.get_all_ids()
    total = len(all_users)
    discrepancies = 0

    print(f"\n{'='*60}")
    print(f"  Balance Audit — {total} users")
    print(f"{'='*60}")

    for row in all_users:
        user_id = row['user_id']
        legacy_balance = legacy_get_balance(user_id)
        new_balance = new_get_balance(user_id)

        if legacy_balance != new_balance:
            discrepancies += 1
            print(f"  ❌ MISMATCH: user={user_id}, legacy={legacy_balance}, new={new_balance}")
            if fix:
                # Fix legacy from new
                import sqlite3

                from config import DB_CONFIG
                conn = sqlite3.connect(DB_CONFIG['users_db'])
                conn.execute('UPDATE users SET balance = ? WHERE user_id = ?', (new_balance, user_id))
                conn.commit()
                conn.close()
                print(f"     → Fixed: legacy now = {new_balance}")
        elif show_all:
            print(f"  ✅ user={user_id}, balance={legacy_balance}")

    print(f"{'='*60}")
    print(f"  Results: {discrepancies}/{total} discrepancies")
    if discrepancies == 0:
        print("  ✅ ALL BALANCES MATCH — Migration consistent")
    else:
        print(f"  ⚠️  {discrepancies} mismatches detected!")
    print(f"{'='*60}\n")

    return total, discrepancies


def audit_single(user_id: int):
    """Audit a single user."""
    from compat.legacy_facade import get_balance as new_get_balance
    from database import get_user_balance as legacy_get_balance

    legacy = legacy_get_balance(user_id)
    new = new_get_balance(user_id)

    print(f"\n  User: {user_id}")
    print(f"  Legacy balance:  {legacy:,} Toman")
    print(f"  New balance:     {new:,} Toman")
    if legacy == new:
        print("  Status: ✅ MATCH")
    else:
        print(f"  Status: ❌ MISMATCH (diff={new - legacy})")
    print()


if __name__ == '__main__':
    args = sys.argv[1:]

    if '--user' in args:
        idx = args.index('--user')
        if idx + 1 < len(args):
            audit_single(int(args[idx + 1]))
            sys.exit(0)

    show_all = '--all' in args
    fix = '--fix' in args

    total, disc = audit_all(show_all=show_all, fix=fix)
    sys.exit(1 if disc > 0 else 0)
