# راهنمای قدم به قدم دیپلوی روی همروش

این راهنما برای دیپلوی نسخه production ترب‌جان است.

## 1. تصمیم مهم قبل از دیپلوی

در لوکال، IP `5.208.12.139` توسط ترب whitelist شده و API مستقیم ترب جواب می‌دهد.

روی همروش، درخواست‌ها از IP سرور همروش خارج می‌شوند، نه IP لوکال تو. بنابراین بعد از دیپلوی باید یکی از این دو حالت را داشته باشیم:

### حالت پیشنهادی

از API مستقیم ترب استفاده کنیم:

```text
TOROB_BASE_URL=https://api.torob.com
TOROB_PROXY_TOKEN=
```

بعد اگر `/admin/torob-health` در production خطا داد، IP خروجی همروش را به ترب می‌دهی تا whitelist کنند.

### حالت جایگزین موقت

اگر ترب هنوز IP همروش را whitelist نکرده بود، از gateway استفاده کن:

```text
TOROB_BASE_URL=https://torob-proxy-gateway.darkube.ir
TOROB_PROXY_TOKEN=torob-gateway-2026-secret-8XkP91mZqA
```

## 2. ساخت دیتابیس Postgres در همروش

در پنل همروش:

1. یک سرویس/database از نوع `PostgreSQL` بساز.
2. نام دیتابیس، یوزر، پسورد و host را بردار.
3. connection string را به این فرم بساز:

```text
postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME
```

این مقدار را برای env زیر لازم داریم:

```text
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME
```

## 3. ساخت اپ Docker در همروش

در پنل همروش:

1. یک Application جدید بساز.
2. روش build را Dockerfile انتخاب کن.
3. Repository همین پروژه را بده.
4. Container port را `8000` تنظیم کن.
5. اگر گزینه health/liveness دارد، path را `/health` بگذار.

## 4. Environment Variables

این‌ها را در بخش env همروش بگذار:

```text
APP_ENV=production
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME
ADMIN_PASSWORD=یک-رمز-قوی-برای-ادمین
SESSION_SECRET=یک-رشته-خیلی-طولانی-و-تصادفی
UPLOAD_DIR=/data/uploads

TOROB_BASE_URL=https://api.torob.com
TOROB_PROXY_TOKEN=
TOROB_COOKIE=
TOROB_CSRF_TOKEN=
TOROB_TIMEOUT_SECONDS=30
TOROB_MAX_RETRIES=1
TOROB_RATE_LIMIT_SECONDS=0.10
```

برای ساخت `SESSION_SECRET` می‌توانی این دستور را روی سیستم خودت بزنی:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## 5. Volume برای فایل‌های آپلودی

اگر می‌خواهی فایل‌های Excel آپلودشده بعد از restart یا redeploy باقی بمانند:

1. یک volume بساز.
2. آن را روی مسیر زیر mount کن:

```text
/data/uploads
```

اگر volume ندهی، محصول همچنان کار می‌کند، اما فایل‌های اصلی آپلودشده ممکن است بعد از redeploy پاک شوند. خروجی‌ها از دیتابیس ساخته می‌شوند، ولی نگهداری فایل اصلی برای audit بهتر است.

## 6. Deploy

بعد از deploy:

1. دامنه/URL اپ را باز کن.
2. این مسیر باید `ok` بدهد:

```text
/health
```

3. برو به:

```text
/admin/login
```

4. با `ADMIN_PASSWORD` وارد شو.
5. این مسیر را بزن:

```text
/admin/torob-health
```

## 7. نتیجه‌های ممکن `/admin/torob-health`

### اگر OK بود

یعنی ترب از production قابل دسترسی است. بعد:

1. یک فایل 5 ردیفی تست کن.
2. اگر درست بود، فایل 110 ردیفی را تست کن.

### اگر `torob_bot_challenge` بود

IP خروجی همروش باید به ترب داده شود یا باید موقتاً gateway را در env بگذاری.

### اگر `torob_timeout` بود

مشکل شبکه/فایروال/مسیر خروجی سرور است.

### اگر `torob_gateway_not_found` بود

فقط وقتی معنی دارد که `TOROB_BASE_URL` را روی gateway گذاشته باشی. یعنی route/deploy gateway مشکل دارد.

## 8. نکات عملی برای اولین کاربر واقعی

برای اولین pilot:

1. فقط 1 فروشنده واقعی.
2. حداکثر 100 تا 200 محصول.
3. قبل از تحویل به فروشنده، `/admin/torob-health` را چک کن.
4. بعد از submission، خروجی Excel را از admin دانلود و دستی بررسی کن.
5. اگر ردیف‌هایی retry داشتند، اول health را چک کن، بعد retry بزن.

## 9. Rollback سریع

اگر production مشکل خورد:

1. env `TOROB_BASE_URL` را از API مستقیم به gateway تغییر بده، اگر gateway سالم است.
2. یا برعکس، اگر gateway خراب بود، به API مستقیم برگرد.
3. redeploy کن.
4. `/admin/torob-health` را دوباره تست کن.

