# 🚀 Tele2Rub

انتقال خودکار فایل از تلگرام به روبیکا — سریع، ساده، بدون هزینه و دردسر

**پشتیبانی از ارسال فایل تا ۲ گیگابایت**

---

## 🧠 معرفی

**Tele2Rub**

یک ابزار سبک و کاربردی است که فایل‌ها را از بات تلگرام دریافت کرده و به صورت خودکار به **سیو مسیج (Saved Messages)** روبیکا ارسال می‌کند.

کل فرایند به صورت **صف (Queue)** انجام می‌شود تا از بروز خطا و تداخل جلوگیری شود.

---

## ⚙️ نحوه کار

```text
ارسال به روبیکا → صف پردازش → دانلود فایل → ربات تلگرام
```

* دریافت فایل از تلگرام
* ذخیره موقت در سرور
* ثبت در صف
* ارسال خودکار توسط **Worker**

---

## ✨ قابلیت‌ها

* 📥 دریافت انواع فایل از تلگرام
* 🔗 پشتیبانی دانلود از لینک مستقیم 
* 📤 ارسال خودکار به روبیکا
* 🧾 ارسال همه فایل‌ها به صورت Document
* 📊 نمایش وضعیت دانلود و آپلود
* ❌ امکان حذف یک فایل از صف با `/del`
* 🧨 امکان پاکسازی کل صف با `/delall`
* 🛡 حالت Safe Mode برای ارسال فایل ها به صورت ZIP رمز دار
* ⚡سیستم صف برای جلوگیری از کرش
* 🔄 اجرای جداگانه پردازش برای پایداری بیشتر
* ⏱ محدودیت زمان آپلود برای جلوگیری از گیر کردن پردازش
 (این مقدار با توجه به سرعت سرور، حجم فایل‌ها و صبر و حوصله خودتون قابل تنظیمه.)
  (به‌صورت پیش‌فرض روی **۱۰ دقیقه** تنظیم شده.)
---

## 🛠 نصب سریع

ابتدا پروژه را دریافت کنید:

```bash
git clone https://github.com/caffeinexz/Tele2Rub.git
cd Tele2Rub
```

نصب وابستگی‌ها:

```bash
pip install -r requirements.txt
```

اجرای پروژه:

```bash
python3 main.py
```

## 🐳 اجرای Docker Compose (پیشنهادی)

```bash
docker compose up -d --build
```

برای ری‌استارت و پاکسازی کامل صف از داخل بات:

```text
/restart
```

این دستور فایل‌های موقت و صف را پاک می‌کند و سپس `docker compose restart` را اجرا می‌کند.

### ورود به روبیکا از داخل بات

حالا لاگین اولیه روبیکا از داخل بات انجام می‌شود:

1. دستور `/rubika_login` یا متن `ورود به روبیکا` را بزنید.
2. شماره موبایل را ارسال کنید.
3. کد OTP را که دریافت کردید بفرستید.
4. سشن ذخیره می‌شود و دفعات بعد (تا زمان انقضا/خروج) نیازی به OTP نیست.

## 📦 Build خودکار روی GitHub Container Registry (GHCR)

در این پروژه یک Workflow آماده شده که بعد از هر Push روی شاخه `main` (یا Tag مثل `v1.0.0`) ایمیج Docker را روی GHCR منتشر می‌کند:

```text
ghcr.io/<OWNER>/<REPO>:latest
ghcr.io/<OWNER>/<REPO>:<branch>
ghcr.io/<OWNER>/<REPO>:<tag>
ghcr.io/<OWNER>/<REPO>:sha-xxxxxxx
```

فایل Workflow:

```text
.github/workflows/docker-publish.yml
```

---

## ☁️ راهنمای Deploy روی سرور (با GHCR)

### 1) پیش‌نیازها روی سرور

```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg
```

Docker و Compose Plugin را نصب کنید (طبق داکیومنت رسمی Docker).

---

### 2) ساخت PAT در GitHub

در GitHub یک **Personal Access Token (classic)** بسازید با دسترسی:

* `read:packages`

اگر Repo خصوصی است:

* `repo`

---

### 3) لاگین GHCR روی سرور

```bash
echo "YOUR_GITHUB_PAT" | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin
```

---

### 4) ساخت فایل `.env` در سرور

```env
API_ID=...
API_HASH=...
BOT_TOKEN=...
RUBIKA_SESSION=rubsession
```

---

### 5) ساخت `docker-compose.prod.yml`

```yaml
services:
  tele2rub:
    image: ghcr.io/OWNER/REPO:latest
    container_name: tele2rub
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./downloads:/app/downloads
      - ./queue:/app/queue
      - ./sessions:/app/sessions
```

---

### 6) اجرای سرویس

```bash
docker compose -f docker-compose.prod.yml up -d
```

مشاهده لاگ:

```bash
docker compose -f docker-compose.prod.yml logs -f
```

---

### 7) آپدیت به آخرین نسخه

```bash
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

---

## 🖥 نصب روی سرور

### 1. نصب پیش‌نیازها

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip git -y
```

---

### 2. دریافت پروژه

```bash
git clone https://github.com/caffeinexz/Tele2Rub.git
cd Tele2Rub
```

---

### 3. ساخت محیط مجازی

```bash
python3 -m venv venv
```

---

### 4. فعال‌سازی محیط مجازی

```bash
source venv/bin/activate
```

---

### 5. نصب وابستگی‌ها

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

### 6. ساخت فایل تنظیمات

```bash
nano .env
```

و مقادیر زیر را وارد کنید:

```env
API_ID=عدد_API
API_HASH=کد_API
BOT_TOKEN=توکن_ربات
RUBIKA_SESSION=rubsession
```

---

### 7. اجرای دائمی (Screen)

```bash
screen -S tele2rub
source venv/bin/activate
python main.py
```

---

## ⚙️ تنظیمات

یک فایل `.env` در **ریشه پروژه** بسازید:

```env
API_ID=عدد_API
API_HASH=کد_API
BOT_TOKEN=توکن_ربات
RUBIKA_SESSION=rubsession
```

یا از فایل نمونه استفاده کنید:

```bash
cp .env.example .env
```

## 📌 دریافت API_ID و API_HASH از تلگرام

برای استفاده از پروژه، ابتدا باید API تلگرام دریافت کنید:

1. وارد سایت زیر شوید:
   👉 https://my.telegram.org

2. با شماره تلگرام خود وارد شوید

3. روی **API development tools** کلیک کنید

4. فرم را به شکل زیر پر کنید:

```text
App title: tele2rub
Short name: t2r
```

5. پس از ثبت، مقادیر زیر به شما داده می‌شود:

* **API_ID**
* **API_HASH**

این مقادیر را در فایل `.env` قرار دهید.

درصورت مشکل در دریافت API ID و API HASH مقادیر در کانال تلگرام قرار گرفته 
لینک : https://t.me/caffeinexz/3

---

## 🔐 اجرای اولیه

در اولین اجرا:

* شماره روبیکا را وارد کنید
* کد تایید را وارد کنید
* فایل سشن ذخیره می‌شود و در دفعات بعد نیاز نیست

---

## 📥 نحوه استفاده

1. وارد **بات تلگرام** شوید
2. فایل ارسال کنید
3. فایل به صورت خودکار در **Saved Messages روبیکا** ارسال می‌شود

---
