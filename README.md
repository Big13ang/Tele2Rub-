# 🚀 Tele2Rub

انتقال خودکار فایل از تلگرام به روبیکا با صف پایدار + اجرای کامل با Docker.

---

## ✅ اجرای سریع با Docker (فقط همین)

### 1) دریافت پروژه

```bash
git clone https://github.com/Big13ang/Tele2Rub-.git
cd Tele2Rub-
```

### 2) ساخت فایل `.env`

```env
API_ID=...
API_HASH=...
BOT_TOKEN=...
RUBIKA_SESSION=rubsession
```

### 3) اجرا

```bash
docker compose up -d --build
```

### 4) مشاهده لاگ

```bash
docker compose logs -f
```

### 5) ورود اولیه روبیکا (داخل خود بات)

1. داخل بات بزنید: `/rubika_login` یا `ورود به روبیکا`
2. شماره را بفرستید
3. کد OTP را بفرستید
4. سشن ذخیره می‌شود

---

## 🔄 دستورات ضروری

- ری‌استارت سرویس + پاکسازی صف از داخل بات:

```text
/restart
```

- پاکسازی کل صف:

```text
/delall
```

- حذف یک آیتم از صف:

```text
/del <job_id>
```

---

## ⬆️ آپدیت به آخرین نسخه

```bash
git pull
docker compose up -d --build
```

---

## 📦 انتشار خودکار Docker Image روی GHCR

Workflow آماده است و روی push به `main` یا tag مثل `v1.0.0` ایمیج می‌سازد و push می‌کند:

```text
.github/workflows/docker-publish.yml
```

Image:

```text
ghcr.io/big13ang/tele2rub-:latest
```
