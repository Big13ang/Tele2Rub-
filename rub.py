import os
import re
import json
import time
import secrets
import string
import fcntl
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from rubpy import Client as RubikaClient
import requests
import pyzipper
from urllib.parse import urlparse
import threading

load_dotenv()

SESSION_NAME = os.getenv("RUBIKA_SESSION", "rubika_session").strip()

BASE_DIR = Path(__file__).resolve().parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
QUEUE_DIR = BASE_DIR / "queue"
QUEUE_FILE = QUEUE_DIR / "tasks.jsonl"
PROCESSING_FILE = QUEUE_DIR / "processing.json"
FAILED_FILE = QUEUE_DIR / "failed.jsonl"
STATUS_FILE = QUEUE_DIR / "status.jsonl"
URL_DIR = DOWNLOAD_DIR / "url"
CANCEL_FILE = QUEUE_DIR / "cancelled.jsonl"
QUEUE_LOCK_FILE = QUEUE_DIR / ".queue.lock"
AUTH_REQUEST_FILE = QUEUE_DIR / "auth_request.json"
AUTH_STATE_FILE = QUEUE_DIR / "auth_state.json"

MAX_RETRIES = 5
UPLOAD_TIMEOUT = 1800
TARGET = "me"

DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
QUEUE_DIR.mkdir(parents=True, exist_ok=True)
URL_DIR.mkdir(parents=True, exist_ok=True)
SESSION_DIR = BASE_DIR / "sessions"
SESSION_DIR.mkdir(parents=True, exist_ok=True)
SESSION = str(SESSION_DIR / SESSION_NAME)


def random_ascii_name(length: int = 26) -> str:
    chars = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))


def safe_extension(name: Optional[str], default: str = ".bin") -> str:
    suffix = Path((name or "").strip()).suffix.lower()
    suffix = re.sub(r"[^a-z0-9.]", "", suffix)
    if not suffix.startswith("."):
        suffix = f".{suffix}" if suffix else default
    if len(suffix) > 10:
        return default
    return suffix or default

def pretty_size(size) -> str:
    size = float(size or 0)
    units = ["B", "KB", "MB", "GB"]

    index = 0
    while size >= 1024 and index < len(units) - 1:
        size /= 1024
        index += 1

    return f"{size:.2f} {units[index]}"

def get_per_attempt_timeout(file_path: str) -> int:
    size_mb = Path(file_path).stat().st_size / (1024 * 1024)

    if size_mb < 100:
        return 180
    elif size_mb < 500:
        return 420
    elif size_mb < 1000:
        return 720
    else:
        return 1200
    
