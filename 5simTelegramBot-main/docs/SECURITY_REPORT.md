# SECURITY AUDIT REPORT — NumGenius Enterprise SaaS
## Phase I: Full Security Review

**Date:** 2026-05-31
**Auditor:** Security Auditor
**Scope:** All source code, Docker config, nginx config, environment handling

---

## 1. EXECUTIVE SUMMARY

| Severity | Count |
|----------|-------|
| CRITICAL | 4 |
| HIGH | 7 |
| MEDIUM | 8 |
| LOW | 5 |
| **TOTAL** | **24** |

**Overall Security Posture:** NEEDS IMPROVEMENT — 4 CRITICAL issues must be resolved before production. The codebase shows good security intent (webhook tokens, CSRF protection, idempotency checks, audit logging) but has dangerous implementation gaps.

---

## 2. CRITICAL FINDINGS

### S-1: Admin API Token Exposed in URL Query String
- **Severity:** CRITICAL
- **Category:** Authentication — Token Leakage
- **Files:**
  - [`admin_bot.py:46-47`](admin_bot.py:46-47) — Generates link with token in query param
  - [`web/routes/admin_panel.py`](web/routes/admin_panel.py) — Reads token from `request.args.get('token')`
- **Root Cause:** `f'<a href="{w}/admin?token={t}">🔗 Admin Panel</a>'` embeds the admin API token directly in the URL.
- **Attack Vector:**
  1. Proxy/nginx/server access logs capture the full URL including `?token=...`
  2. Browser history stores the token
  3. Referer headers leak the token to third-party sites
  4. Anyone with log access gains admin panel access
- **Recommended Fix:**
  - Use HTTP `Authorization: Bearer <token>` header
  - Create a login page that POSTs the token
  - Use session cookies after authentication

### S-2: Webhook Secret Token Bypass in Production
- **Severity:** CRITICAL
- **Category:** Authentication — Missing Enforcement
- **File:** [`web/routes/webhook.py:32-37`](web/routes/webhook.py:32-37)
- **Root Cause:**
```python
def _verify_webhook_token() -> bool:
    token = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
    if not _WEBHOOK_SECRET_TOKEN:
        return True  # If not configured, allow all ← THIS IS DANGEROUS
    return token == _WEBHOOK_SECRET_TOKEN
```
- **Attack Vector:** If `WEBHOOK_SECRET_TOKEN` is not set in production `.env`, anyone can POST fake Telegram updates to the webhook endpoint.
- **Impact:** Attackers can:
  - Trigger purchases on behalf of users (callback_query forgery)
  - Exfiltrate user data through bot responses
  - Send spam through the bot
- **Recommended Fix:**
```python
def _verify_webhook_token() -> bool:
    token = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
    if not _WEBHOOK_SECRET_TOKEN:
        if IS_PRODUCTION:
            return False  # FAIL CLOSED
        return True  # Dev only
    import secrets
    return secrets.compare_digest(token, _WEBHOOK_SECRET_TOKEN)
```
Note: Also use `secrets.compare_digest()` for timing-attack-safe comparison.

### S-3: SECRET_KEY Auto-Generated on Every Restart
- **Severity:** CRITICAL
- **Category:** Cryptography — Non-Deterministic Key
- **File:** [`config.py:80`](config.py:80)
- **Root Cause:** `SECRET_KEY = os.getenv('SECRET_KEY', os.urandom(32).hex())`
- **Impact:**
  - All Flask sessions invalidated on restart
  - CSRF tokens broken
  - If SECRET_KEY is used for signing anything persistent, signatures are unverifiable after restart
- **Recommended Fix:** Remove the fallback. Make SECRET_KEY mandatory:
```python
SECRET_KEY = _env('SECRET_KEY')  # Use validator that raises if missing
```

### S-4: POSTGRES_PASSWORD Has Hardcoded Default in Docker Compose
- **Severity:** CRITICAL
- **Category:** Hardcoded Credentials
- **File:** [`docker-compose.yml:20`](docker-compose.yml:20)
- **Root Cause:** `${POSTGRES_PASSWORD:-MyS3cur3Pssw0r}`
- **Impact:** If `POSTGRES_PASSWORD` is not set in `.env`, the database runs with a publicly known default password. The database is accessible from any container on the `internal` Docker network.
- **Recommended Fix:** Remove the default. Make it mandatory:
```yaml
environment:
  POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set}
```

