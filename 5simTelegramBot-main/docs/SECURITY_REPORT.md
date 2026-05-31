# SECURITY REPORT — NumGenius Enterprise SaaS
## Phase I: Security Audit

**Date:** 2026-05-31
**Status:** NEEDS REMEDIATION

---

## EXECUTIVE SUMMARY

| Risk Level | Count |
|------------|-------|
| CRITICAL | 3 |
| HIGH     | 4 |
| MEDIUM   | 6 |
| LOW      | 5 |

---

## CRITICAL FINDINGS

### S1 — Hardcoded Secrets in Version Control

**Severity:** CRITICAL
**Finding:** The config file previously contained hardcoded secrets. While [`config.py`](5simTelegramBot-main/config.py) now uses `_env()` from environment variables, the following concerns exist:

1. **Startup script uses hardcoded path:** [`startup_test.py:4`](5simTelegramBot-main/startup_test.py:4) — `os.chdir(r'c:\Users\MC\Downloads\...)` exposes a developer username
2. **Test file checks for old secrets:** [`test_enterprise_services.py:313-319`](5simTelegramBot-main/tests/test_enterprise_services.py:313) — verifies old tokens are NOT present, but the test file itself documents them

**Risk:** If secrets were ever committed to git history, they remain accessible even after removal from current files.

**Fix:** Run `git filter-branch` or `bfg-repo-cleaner` to purge secrets from git history. Rotate all exposed credentials.

---

### S2 — Missing Webhook Secret Verification

**Severity:** CRITICAL
**File:** [`web/routes/webhook.py:23-37`](5simTelegramBot-main/web/routes/webhook.py:23)
**Finding:** The Telegram webhook endpoint has zero authentication:
- No `X-Telegram-Bot-Api-Secret-Token` header verification
- Accepts GET requests (should be POST only)
- Returns `'OK'` on GET (information disclosure — confirms bot is live)
- Processes ANY JSON payload as a Telegram Update

**Attack Vector:** An attacker who discovers the webhook URL can:
- Send forged update payloads to trigger handlers
- Cause the bot to send messages to users (if handler code references `call.from_user.id`)
- Denial of service via malformed JSON

**Fix:**
1. Change route to `methods=['POST']` only
2. Add secret token verification
3. Configure webhook with `secret_token` parameter

---

### S3 — Payment Callback CSRF

**Severity:** CRITICAL
**Finding:** The ZarinPal callback endpoint at `/verify/<user_id>/<amount>` has no CSRF protection:
- No state/nonce token verification
- No origin validation
- Relies solely on `Authority` and `Status` query parameters which come from the payment gateway redirect
- A malicious actor could attempt to replay a valid Authority value

**Risk:** Medium-low in practice (Authority is single-use per ZarinPal), but the endpoint should still implement state verification.

**Fix:** Add a `state` parameter stored in the user's session before redirecting to ZarinPal. Verify `state` on callback.

---

## HIGH FINDINGS

### S4 — Insecure `SECRET_KEY` Default

**Severity:** HIGH
**File:** [`config.py:79`](5simTelegramBot-main/config.py:79)
**Finding:** `SECRET_KEY = os.getenv('SECRET_KEY', os.urandom(32).hex())` — When no env var is set:
- Every process restart generates a new key
- Flask sessions become invalid
- Session-based admin auth breaks
- Multiple Gunicorn workers each get different keys

**Fix:** Make `SECRET_KEY` a required env var. Raise on missing in production.

---

### S5 — SQL Injection Risk in Migration Manager

**Severity:** HIGH
**File:** [`db/migrations.py:17-18`](5simTelegramBot-main/db/migrations.py:17)
**Finding:** Settings seeding uses Python f-string interpolation:
```python
f"INSERT INTO settings (key, value) VALUES ('{k}', '{v}') ON CONFLICT (key) DO NOTHING"
```
If any setting key or value from `DEFAULT_SETTINGS` contains a single quote, this produces invalid SQL. While the current values are hardcoded and safe, the pattern is dangerous.

**Fix:** Use parameterized queries:
```python
"INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING", (k, v)
```

---

### S6 — Admin API Token Exposure in Chat

**Severity:** HIGH
**File:** [`bot/handlers/admin_bot.py:869`](5simTelegramBot-main/bot/handlers/admin_bot.py:869)
**Finding:** The `admin:web_panel` callback displays the admin API token in plain text:
```python
panel_url = f"{webhook_url}/admin?token={token}"
# ...
f"🔗 `{panel_url}`"
```
Anyone who can see the admin's Telegram chat (including Telegram itself, any forward recipients, or screenshot viewers) can access the admin panel.

**Fix:** Send the token in a separate, auto-deleting message, or use a one-time token system.

---

### S7 — No Rate Limiting on Customer Bot Handlers

