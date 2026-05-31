# 🚀 تعليمات النشر الكاملة — NumGenius Enterprise SaaS
## من الصفر إلى الإنتاج على VPS

---

## 1. متطلبات الخادم

```
OS: Ubuntu 22.04 LTS أو Debian 12
RAM: 2GB minimum (4GB recommended)
CPU: 2 cores minimum
Disk: 20GB minimum
```

---

## 2. الاتصال بالخادم

```bash
ssh root@YOUR_VPS_IP
```

---

## 3. تحديث النظام وتثبيت المتطلبات الأساسية

```bash
apt update && apt upgrade -y

# تثبيت Docker + Docker Compose + Git + Nginx + Certbot
apt install -y \
    docker.io docker-compose-v2 \
    git nginx certbot python3-certbot-nginx \
    curl wget ufw
```

---

## 4. إعداد جدار الحماية (Firewall)

```bash
ufw allow 22    # SSH
ufw allow 80    # HTTP
ufw allow 443   # HTTPS
ufw enable
```

---

## 5. تحميل المشروع

```bash
cd /opt
git clone https://github.com/YOUR_USERNAME/5simTelegramBot-main.git numgenius
cd numgenius
```

---

## 6. إعداد ملف البيئة `.env`

```bash
cp .env.example .env
nano .env
```

**املأ القيم الحقيقية:**

```env
# ── بيئة التطبيق ───────────────────────────────────
APP_ENV=production

# ── بوت العملاء (Telegram Bot Token) ───────────────
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
WEBHOOK_URL=https://api.yourdomain.com
WEBSITE_URL=https://app.yourdomain.com
WEBHOOK_SECRET_TOKEN=YOUR_RANDOM_64_CHAR_SECRET_TOKEN_HERE

# ── بوت الإدارة (يجب أن يكون مختلفاً عن بوت العملاء) ──
ADMIN_BOT_TOKEN=9876543210:ZYXwvuTSRqpONMlkjIHGfedCBA
ADMIN_IDS=YOUR_TELEGRAM_USER_ID
ADMIN_WEBHOOK_URL=https://admin.yourdomain.com

# ── HeroSMS API ────────────────────────────────────
HEROSMS_API_KEY=YOUR_HEROSMS_API_KEY
HEROSMS_API_URL=https://hero-sms.com/stubs/handler_api.php

# ── ZarinPal ───────────────────────────────────────
ZARINPAL_MERCHANT=YOUR_ZARINPAL_MERCHANT_ID
ZARINPAL_SANDBOX=false

# ── Navasan (نرخ ارز) ──────────────────────────────
NAVASAN_API_KEY=YOUR_NAVASAN_API_KEY

# ── قاعدة البيانات PostgreSQL ──────────────────────
DATABASE_URL=postgresql://smsbot:STRONG_PASSWORD_HERE@postgres:5432/smsbot
POSTGRES_USER=smsbot
POSTGRES_PASSWORD=STRONG_PASSWORD_HERE
POSTGRES_DB=smsbot

# ── Redis ──────────────────────────────────────────
REDIS_PASSWORD=STRONG_REDIS_PASSWORD_HERE
CELERY_BROKER_URL=redis://:STRONG_REDIS_PASSWORD_HERE@redis:6379/0
CELERY_RESULT_BACKEND=redis://:STRONG_REDIS_PASSWORD_HERE@redis:6379/0

# ── Flask ──────────────────────────────────────────
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=false
SECRET_KEY=GENERATE_A_RANDOM_64_CHAR_STRING_HERE_USE_PASSWORD_MANAGER

# ── لوحة الإدارة ──────────────────────────────────
ADMIN_API_TOKEN=GENERATE_ANOTHER_RANDOM_64_CHAR_TOKEN_HERE

# ── التسجيل ───────────────────────────────────────
LOG_LEVEL=INFO

# ── النسخ الاحتياطي ───────────────────────────────
BACKUP_INTERVAL_SECONDS=300
BACKUP_FILE=data/users_backup.json
BACKUP_DIR=data/backups
```

**توليد كلمات السر العشوائية:**