---

## 3. HIGH FINDINGS

### S-5: No Redis Authentication
- **Severity:** HIGH
- **Category:** Infrastructure Security
- **File:** [`docker-compose.yml:39-41`](docker-compose.yml:39-41)
- **Root Cause:** Redis runs without `requirepass`.
- **Impact:** Any container on the internal network can read/write/delete Redis data. Cache poisoning. Celery task manipulation.
- **Recommended Fix:** Add `--requirepass ${REDIS_PASSWORD}` and configure Celery and apps with the password.

### S-6: No Input Validation on Admin Balance Operations
- **Severity:** HIGH
- **Category:** Input Validation
- **File:** [`bot/handlers/admin_bot.py:202-218`](bot/handlers/admin_bot.py:202-218), lines 230-246
- **Root Cause:** No upper bound on balance additions/deductions. An admin could accidentally add billions.
- **Impact:** Financial manipulation. No audit trail visibility on large transactions without checking logs.
- **Recommended Fix:** Add `MAX_BALANCE_CHANGE = 100_000_000` and validate.

### S-7: No Rate Limiting on Admin Endpoints
- **Severity:** HIGH
- **Category:** Abuse Prevention
- **File:** [`bot/handlers/admin_bot.py`](bot/handlers/admin_bot.py) (entire file)
- **Root Cause:** Rate limiter exists in `services/rate_limiter.py` but is never applied to admin handlers.
- **Impact:** Brute-force user ID enumeration. Rapid balance changes. No brute-force protection.
- **Recommended Fix:** Apply `RateLimiter.is_allowed()` checks on search, balance add/deduct, ban operations.

### S-8: Payment CSRF State Token Not Reaching Callback
- **Severity:** HIGH
- **Category:** CSRF
- **File:** [`bot/handlers/payment.py:56-66`](bot/handlers/payment.py:56-66)
- **Root Cause:** State token is generated but NOT appended to the ZarinPal callback URL. The `/verify` endpoint receives `state=''` (empty string), which will NEVER match any stored state.
- **Impact:** ALL ZarinPal payment callbacks will fail CSRF validation. Users will see "Invalid or expired session" errors after paying.
- **Recommended Fix:** Pass state token to `payment_create_zarinpal()` and include it in the ZarinPal request's `callback_url` parameter.

### S-9: In-Memory Payment State Store Lost on Restart
- **Severity:** HIGH
- **Category:** Data Integrity
- **File:** [`bot.py:47`](bot.py:47)
- **Root Cause:** `_payment_states: dict[str, dict] = {}` — in-memory only.
- **Impact:** If bot restarts while users have active payment sessions, all CSRF state tokens are lost. Users must restart payment flow.
- **Recommended Fix:** Use Redis with 30-minute TTL for payment states.

### S-10: Broadcaster Sends to All Users Without Rate Limiting
- **Severity:** HIGH
- **Category:** Abuse Prevention
- **File:** [`bot/handlers/admin_bot.py:547-566`](bot/handlers/admin_bot.py:547-566)
- **Root Cause:** Sequential `send_message()` loop with no delay. Telegram rate limit: ~30/sec.
- **Impact:** Messages beyond rate limit fail silently. Could trigger Telegram anti-spam detection.
- **Recommended Fix:** Use Celery task with 0.05s delay between messages. Track successes/failures.

### S-11: Audit Log Only in Database — Can Be Deleted
- **Severity:** HIGH
- **Category:** Audit Trail Integrity
- **File:** [`services/admin_service.py:30-37`](services/admin_service.py:30-37), [`services/audit_service.py`](services/audit_service.py)
- **Root Cause:** All audit entries go to `audit_log` table only. A compromised database admin could delete audit records.
- **Impact:** No tamper-evident audit trail.
- **Recommended Fix:** Write critical audit events to append-only file with hash chaining (blockchain-style). Or use a separate audit database with INSERT-only permissions.

