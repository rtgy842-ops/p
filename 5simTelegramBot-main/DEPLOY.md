# 🚀 دليل تشغيل المشروع على VPS — خطوة بخطوة

## المتطلبات الأساسية للـ VPS

| المتطلب | الحد الأدنى |
|---------|------------|
| نظام التشغيل | Ubuntu 22.04 LTS (مُوصى به) |
| الرام | 1 GB |
| المساحة | 10 GB SSD |
| النطاق | `abunumapp.com` يشير إلى IP السيرفر |
| المنافذ المفتوحة | 80 (HTTP), 443 (HTTPS) |

---

## الخطوة 1: الاتصال بالسيرفر وتحديث النظام

```bash
ssh root@YOUR_SERVER_IP

# تحديث الحزم
apt update && apt upgrade -y

# تثبيت الأدوات الأساسية
apt install -y git curl wget ufw
```

---

## الخطوة 2: تثبيت Docker و Docker Compose

```bash
# تثبيت Docker
curl -fsSL https://get.docker.com | sh

# تشغيل Docker تلقائياً
systemctl enable docker
systemctl start docker

# تثبيت Docker Compose
apt install -y docker-compose-plugin

# التحقق من التثبيت
docker --version
docker compose version
```

---

## الخطوة 3: تحميل المشروع

```bash
cd /opt
git clone https://github.com/YOUR_USER/5simTelegramBot.git
cd 5simTelegramBot
```

إذا كنت ترفع المشروع يدوياً (SFTP/SCP):
```bash
mkdir -p /opt/5simTelegramBot
# ارفع جميع ملفات المشروع إلى /opt/5simTelegramBot
```

---

## الخطوة 4: إعداد ملف البيئة `.env`

```bash
cd /opt/5simTelegramBot

# إنشاء .env من المثال (إذا لم يكن موجوداً)
cp .env.example .env

# تحرير .env بالمعلومات الصحيحة
nano .env
```

تأكد من هذه القيم في `.env`:
```
BOT_TOKEN=8867840427:AAG56v1yGp4XBjL2-vlhHIhPR765NikFhDI
ADMIN_IDS=8683874068
WEBHOOK_URL=https://abunumapp.com
WEBSITE_URL=https://abunumapp.com
HEROSMS_API_KEY=cb28fe1389Abce0053b2fb3bA48d6b4c
ZARINPAL_MERCHANT=1344b5d4-0048-11e8-94db-005056a205be
ZARINPAL_SANDBOX=false       # false = إنتاج حقيقي
```

---

## الخطوة 5: إعداد الجدار الناري

```bash
ufw allow 22/tcp     # SSH
ufw allow 80/tcp     # HTTP
ufw allow 443/tcp    # HTTPS
ufw enable
```

---

## الخطوة 6: إنشاء مجلدات البيانات

```bash
cd /opt/5simTelegramBot
mkdir -p data/backups logs nginx/conf.d certs
chmod -R 755 data logs
```

---

## الخطوة 7: بناء وتشغيل الخدمات

```bash
cd /opt/5simTelegramBot

# بناء الصور
docker compose build

# تشغيل جميع الخدمات
docker compose up -d

# مشاهدة حالة الخدمات
docker compose ps

# مشاهدة السجلات
docker compose logs -f
```

---

## الخطوة 8: التحقق من صحة الخدمات

```bash
# اختبار البوت
curl http://localhost:5000/ping
# يجب أن يظهر: pong

# اختبار الصحة الشاملة
curl http://localhost:5000/health
# يجب أن يظهر JSON بحالة healthy

# رؤية جميع الحاويات
docker ps
```

يجب أن ترى 5 حاويات:
- `smsbot-nginx` — reverse proxy
- `smsbot-bot` — البوت + Flask
- `smsbot-redis` — cache + queue
- `smsbot-worker` — Celery worker
- `smsbot-beat` — Celery scheduler

---

## الخطوة 9: تثبيت SSL (Let's Encrypt)

```bash
# تثبيت certbot
apt install -y certbot

# إيقاف nginx مؤقتاً لتحرير المنفذ 80
docker compose stop nginx

# إنشاء الشهادة
certbot certonly --standalone -d abunumapp.com

# نسخ الشهادات إلى مجلد certs
cp /etc/letsencrypt/live/abunumapp.com/fullchain.pem certs/
cp /etc/letsencrypt/live/abunumapp.com/privkey.pem certs/
chmod 644 certs/*.pem

# إعادة تشغيل nginx
docker compose up -d nginx
```

---

## الخطوة 10: تفعيل Webhook Telegram

```bash
BOT_TOKEN="8867840427:AAG56v1yGp4XBjL2-vlhHIhPR765NikFhDI"

# حذف webhook القديم
curl "https://api.telegram.org/bot${BOT_TOKEN}/deleteWebhook"

# تعيين webhook الجديد
curl "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook?url=https://abunumapp.com/"

# التحقق من حالة webhook
curl "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo"
```

يجب أن تظهر النتيجة:
```json
{
  "ok": true,
  "result": {
    "url": "https://abunumapp.com/",
    "has_custom_certificate": false,
    "pending_update_count": 0
  }
}
```

---

## الخطوة 11: اختبار البوت

1. افتح تيليجرام
2. ابحث عن البوت الخاص بك
3. أرسل `/start`
4. يجب أن يظهر لك رسالة الترحيب والقائمة الرئيسية

---

## أوامر الصيانة اليومية

```bash
cd /opt/5simTelegramBot

# مشاهدة الحالة
docker compose ps

# مشاهدة السجلات (آخر 100 سطر)
docker compose logs --tail 100

# إعادة تشغيل خدمة معينة
docker compose restart bot

# إعادة تشغيل الكل
docker compose restart

# تحديث المشروع (بعد git pull)
git pull
docker compose build
docker compose up -d

# النسخ الاحتياطي اليدوي
docker compose exec bot python -c "
from backup_manager import BackupManager
bm = BackupManager(backup_interval=5)
bm.create_backup()
"
```

---

## التجديد التلقائي لشهادة SSL

```bash
# إنشاء cron job للتجديد التلقائي
crontab -e

# أضف هذا السطر (كل شهر في منتصف الليل):
0 0 1 * * docker compose -f /opt/5simTelegramBot/docker-compose.yml stop nginx && certbot renew --quiet && cp /etc/letsencrypt/live/abunumapp.com/fullchain.pem /opt/5simTelegramBot/certs/ && cp /etc/letsencrypt/live/abunumapp.com/privkey.pem /opt/5simTelegramBot/certs/ && docker compose -f /opt/5simTelegramBot/docker-compose.yml up -d nginx
```

---

## استكشاف الأخطاء

### البوت لا يستجيب
```bash
# تحقق من webhook
curl "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo"

# تحقق من سجلات البوت
docker compose logs bot --tail 50
```

### خطأ في قاعدة البيانات
```bash
# إعادة تشغيل الترحيلات
docker compose exec bot python -c "
from db.migrations import MigrationManager
mm = MigrationManager()
print('Current version:', mm.get_current_version())
print('Status:', mm.status())
"
```

### nginx لا يعمل
```bash
docker compose logs nginx --tail 20
docker compose restart nginx