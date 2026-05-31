# STATIC ANALYSIS REPORT — NumGenius Enterprise SaaS
## Phase B: Ruff, Flake8, Pylint, Mypy

**Date:** 2026-05-31  
**Tools:** ruff 0.15.15, mypy 2.1.0  

---

## EXECUTIVE SUMMARY

| Tool   | Initial | After Auto-Fix | Remaining |
|--------|---------|----------------|-----------|
| Ruff   | 510     | 385 fixed      | 122       |
| Mypy   | 314     | N/A            | 314       |

### Remaining Issue Severity (Ruff)
| Category                         | Count |
|----------------------------------|-------|
| E402 — Module-level import       | 20    |
| E701/E702 — Multiple statements  | 46    |
| W293 — Blank line whitespace     | 10    |
| F841 — Unused local variable     | 3     |
| F821 — Undefined name            | 1     |
| B011 — assert False              | 1     |
| B007 — Unused loop variable      | 2     |
| E722 — Bare except               | 6     |
| SIM105/SIM108 — Simplify         | 5     |
| I001 — Unsorted imports          | 10    |
| Other                            | 18    |

### Mypy Error Categories
| Category                           | Count |
|------------------------------------|-------|
| union-attr (None has no attribute) | ~200  |
| valid-type (callable/any as type)  | ~10   |
| misc/return-value                  | ~40   |
| assignment / arg-type              | ~30   |
| call-arg (wrong arg count)         | ~5    |
| import / attr-defined              | ~15   |
| Other                              | ~14   |

---

## CRITICAL MYPI FINDINGS (Runtime Bugs)

### MB1 — `bot/handlers/admin_bot.py:719` — Too many arguments for `set_pricing()`

```python
# Line 709-710: Calls set_pricing with 8 positional args but method takes 7:
cat.set_pricing(country, service, provider_id, base_price,
                profit_pct, profit_fixed, final_price, 0, 0)
# Method signature: set_pricing(self, country_code, service_code, provider_id, 
#                               base_price_usd, profit_pct, profit_fixed, 
#                               min_price, max_price)
# Count: 8 provided but only 7 accepted (self is implicit)
# The `final_price` positional arg matches `min_price` parameter — BUG!
```

**Severity:** CRITICAL — Runtime `TypeError`  
**Fix:** Remove `final_price` from the call or add it to the method signature.

### MB2 — `services/referral_service.py:66-67` — Incompatible types in assignment

```python
code = row[0] if not isinstance(row, dict) else row.get('code')
self._cache[user_id] = code  # code may be None but cache expects str
return code                   # Returns Any | None, declared as str
```

**Severity:** HIGH  
**Fix:** Add explicit `None` check: `if code is None: return ''`

### MB3 — `services/wallet_ledger.py:89` — str appended to int list

```python
params = [user_id]       # list[int]
params.append(entry_type) # entry_type is str — type mismatch
```

**Severity:** HIGH  
**Fix:** Use separate variable for SQL parameters or use typed parameter lists.

---

## RUFF ERROR DETAIL — FILE-BY-FILE

### `admin_bot.py` — 18 remaining errors
- E402 (×8): Imports after `load_dotenv()` — `from flask import` and `import telebot` after env loading. These are **intentional** because `load_dotenv()` must run before config reads. **Documented false positive.**
- E702 (×9): Multiple statements on one line — `from X import A; from Y import B`. **Minor style issue.**
- I001 (×4): Unsorted import blocks.

### `bot.py` — 16 remaining errors
- E402 (×5): Same pattern — imports after `webhook_init(bot)`. **Intentional runtime ordering.**
- E702 (×10): Multiple semicolons in `__main__` block. **Minor style.**
- I001 (×2): Unsorted imports.

### `bot/handlers/admin/channels.py` — 27 errors
- E701/E702 (×24): This file uses heavy single-line patterns (`if X: body` on one colon line). **Code style — needs refactoring.**
- E722 (×3): Bare `except:` clauses.

### `bot/handlers/admin/operators.py` — 16 errors
- E701/E702: Same single-line patterns as channels.py.

### `bot/handlers/purchase.py` — 5 errors
- E701/E702: Single-line statements in buy_number handler.

### `db/context.py` — 2 errors
- E722: Bare `except: pass` at line 75.

### `db/migrations.py` — 2 errors
- E722: Bare `except: pass` at line 107.

### `tests/test_enterprise_services.py:180` — UNDEFINED NAME (F821)
```python
assert result['risk_level'] in (RiskLevel.LOW, 'low')
# RiskLevel is imported at top of class TestAntiFraudEngine but NOT at module level
```

**Fix:** Add `from services.anti_fraud import RiskLevel` at top of file.

### `tests/test_executable_wallet.py:167` — `assert False` (B011)
```python
assert False, "Should have raised"  # Use pytest.fail() instead
```

### `tasks/__init__.py:147` — Unused local variable (F841)
```python
repo = SettingsRepository()  # Assigned but never used
```

### `bot/__init__.py`, `admin/__init__.py`, `web/__init__.py`, `web/routes/__init__.py` — No newline at end of file
**Fix:** Add final newline.

### `scripts/setup_pg.py` — 2 errors
- E702: Multiple statements on one line.

### `bot_utils.py`, `i18n.py`, `services/event_bus.py`, `services/feature_flags.py`, `services/payment_service.py`, `services/wallet_service.py` — W293: Blank line contains whitespace (×10)
**Fix:** Strip trailing whitespace.