def eta_text(seconds) -> str:
    if not seconds or seconds <= 0:
        return "نامشخص"

    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60

    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def push_status(task: dict, text: str, status: str = "working", percent: float | None = None):
    payload = {
        "chat_id": task.get("chat_id"),
        "message_id": task.get("status_message_id"),
        "status": status,
        "text": text,
        "percent": percent,
        "time": time.time(),
    }

    with open(STATUS_FILE, "a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _extract(data, *keys):
    cur = data
    for key in keys:
        if isinstance(cur, dict):
            cur = cur.get(key)
        else:
            cur = getattr(cur, key, None)
        if cur is None:
            return None
    return cur


def process_auth_request():
    if not AUTH_REQUEST_FILE.exists():
        return
    try:
        req = json.loads(AUTH_REQUEST_FILE.read_text(encoding="utf-8"))
    except Exception:
        AUTH_REQUEST_FILE.unlink(missing_ok=True)
        return
    AUTH_REQUEST_FILE.unlink(missing_ok=True)

    chat_id = req.get("chat_id")
    message_id = req.get("status_message_id")
    task = {"chat_id": chat_id, "status_message_id": message_id}
    action = req.get("action")

    if action == "send_code":
        phone_number = str(req.get("phone_number", "")).strip()
        if not phone_number:
            push_status(task, "شماره معتبر نیست.", "failed")
            return
        client = RubikaClient(name=SESSION)
        try:
            result = client.send_code(phone_number)
            phone_code_hash = _extract(result, "phone_code_hash") or _extract(result, "data", "phone_code_hash")
            public_key = _extract(result, "public_key") or _extract(result, "data", "public_key")
            if not phone_code_hash or not public_key:
                raise RuntimeError("پارامترهای تایید دریافت نشد.")
            AUTH_STATE_FILE.write_text(
                json.dumps(
                    {
                        "phone_number": phone_number,
                        "phone_code_hash": phone_code_hash,
                        "public_key": public_key,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            push_status(task, "کد OTP ارسال شد. لطفا کد را وارد کنید.", "auth_wait_otp")
        except Exception as e:
            push_status(task, f"خطا در ارسال کد: {e}", "failed")
        finally:
            try:
                client.disconnect()
            except Exception:
                pass
    elif action == "verify_code":
        if not AUTH_STATE_FILE.exists():
            push_status(task, "درخواست OTP منقضی شده. دوباره ورود به روبیکا را شروع کنید.", "failed")
            return
        code = str(req.get("otp_code", "")).strip()
        state = json.loads(AUTH_STATE_FILE.read_text(encoding="utf-8"))
        client = RubikaClient(name=SESSION)
        try:
            client.sign_in(
                phone_code=code,
                phone_number=state["phone_number"],
                phone_code_hash=state["phone_code_hash"],
                public_key=state["public_key"],
            )
            AUTH_STATE_FILE.unlink(missing_ok=True)
            push_status(task, "✅ ورود به روبیکا موفق بود. حالا می‌توانید فایل ارسال کنید.", "done")
        except Exception as e:
            push_status(task, f"کد OTP نامعتبر یا منقضی شده: {e}", "failed")
        finally:
            try:
                client.disconnect()
            except Exception:
                pass

def is_cancelled(task: dict) -> bool:
    job_id = str(task.get("job_id", ""))

    if not job_id or not CANCEL_FILE.exists():
        return False

    with open(CANCEL_FILE, "r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue

            item = json.loads(line)
            if str(item.get("job_id")) == job_id:
                return True

    return False

def unique_path(path: Path) -> Path:
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    index = 1

    while True:
        candidate = path.with_name(f"{stem}_{index}{suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def has_session(session_name: str) -> bool:
    candidates = [
        Path(session_name),
        Path(f"{session_name}.session"),
        Path(f"{session_name}.sqlite"),
    ]
    return any(path.exists() for path in candidates)


def ensure_session():
    if has_session(SESSION):
        return
    raise RuntimeError("No session. Use bot login flow first.")


def send_document(file_path: str, caption: str = ""):
    client = RubikaClient(name=SESSION)

    try:
        client.start()
        return client.send_document(
            TARGET,
            file_path,
            caption=caption or ""
        )
    finally:
        try:
            client.disconnect()
        except Exception:
            pass

def send_with_timeout(file_path, caption, timeout, task_ref=None):
    result = {}
    error = {}

    upload_state = {"done": False}

    def target():
        try:
            result["data"] = send_document(file_path, caption)
        except Exception as e:
            error["err"] = e
        finally:
            upload_state["done"] = True

    def progress_target():
        fake_percent = 1.0
        while not upload_state["done"]:
            if task_ref:
                push_status(
                    task_ref,
                    "🔼 در حال آپلود در روبیکا...",
                    "uploading",
                    min(fake_percent, 95.0),
                )
            fake_percent += 2.5
            time.sleep(2)

    t = threading.Thread(target=target)
    p = threading.Thread(target=progress_target, daemon=True)
    t.start()
    p.start()
    t.join(timeout)

    if t.is_alive():
        raise RuntimeError("آپلود بیشتر از حد مجاز طول کشید و لغو شد.")

    if "err" in error:
        raise error["err"]

    return result.get("data")

def send_with_retry(file_path: str, caption: str = "", task: dict | None = None):
    last_error = None
    start_time = time.time()

    for attempt in range(1, MAX_RETRIES + 1):

        if time.time() - start_time > UPLOAD_TIMEOUT:
            raise RuntimeError("آپلود بیشتر از حد مجاز طول کشید و لغو شد.")

        if task and is_cancelled(task):
            raise RuntimeError("ارسال لغو شد.")

        try:
            if task:
                push_status(
                    task,
                    f"🔼 در حال آپلود در روبیکا...\n\n"
                    f"🔴 تلاش {attempt} از {MAX_RETRIES}\n\n"
                    f"برای لغو ارسال:\n"
                    f"`/del {task.get('job_id')}`",
                    "uploading"
                )

            elapsed = time.time() - start_time
            remaining = UPLOAD_TIMEOUT - elapsed

            if remaining <= 0:
                raise RuntimeError("آپلود بیشتر از ۳۰ دقیقه طول کشید و لغو شد.")

            per_attempt = min(get_per_attempt_timeout(file_path), remaining)

            return send_with_timeout(file_path, caption, per_attempt, task)

        except Exception as e:
            last_error = e
            error_text = str(e).lower()

            transient = any(
                key in error_text
                for key in [
                    "502", "503", "bad gateway", "timeout",
                    "cannot connect", "connection reset",
                    "temporarily unavailable",
                    "error uploading chunk",
                    "unexpected mimetype",
                ]
            )

            if transient and attempt < MAX_RETRIES:

                if task and is_cancelled(task):
                    raise RuntimeError("ارسال لغو شد.")

                if task:
                    push_status(
                        task,
                        f"ارتباط با روبیکا ناپایدار بود...\n"
                        f"دوباره تلاش می‌کنم ({attempt + 1})",
                        "uploading"
                    )

                time.sleep(3)
                continue

    raise last_error if last_error else RuntimeError("Upload failed.")

def download_url(task: dict) -> Path:
    url = task.get("url", "").strip()
    if not url:
        raise RuntimeError("URL خالیه")

    push_status(task, "در حال دانلود ...", "downloading", 0)

    try:
        resp = requests.get(url, stream=True, timeout=(10, 60), allow_redirects=True)
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        raise RuntimeError("لینک جواب نداد")
    except requests.exceptions.ConnectionError:
        raise RuntimeError("مشکل شبکه")
    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response else "نامشخص"
        raise RuntimeError(f"دانلود انجام نشد. کد خطا: {code}")
    
    cd = resp.headers.get("content-disposition", "")
    match = re.findall(r'filename="(.+?)"', cd)
    name = match[0] if match else Path(urlparse(url).path).name
    suffix = safe_extension(name)
    name = f"{random_ascii_name()}{suffix}"

    target = unique_path(URL_DIR / name)
    total = int(resp.headers.get("content-length") or 0)
    downloaded, last_update, started = 0, 0, time.time()

    with open(target, "wb") as f:
        for chunk in resp.iter_content(1024 * 1024):
            if not chunk:
                continue
            f.write(chunk)
            downloaded += len(chunk)

            now = time.time()
            if now - last_update < 3 and downloaded < total:
                continue
            last_update = now

            speed = downloaded / max(now - started, 1)
            eta = (total - downloaded) / speed if total and speed else None
            percent = downloaded * 100 / total if total else None

            text = f"داره دانلود میکنه...\n\n{pretty_size(downloaded)}"
            if total:
                text += f" از {pretty_size(total)}"
            text += f"\nسرعت: {pretty_size(speed)}/s"
            if eta:
                text += f"\nمونده: {eta_text(eta)}"

            push_status(task, text, "downloading", percent)

    if not target.exists() or target.stat().st_size == 0:
        raise RuntimeError("فایل دانلود نشد")

    task["file_name"] = target.name
    task["file_size"] = target.stat().st_size
    return target

def make_zip_with_password(file_path: Path, password: str) -> Path:
    zip_path = unique_path(file_path.with_suffix(file_path.suffix + ".zip"))

    with pyzipper.AESZipFile(
        zip_path,
        "w",
        compression=pyzipper.ZIP_STORED,
        encryption=pyzipper.WZ_AES,
    ) as zip_file:
        zip_file.setpassword(password.encode("utf-8"))
        zip_file.write(file_path, arcname=file_path.name)

    return zip_path

def pop_first_task():
    with open(QUEUE_LOCK_FILE, "a+", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if not QUEUE_FILE.exists():
            return None

        with open(QUEUE_FILE, "r", encoding="utf-8") as file:
            lines = [line for line in file if line.strip()]

        if not lines:
            return None

        first_line = lines[0]
        remaining = lines[1:]

        with open(QUEUE_FILE, "w", encoding="utf-8") as file:
            file.writelines(remaining)

        return json.loads(first_line)


def save_processing(task: dict) -> None:
    with open(PROCESSING_FILE, "w", encoding="utf-8") as file:
        json.dump(task, file, ensure_ascii=False, indent=2)


def clear_processing() -> None:
    if PROCESSING_FILE.exists():
        PROCESSING_FILE.unlink()


def append_failed(task: dict, error: str) -> None:
    payload = {"task": task, "error": error}
    with open(FAILED_FILE, "a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False) + "\n")

def process_task(task: dict):
    task_type = task.get("type")
    caption = task.get("caption", "")
    safe_mode = task.get("safe_mode", False)
    zip_password = task.get("zip_password", "")

    local_path: Path | None = None

    if task_type == "local_file":
        local_path = Path(task.get("path", ""))

        if not local_path.exists():
            raise RuntimeError("Local file not found.")

    elif task_type == "direct_url":
        local_path = download_url(task)

    else:
        raise RuntimeError("Unknown task type.")

    if safe_mode and zip_password:
        push_status(task, "در حال تبدیل به فایل zip ...", "processing")

        try:
            zipped = make_zip_with_password(local_path, zip_password)
        finally:
            try:
                if local_path.exists():
                    local_path.unlink()
            except Exception:
                pass

        send_path = zipped

    else:
        send_path = local_path

    try:
        if is_cancelled(task):
            raise RuntimeError("ارسال لغو شد.")

        send_with_retry(str(send_path), caption, task)

        push_status(
            task,
            "فایل با موفقیت در روبیکا آپلود شد.",
            "done"
        )

    finally:
        try:
            if send_path and send_path.exists():
                send_path.unlink()
        except Exception:
            pass

def worker_loop():
    print("Rubika worker started.")

    while True:
        process_auth_request()
        task = pop_first_task()

        if not task:
            time.sleep(0.2)
            continue

        save_processing(task)

        try:
            ensure_session()
            process_task(task)
        except Exception as e:
            append_failed(task, str(e))
            push_status(task, f"خطا: {str(e)}", "failed")
        finally:
            clear_processing()

if __name__ == "__main__":
    worker_loop()