---

## 4. MEDIUM FINDINGS

### S-12: No HTTPS Enforcement in Flask
- **Severity:** MEDIUM
- **Category:** Transport Security
- **Files:** [`bot.py`](bot.py:109), [`admin_bot.py`](admin_bot.py:60)
- **Root Cause:** `app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)` — Flask runs HTTP only. nginx provides HTTPS termination externally.
- **Impact:** If nginx is misconfigured or bypassed, traffic is unencrypted.
- **Recommended Fix:** Document the nginx dependency for HTTPS. Add HSTS headers in nginx.

### S-13: No Content Security Policy Headers
- **Severity:** MEDIUM
- **Category:** Web Security
- **Files:** All Flask routes
- **Root Cause:** No CSP, X-Frame-Options, X-Content-Type-Options headers set.
- **Impact:** Clickjacking risk on admin panel. MIME sniffing risk.
- **Recommended Fix:** Add Flask after-request handler to set security headers.

### S-14: No CORS Configuration
- **Severity:** MEDIUM
- **Category:** Web Security
- **Files:** [`web/routes/admin_api.py`](web/routes/admin_api.py)
- **Root Cause:** No CORS headers configured. Default Flask behavior allows same-origin only.
- **Impact:** If admin panel is served from a different origin, API calls fail.
- **Recommended Fix:** Add Flask-CORS with explicit allowed origins.

### S-15: Missing `secrets.compare_digest()` for Token Comparison
- **Severity:** MEDIUM
- **Category:** Cryptography — Timing Attack
- **File:** [`web/routes/webhook.py:37`](web/routes/webhook.py:37)
- **Root Cause:** `token == _WEBHOOK_SECRET_TOKEN` uses standard string comparison which short-circuits. Vulnerable to timing attacks.
- **Impact:** An attacker could theoretically determine the webhook token character-by-character through timing analysis.
- **Recommended Fix:** Use `secrets.compare_digest(token, _WEBHOOK_SECRET_TOKEN)`.

### S-16: Docker daemon Runs as root (USER botuser but entrypoint runs exec)
- **Severity:** MEDIUM
- **Category:** Container Security
- **File:** [`Dockerfile:40`](Dockerfile:40)
- **Root Cause:** Dockerfile correctly sets `USER botuser`, but docker-entrypoint.sh uses `exec "$@"` which respects the USER.
- **Impact:** Acceptable risk. Non-root user. Verified.
- **Recommended Fix:** Add `--read-only` to docker-compose for filesystem where possible.

### S-17: No Request Size Limiting in Flask
- **Severity:** MEDIUM
- **Category:** DoS Prevention
- **Files:** [`bot.py`](bot.py), [`admin_bot.py`](admin_bot.py)
- **Root Cause:** Flask default max content length is unlimited. nginx sets `client_max_body_size 20M`.
- **Impact:** If nginx is bypassed, large uploads could consume memory.
- **Recommended Fix:** Set `app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024` in Flask.

### S-18: `eval()` or `exec()` — None Found ✅
- **Status:** CLEAN — No use of `eval()`, `exec()`, or `compile()` found anywhere in the codebase.

### S-19: SQL Injection — PostgreSQL Parameterized Queries Used ✅
- **Status:** CLEAN — All database queries use `%s` placeholders with parameterized execution. No string concatenation with user input in SQL queries.
- **One exception:** Migration 002 uses `f"DELETE FROM {table}"` but `table` is hardcoded in the migration, not user-controlled. Safe.

---

## 5. LOW FINDINGS