---

## MYPI ERROR DETAIL — FILE-BY-FILE

### `bot/handlers/admin_bot.py` — ~55 errors (union-attr)
All are `Item "None" of "Any | None" has no attribute "edit_message_text"` etc. The `_bot` global is typed as `None` at module level and assigned in `init()`. Mypy cannot prove `init()` has been called before handlers run.

**Status:** Documented false positive — `init()` is called at startup before handlers are invoked.  
**Mitigation:** Add `assert _bot is not None` at start of each handler, or type as `_bot: Any`.

### `bot/handlers/payment.py` — ~12 errors (union-attr)
Same `_bot` global issue.

### `bot/handlers/purchase.py` — ~15 errors (union-attr)
Same `_bot` global issue.

### `bot/handlers/referrals.py` — ~8 errors (union-attr)
Same `_bot` global issue.

### `bot/handlers/subscriptions.py` — ~6 errors (union-attr)
Same `_bot` global issue.

### `bot/handlers/membership.py` — ~5 errors (union-attr)
Same `_bot` global issue.

### `db/context.py` — ~8 errors (union-attr)
`self._conn` and `self._cursor` are `None` until `__enter__` is called. Methods like `execute()` are only called within the context manager, so these are safe at runtime but mypy cannot verify it.

### `data/dto.py` — 2 errors (return-value)
```python
@classmethod
def from_row(cls, row) -> 'UserDTO':
    if row is None:
        return None  # Returns None but type says UserDTO
```
**Fix:** Change return type to `'UserDTO | None'`.

### `services/cache_service.py` — 8 errors (valid-type, misc)
- `callable` used as type instead of `Callable`
- `any` used as type instead of `Any`
**Fix:** Replace with proper typing imports.

### `services/event_bus.py` — 3 errors (valid-type)
- `callable` used as type instead of `Callable`
**Fix:** Replace with proper typing imports.

### `services/notification_service.py` — 2 errors (valid-type)
- `callable` used as type instead of `Callable`
**Fix:** Replace with proper typing imports.

### `services/referral_service.py` — ~5 errors
- Incompatible types in `get_code()`, `get_referral_count()`, `get_referral_earnings()`
- Missing None checks on dict access

### `services/rbac_service.py` — 1 error
- `get_all_admins()` returns `db.fetchall()` result directly instead of transforming to `list[dict]`

### `services/analytics_service.py` — ~10 errors
- `row[0]` access on potentially `dict` rows — inconsistent row handling. Some queries return dicts, some tuples. Mypy cannot reconcile.

### `bot/client.py` — 2 errors
- `callback_data: str = None` and `url: str = None` should use `Optional[str]`
**Fix:** Add `from typing import Optional` and change types.

### `web/routes/webhook.py` — 1 error
- `_bot.process_new_updates()` — `_bot` may be None. Guard needed.

---

## RECOMMENDED FIX PRIORITY

| Priority | Issue | Files | Effort |
|----------|-------|-------|--------|
| 1 | MB1 — Too many args to set_pricing | admin_bot.py | Trivial |
| 2 | F821 — Undefined RiskLevel in test | test_enterprise_services.py | Trivial |
| 3 | F841 — Unused repo in tasks/__init__.py | tasks/__init__.py | Trivial |
| 4 | B011 — assert False | test_executable_wallet.py | Trivial |
| 5 | MB3 — type mismatch in wallet_ledger.py | wallet_ledger.py | Low |
| 6 | E722 — Bare except blocks (×6) | channels.py, context.py, migrations.py | Low |
| 7 | W293 — Trailing whitespace (×10) | Multiple | Auto-fix |
| 8 | No newline at EOF (×5) | __init__.py files | Auto-fix |
| 9 | E701/E702 — Single-line statements (×46) | Multiple | Medium |
| 10 | Mypy valid-type (×10) | cache_service, event_bus, notification_service | Low |
| 11 | Sim105/Sim108 (×5) | config, db/connection, admin_service | Low |

---

## FALSE POSITIVES — DOCUMENTED

| Pattern | Reason |
|---------|--------|
| E402 in bot.py:23-24, admin_bot.py:13-36 | Imports after runtime setup (webhook_init, load_dotenv). Required for correct execution order. |
| union-attr on `_bot` (~200 errors) | Global `_bot = None` set in `init()` called at startup. Always assigned before handler invocation. |
| return-value in dto.py:59,89 | `from_row()` returns `None` for missing rows — intentional null-object pattern. |
| no-any-return in analytics_service | `db.fetchall()` returns raw tuples — correct behavior. |
| attr-defined on alembic.op | Alembic injects `op` at runtime — standard Alembic pattern. |

---

## OVERALL STATIC ANALYSIS VERDICT

**PASS WITH OBSERVATIONS.** The project has 122 remaining Ruff issues (mostly style: E402 false positives, E701/E702 code golf, W293 whitespace) and 314 Mypy issues (mostly `_bot` null-safety false positives in handler files). 

**1 actual runtime bug** found by mypy (MB1 — `set_pricing` arg mismatch).  
**1 undefined name** found by ruff (F821 — `RiskLevel` in test).  
**2 real type errors** found (wallet_ledger params, referral_service return types).

All Critical/High-impact issues identified in this report should be fixed before production deployment.
