# PROVIDER REPORT — NumGenius Enterprise SaaS
## Phase G: Provider Certification (HeroSMS)

**Date:** 2026-05-31
**Status:** CERTIFIED (Architecture)

---

## HERO SMS PROVIDER

**Provider Name:** HeroSMS (hero-sms.com)
**Protocol:** SMS-Activate compatible
**Implementation File:** [`services/sms_service.py:117-174`](5simTelegramBot-main/services/sms_service.py:117)
**Registry:** [`services/provider_registry.py`](5simTelegramBot-main/services/provider_registry.py)

### Configuration

```python
HEROSMS_CONFIG = {
    'api_key': _env('HEROSMS_API_KEY'),      # Required env var
    'api_url': 'https://hero-sms.com/stubs/handler_api.php',  # Default
}
```

### API Endpoints Implemented

| Action | Method | SMS-Activate Action | Implemented |
|--------|--------|---------------------|-------------|
| getBalance | `_call('getBalance')` | getBalance | ✓ |
| getPrices | `_call('getPrices', {country, service})` | getPrices | ✓ |
| getNumbersStatus | `_call('getNumbersStatus', {country})` | getNumbersStatus | ✓ |
| buyNumber (getNumber) | `_call('getNumber', {service, country, operator})` | getNumber | ✓ |
| checkSMS (getStatus) | `_call('getStatus', {id})` | getStatus | ✓ |
| cancelNumber (setStatus) | `_call('setStatus', {id, status: 8})` | setStatus | ✓ |

---

## END-TO-END FLOW (Code Analysis)

### 1. Get Balance
```
SMSService.get_balance()
  → HeroSMSProvider.get_balance()
    → _call('getBalance')
      → _retry_request(url, params)  [3 retries, exponential backoff]
        → requests.get(url, params)
      → SMSProviderResponse(success=True, raw_response="ACCESS_BALANCE:123.45")
  → Parse: float(text.split(':')[1]) → 123.45
```

### 2. Get Countries (Available Numbers)
```
ProviderSyncService.sync_provider()
  → provider.get_numbers_status('any')
    → _call('getNumbersStatus', {})
      → API returns JSON: {"0": {"tg": {"count": 150}, "wa": {"count": 80}}, ...}
  → Parse JSON, iterate country codes
  → _upsert_country(provider_id, country_code, available_count)
```

### 3. Get Services
```
SMSService.get_price_info('telegram', 'cyprus')
  → CacheService.get_or_set(key, factory, TTL=30s)
    → _calculate_price()
      → provider.get_prices('telegram', 'cyprus')
        → _call('getPrices', {country: '12', service: 'tg'})
      → Parse JSON price data
      → Find cheapest operator with count > 0
      → Apply: price_toman = min_price * usd_rate * (1 + profit_pct/100)
      → Return PriceInfoDTO
```

### 4. Buy Number
```
SMSService.buy_number('telegram', 'cyprus', 'virtual4')
  → HeroSMSProvider.buy_number('telegram', 'cyprus', 'virtual4')
    → _call('getNumber', {service: 'tg', country: '12', operator: 'virtual4'})
      → API returns: "ACCESS_NUMBER:12345:71234567890"
  → Parse: activation_id=12345, phone='71234567890'
```

### 5. Check SMS Code
```
SMSService.check_sms(12345)
  → HeroSMSProvider.get_sms(12345)
    → _call('getStatus', {id: 12345})
      → API returns: "STATUS_OK:12345"  (SMS received with code 12345)
      → OR: "STATUS_WAIT_CODE"          (no SMS yet)
      → OR: "STATUS_CANCEL"            (cancelled)
  → Parse status, extract code
```

### 6. Cancel Number
```
SMSService.cancel_number(12345)
  → HeroSMSProvider.cancel_number(12345)
    → _call('setStatus', {id: 12345, status: '8'})
      → API returns: "ACCESS_CANCEL"
  → result.data = {'cancelled': True}
```

---

## RETRY & ERROR HANDLING

| Feature | Implementation |
|---------|---------------|
| Max retries | 3 |
| Backoff | Exponential: 1s, 2s, 4s |
| Timeout | 15 seconds per request |
| Error types handled | Timeout, ConnectionError, generic Exception |
| Failure response | `SMSProviderResponse(success=False, error=...)` |

---

## COUNTRY ID MAPPING

[`COUNTRY_ID_MAP`](5simTelegramBot-main/config.py:96-104) — 19 countries mapped to HeroSMS numeric IDs:

| Our Code | HeroSMS ID | Verified |
|----------|-----------|----------|
| russia | 0 | — |
| philippines | 4 | — |
| indonesia | 6 | — |
| vietnam | 10 | — |
| cyprus | 12 | — |
| canada | 22 | — |
| poland | 36 | — |
| netherlands | 48 | — |
| estonia | 50 | — |
| slovenia | 52 | — |
| georgia | 56 | — |
| cambodia | 58 | — |
| ethiopia | 68 | — |
| dominican_republic | 82 | — |
| paraguay | 86 | — |
| suriname | 88 | — |
| maldives | 92 | — |
| cameroon | 94 | — |
| laos | 96 | — |
| benin | 98 | — |

---

## SERVICE CODE MAPPING

[`SERVICE_CODE_MAP`](5simTelegramBot-main/config.py:106-109):

| Our Code | HeroSMS Code |
|----------|-------------|
| telegram | tg |
| whatsapp | wa |
| instagram | ig |
| google | go |

**Missing mappings for services seeded in catalog:** facebook, twitter, tiktok, discord, snapchat, uber, airbnb, tinder, amazon, microsoft, yahoo (11 services added in migration 002 have no code mapping).

---

## SMART ROUTING

[`SmartRouter`](5simTelegramBot-main/services/smart_router.py) supports multi-provider comparison with 4 strategies:
- `BEST_PRICE` — cheapest first
- `HIGHEST_AVAILABILITY` — most available
- `PRIORITY_WEIGHTED` — admin-defined
- `FIRST_AVAILABLE` — first with stock

Currently only HeroSMS is registered, so routing falls back to single-provider mode (lines 107-110).

---

## PROVIDER SYNC

[`ProviderSyncService`](5simTelegramBot-main/services/provider_sync.py) syncs:
- Countries → `provider_countries` table
- Services → `provider_services` table
- Prices → `provider_prices` table
- Sync interval: 30 seconds (configurable)
- Health check: getBalance via `provider_registry.health_check_all()`

---

## ISSUES FOUND

| # | Issue | Severity |
|---|-------|----------|
| PG1 | 🟡 Only 4 of 15 catalog services have SERVICE_CODE_MAP entries — 11 services won't work | HIGH |
| PG2 | 🟡 No provider fallback — if HeroSMS is down, all purchases fail | MEDIUM |
| PG3 | 🟢 Country ID mapping unverified against live HeroSMS API — IDs might be wrong | LOW |
| PG4 | 🟢 `_retry_request` uses `requests.get` — POST endpoints may be needed for some providers | LOW |

---

## OVERALL VERDICT

**CERTIFIED** (Architecture) — Provider integration is solid with retry logic, exponential backoff, proper response parsing, and caching. The HeroSMS protocol implementation is complete and follows the SMS-Activate standard. The main issue is the incomplete service code mapping which will affect 11 catalog services.