### S-20: `.env.example` Shows Placeholder Values
- **Severity:** LOW
- **File:** [`.env.example`](.env.example)
- **Impact:** None for security (it's documentation). Just a reminder to not commit real `.env`.
- **Status:** `.env` is in `.gitignore`. ✅

### S-21: Logger May Log Sensitive Data in Callback Data
- **Severity:** LOW
- **File:** [`bot/middleware.py:108`](bot/middleware.py:108)
- **Root Cause:** `logger.info(f"Request: user={uid}, data={data[:100]}")` — callback data may contain user IDs, amounts, etc.
- **Impact:** Low. Callback data is not secret but may include service/country choices.
- **Recommended Fix:** Sanitize or truncate to first 20 chars.

### S-22: Debug Mode Controlled by Env Var
- **Severity:** LOW
- **File:** [`config.py:79`](config.py:79)
- **Root Cause:** `FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'`
- **Impact:** If FLASK_DEBUG=true in production, Werkzeug debugger exposes code execution.
- **Status:** Default is `false`. ✅ Safe by default.

### S-23: No Signed Cookies
- **Severity:** LOW
- **Category:** Session Security
- **Files:** All web routes
- **Root Cause:** Flask sessions are not used. Admin panel uses token-based auth (query param — see S-1). No cookies to protect.
- **Impact:** If sessions are added later, ensure they use `SESSION_COOKIE_SECURE=True` and `SESSION_COOKIE_HTTPONLY=True`.

### S-24: nginx TLS Configuration Missing Modern Cipher Suites
- **Severity:** LOW
- **File:** [`nginx/numgenius.conf`](nginx/numgenius.conf)
- **Root Cause:** No explicit `ssl_ciphers`, `ssl_protocols`, or `ssl_prefer_server_ciphers` directives.
- **Impact:** Uses nginx defaults which are acceptable but not optimal.
- **Recommended Fix:** Add:
```nginx
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
ssl_prefer_server_ciphers off;
```

---

## 6. SECURITY POSTURE SUMMARY

| Category | Status | Notes |
|----------|--------|-------|
| Hardcoded secrets | ⚠️ FAIL | Docker Compose Postgres default password |
| Environment leaks | ✅ PASS | `.env` in `.gitignore`, `.env.example` is placeholder-only |
| SQL injection | ✅ PASS | All queries parameterized with `%s` |
| Command injection | ✅ PASS | No `os.system()`, `subprocess` with shell=True found |
| Path traversal | ✅ PASS | No file path operations on user input |
| XSS | ⚠️ NEEDS REVIEW | Telegram API handles escaping; Flask templates not checked for `|safe` misuse |
| CSRF | ⚠️ PARTIAL | Payment CSRF implemented but broken (S-8) |
| Authentication | ⚠️ FAIL | Webhook token bypass in prod (S-2), admin token in URL (S-1) |
| Authorization | ✅ PASS | RBAC service with role-based checks on all admin operations |
| Rate limiting | ⚠️ PARTIAL | RateLimiter class exists but not applied (S-7) |
| Abuse prevention | ⚠️ PARTIAL | Broadcast has no rate limiting (S-10) |
| Audit trail | ⚠️ PARTIAL | DB-only audit log, can be deleted (S-11) |
| Transport security | ⚠️ PARTIAL | HTTPS via nginx only, no HSTS (S-12) |
| Cryptographic practices | ⚠️ FAIL | Timing-vulnerable token comparison (S-15), non-deterministic SECRET_KEY (S-3) |

---

## 7. ACTION ITEMS (ORDERED BY PRIORITY)

| Priority | Finding | Action |
|----------|---------|--------|
| P0 | S-4 | Remove Postgres default password |
| P0 | S-3 | Make SECRET_KEY mandatory |
| P0 | S-2 | Enforce webhook token in production |
| P0 | S-1 | Move admin token from query string to Bearer header |
| P1 | S-8 | Fix payment CSRF state token in callback URL |
| P1 | S-5 | Add Redis password |
| P1 | S-7 | Apply rate limiting to admin endpoints |
| P1 | S-10 | Add rate limiting to broadcast |
| P1 | S-11 | Add file-based audit log |
| P2 | S-9 | Move payment states to Redis |
| P2 | S-15 | Use `secrets.compare_digest()` |
| P2 | S-12 | Add HSTS headers in nginx |
| P2 | S-13 | Add security headers (CSP, X-Frame-Options) |
| P3 | S-16 | Harden container filesystem |
| P3 | S-24 | Configure TLS cipher suites |

---

*End of Phase I — Security Audit Report*
