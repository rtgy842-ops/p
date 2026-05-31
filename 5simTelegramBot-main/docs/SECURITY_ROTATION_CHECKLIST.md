# SECURITY CREDENTIAL ROTATION CHECKLIST
# Date: 2026-05-31 — CRITICAL: Rotate ALL keys immediately

# 1. Telegram Bot Tokens
#    OLD: BOT_TOKEN=8867840427:AAG56v1yGp4XBjL2-vlhHIhPR765NikFhDI
#    → Go to @BotFather: /mybots → select bot → API Token → Revoke & Regenerate
#    → Update .env: BOT_TOKEN=<NEW_TOKEN>

# 2. Admin Bot Token  
#    OLD: ADMIN_BOT_TOKEN=8661921297:AAFdV3aIjx_9lTPAT86gR2OqHT4j2lsZvJU
#    → Go to @BotFather: /mybots → select admin bot → Revoke & Regenerate
#    → Update .env: ADMIN_BOT_TOKEN=<NEW_TOKEN>

# 3. HeroSMS API Key
#    OLD: HEROSMS_API_KEY=cb28fe1389Abce0053b2fb3bA48d6b4c
#    → Go to https://hero-sms.com → Account → API Key → Regenerate
#    → Update .env: HEROSMS_API_KEY=<NEW_KEY>

# 4. ZarinPal Merchant ID
#    OLD: ZARINPAL_MERCHANT=1344b5d4-0048-11e8-94db-005056a205be
#    → Go to https://zarinpal.com → Panel → Settings → Regenerate
#    → Update .env: ZARINPAL_MERCHANT=<NEW_ID>

# 5. Navasan API Key
#    OLD: NAVASAN_API_KEY=free26Ln3Pt7qXlEydjJYJEKDcjEYKuS
#    → Rotate via Navasan dashboard
#    → Update .env: NAVASAN_API_KEY=<NEW_KEY>

# 6. Database Password
#    OLD: POSTGRES_PASSWORD=MyS3cur3Pssw0r
#    → ALTER USER smsbot WITH PASSWORD '<NEW_STRONG_PASSWORD>';
#    → Update .env: POSTGRES_PASSWORD=<NEW_PASSWORD>
#    → Update .env: DATABASE_URL=postgresql://smsbot:<NEW_PASSWORD>@postgres:5432/smsbot

# 7. Flask SECRET_KEY
#    OLD: fd9ba87d9c63b82972e3cf7eb6d4b015...
#    → Generate: python -c "import secrets; print(secrets.token_hex(32))"
#    → Update .env: SECRET_KEY=<NEW_KEY>

# 8. ADMIN_API_TOKEN
#    OLD: 671fd5d8672ebbf3d0e122e80573af6a0bff71fd73d7d88e
#    → Generate: python -c "import secrets; print(secrets.token_hex(16))"
#    → Update .env: ADMIN_API_TOKEN=<NEW_TOKEN>

# VERIFICATION AFTER ROTATION:
# [ ] Bot responds to /start
# [ ] Admin bot responds to /start
# [ ] HeroSMS getBalance returns data
# [ ] ZarinPal payment link generated
# [ ] Web admin panel accessible
# [ ] Database connections work