**Severity:** HIGH
**Finding:** While [`services/rate_limiter.py`](5simTelegramBot-main/services/rate_limiter.py) exists with a comprehensive token-bucket implementation and Flask decorator, it is **not integrated** into any customer bot handler or webhook route. The `rate_limit` decorator is defined but never applied.

**Risk:** Brute-force attacks on SMS code checking, purchase attempts, payment callbacks.

**Fix:** Apply `@rate_limit('purchase')` to purchase handlers, `@rate_limit('verify')` to payment callbacks, `@rate_limit('default')` to the webhook endpoint.

---

## MEDIUM FINDINGS

### S8 — Bare Except Clauses (6 instances)

**Severity:** MEDIUM
**Files:** [`bot/handlers/admin/channels.py:33`](5simTelegramBot-main/bot/handlers/admin/channels.py:33), [`db/context.py:75`](5simTelegramBot-main/db/context.py:75), [`db/migrations.py:107`](5simTelegramBot-main/db/migrations.py:107)

Bare `except:` clauses catch `KeyboardInterrupt`, `SystemExit`, and other system exceptions. These should never be silently suppressed.

---

### S9 — Information Disclosure via `startup_test.py`

**Severity:** MEDIUM
**File:** [`startup_test.py`](5simTelegramBot-main/startup_test.py)
**Finding:** Contains absolute path revealing developer username `MC`. If committed, this is in git history.

---

### S10 — API Key Service Is In-Memory Only

**Severity:** MEDIUM
**File:** [`services/api_key_service.py`](5simTelegramBot-main/services/api_key_service.py)
**Finding:** API keys stored in Python dict — lost on restart. Hash is SHA-256 (acceptable), but keys can't be revoked persistently.

---

### S11 — No Input Sanitization on Admin Search

**Severity:** MEDIUM
**File:** [`bot/handlers/admin_bot.py:165`](5simTelegramBot-main/bot/handlers/admin_bot.py:165)
**Finding:** `int(message.text.strip())` — if the message text is extremely large, this could cause memory issues. No length validation before conversion.

---

### S12 — Database Connection String in Environment

**Severity:** MEDIUM
**Finding:** `DATABASE_URL` contains credentials. While using env vars is correct, the connection string is not encrypted at rest in `.env`. Docker secrets or a vault should be used in production.

---

### S13 — No CSP/XSS Headers on Web Templates

**Severity:** MEDIUM
**Finding:** Flask templates (`payment_result.html`, `admin/dashboard.html`, etc.) don't set Content-Security-Policy headers. While templates use Jinja2 auto-escaping (safe), CSP provides defense-in-depth.

---

## LOW FINDINGS

### S14 — No Helmet/Security Headers
Missing: X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Strict-Transport-Security.

### S15 — Debug Mode Configurable via Env
`FLASK_DEBUG` env var could expose stack traces if accidentally set to `true` in production.

### S16 — Gunicorn Not Configured in Docker CMD
`docker-compose.yml` uses `python bot.py` directly — no Gunicorn with multiple workers for production resilience.

### S17 — Redis Without Authentication
`docker-compose.yml` starts Redis without `requirepass`. The internal network provides some isolation, but defense-in-depth would add auth.

### S18 — PostgreSQL Default Credentials
`docker-compose.yml:20-21` uses default credentials `smsbot:MyS3cur3Pssw0r`. While overridable via env vars, the default password is weak.

---

## POSITIVE SECURITY FINDINGS

1. ✓ **All secrets from environment** — `config.py` uses `_env()` with no hardcoded defaults for secrets
2. ✓ **Parameterized queries** — All repositories use `%s` placeholders (except migration manager)
3. ✓ **Row-level locking** — `SELECT ... FOR UPDATE` prevents race conditions on balance
4. ✓ **Idempotent payments** — Double-check prevents double-crediting
5. ✓ **RBAC with 6 roles** — Granular permission system for admin operations
6. ✓ **Audit trail** — All admin actions logged to `audit_log` table
7. ✓ **Anti-fraud engine** — Multi-layer detection with velocity, IP, fingerprint checks
8. ✓ **Rate limiter exists** — PostgreSQL-backed token bucket (needs integration)
9. ✓ **Non-root Docker user** — `Dockerfile:17` creates `botuser`
10. ✓ **No SQLite in production** — All paths use PostgreSQL with psycopg2

---

## OVERALL VERDICT

**NEEDS REMEDIATION** — 3 CRITICAL issues (webhook auth, payment CSRF, git history secrets), 4 HIGH issues (SECRET_KEY default, SQL injection pattern, token exposure, missing rate limit integration).

The security architecture is sound (RBAC, audit, anti-fraud, row locking, parameterized queries), but implementation gaps exist in webhook authentication and rate limiting.

**Blocking for production:** Fix S1 (secret rotation), S2 (webhook verification), S3 (payment CSRF), S7 (rate limiter integration).