```bash
# توليد SECRET_KEY و ADMIN_API_TOKEN
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))"
python3 -c "import secrets; print('ADMIN_API_TOKEN=' + secrets.token_hex(32))"
python3 -c "import secrets; print('REDIS_PASSWORD=' + secrets.token_hex(16))"
python3 -c "import secrets; print('POSTGRES_PASSWORD=' + secrets.token_hex(16))"
python3 -c "import secrets; print('WEBHOOK_SECRET_TOKEN=' + secrets.token_hex(32))"
```

---

## 7. إنشاء مجلدات البيانات

```bash
mkdir -p data/backups logs nginx/ssl
chmod 755 data logs
```

---

## 8. تشغيل المشروع

```bash
# تشغيل كل الخدمات (PostgreSQL + Redis + Customer Bot + Admin Bot + Worker + Beat)
docker compose --profile full up -d --build
```

**التأكد من أن كل شيء يعمل:**

```bash
# فحص الحاويات
docker compose ps

# فحص السجلات
docker compose logs customer_bot --tail 20
docker compose logs admin_bot --tail 20
docker compose logs worker --tail 20

# فحص صحة قاعدة البيانات
docker compose exec postgres pg_isready -U smsbot -d smsbot
```

---

## 9. إعداد Nginx + SSL

### أ. توجيه DNS

قبل المتابعة، تأكد من أن النطاقات تشير إلى IP الخادم:

```
api.yourdomain.com    → YOUR_VPS_IP
admin.yourdomain.com  → YOUR_VPS_IP
app.yourdomain.com    → YOUR_VPS_IP
```

### ب. نسخ إعدادات Nginx

```bash
cp nginx/numgenius.conf /etc/nginx/sites-available/numgenius
nano /etc/nginx/sites-available/numgenius
```

**عدّل اسم النطاق في ملف nginx:**

استبدل كل `api.abunumapp.com` و `admin.abunumapp.com` و `app.abunumapp.com` بنطاقاتك الفعلية.

```bash
# تفعيل الموقع
ln -s /etc/nginx/sites-available/numgenius /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default

# فحص الإعدادات
nginx -t

# إعادة تشغيل Nginx
systemctl restart nginx
```

### ج. شهادة SSL من Let's Encrypt

```bash
# الحصول على الشهادة لجميع النطاقات
certbot --nginx -d api.yourdomain.com -d admin.yourdomain.com -d app.yourdomain.com

# التجديد التلقائي
certbot renew --dry-run
```

---

## 10. إعداد Webhook لتليجرام

```bash
# بوت العملاء
curl -X POST "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://api.yourdomain.com/",
    "secret_token": "YOUR_WEBHOOK_SECRET_TOKEN"
  }'

# بوت الإدارة
curl -X POST "https://api.telegram.org/bot${ADMIN_BOT_TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://admin.yourdomain.com/",
    "secret_token": "YOUR_WEBHOOK_SECRET_TOKEN"
  }'

# التحقق من حالة webhook
curl "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo"
curl "https://api.telegram.org/bot${ADMIN_BOT_TOKEN}/getWebhookInfo"
```

---

## 11. فحص النظام بالكامل

```bash
# فحص صحة التطبيق
curl https://api.yourdomain.com/ping
curl https://api.yourdomain.com/health

curl https://admin.yourdomain.com/ping
curl https://admin.yourdomain.com/health

# فحص السجلات
docker compose logs --tail 50
```

---

## 12. أوامر الصيانة اليومية

```bash
# عرض حالة الحاويات
docker compose ps

# عرض السجلات
docker compose logs --tail 100

# إعادة تشغيل خدمة معينة
docker compose restart customer_bot
docker compose restart admin_bot

# إعادة تشغيل الكل
docker compose restart

# تحديث المشروع (عند وجود تحديثات)
cd /opt/numgenius
git pull
docker compose --profile full up -d --build

# النسخ الاحتياطي لقاعدة البيانات
docker compose exec postgres pg_dump -U smsbot smsbot > backups/db_$(date +%Y%m%d_%H%M%S).sql

# استعادة النسخ الاحتياطي
docker compose exec -T postgres psql -U smsbot smsbot < backups/db_BACKUP_FILE.sql
```

---

## 13. المشاكل الشائعة وحلولها

### المشكلة: Webhook لا يستقبل التحديثات

```bash
# تأكد من أن الشهادة صالحة
curl -I https://api.yourdomain.com/

# أعد تعيين webhook
curl -X POST "https://api.telegram.org/bot${BOT_TOKEN}/deleteWebhook"
curl -X POST "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://api.yourdomain.com/", "secret_token": "YOUR_WEBHOOK_SECRET_TOKEN"}'
```

### المشكلة: حاوية PostgreSQL لا تعمل

```bash
# فحص السجلات
docker compose logs postgres

# إعادة تهيئة قاعدة البيانات (سيؤدي لفقدان البيانات)
docker compose down -v
docker compose --profile full up -d
```

### المشكلة: خطأ CSRF في المدفوعات

تأكد من تعيين `WEBHOOK_SECRET_TOKEN` في `.env` بنفس القيمة المستخدمة في إعداد webhook.

---

## 14. المتغيرات المطلوبة للتشغيل

| المتغير | مطلوب؟ | الوصف |
|---------|--------|-------|
| BOT_TOKEN | ✅ | Token بوت تليجرام للعملاء |
| ADMIN_BOT_TOKEN | ✅ | Token بوت تليجرام للإدارة |
| ADMIN_IDS | ✅ | معرفات مسؤولي النظام |
| HEROSMS_API_KEY | ✅ | مفتاح HeroSMS API |
| ZARINPAL_MERCHANT | ✅ | معرف التاجر في زرينبال |
| DATABASE_URL | ✅ | رابط PostgreSQL |
| POSTGRES_PASSWORD | ✅ | كلمة مرور PostgreSQL |
| REDIS_PASSWORD | ✅ | كلمة مرور Redis |
| SECRET_KEY | ✅ | مفتاح Flask السري |
| ADMIN_API_TOKEN | ✅ | رمز لوحة الإدارة |
| WEBHOOK_SECRET_TOKEN | ✅ | رمز حماية webhook |
| WEBHOOK_URL | ✅ | رابط النطاق الرئيسي |
| WEBSITE_URL | ✅ | رابط موقع الويب |
| NAVASAN_API_KEY | ⚠️ | مفتاح API نوسان (لأسعار العملات) |

---

## 15. هيكل المشروع النهائي على الخادم

```
/opt/numgenius/
├── .env                     # المتغيرات البيئية (سري)
├── docker-compose.yml       # إعدادات Docker
├── Dockerfile               # بناء الحاوية
├── docker-entrypoint.sh     # نقطة دخول الحاوية
├── bot.py                   # بوت العملاء
├── admin_bot.py             # بوت الإدارة
├── config.py                # الإعدادات
├── services/                # طبقة الخدمات
├── db/                      # طبقة قاعدة البيانات
├── bot/                     # معالجات البوت
├── web/                     # مسارات الويب
├── alembic/                 # ترحيل قاعدة البيانات
├── nginx/                   # إعدادات Nginx
├── locales/                 # ملفات الترجمة
├── data/                    # بيانات التطبيق
├── logs/                    # السجلات
└── docs/                    # التقارير والتوثيق
```

---

## 16. قائمة فحص النشر النهائية

- [ ] تثبيت Docker + Docker Compose + Nginx + Certbot
- [ ] استنساخ المشروع إلى `/opt/numgenius`
- [ ] إنشاء ملف `.env` بكل القيم الحقيقية
- [ ] توليد كلمات سر عشوائية لكل الخدمات
- [ ] إعداد DNS للإشارة إلى VPS
- [ ] نسخ وتعديل إعدادات Nginx (`nginx/numgenius.conf`)
- [ ] تشغيل `docker compose --profile full up -d --build`
- [ ] التحقق من `docker compose ps` (كل الخدمات Up)
- [ ] الحصول على شهادة SSL: `certbot --nginx`
- [ ] إعداد Webhook لتليجرام
- [ ] فحص `/ping` و `/health` عبر HTTPS
- [ ] اختبار بوت تليجرام (`/start`)
- [ ] اختبار بوت الإدارة (`/start`)
- [ ] إعداد نسخ احتياطي تلقائي (cron job)

---

**تم — النظام جاهز للإنتاج 🚀**
