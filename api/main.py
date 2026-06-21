import base64
import io
import json
import logging
import re
import threading
import time
from urllib.parse import quote

import functions_framework
import qrcode
from PIL import Image
from qrcode.image.pil import PilImage

# ── tunables ────────────────────────────────────────────────────────────────
ALLOWED_ORIGINS  = {"https://qrhub.tech", "https://www.qrhub.tech"}
MAX_REQUEST_BODY = 1_000_000          # 1 MB raw body (base64 logo ≈ 700 KB max)
MAX_DATA_LEN     = 2048               # encoded QR string length
MAX_LOGO_BYTES   = 512 * 1024         # 512 KB decoded logo
RATE_LIMIT       = 30                 # requests per window per IP
RATE_WINDOW      = 60                 # sliding window in seconds

ALLOWED_IMG_FORMATS = {"PNG", "JPEG", "GIF", "WEBP", "BMP", "ICO"}
Image.MAX_IMAGE_PIXELS = 10_000_000   # decompression-bomb guard (~10 MP)

# Per-field character limits applied before encoding
_FIELD_LIMITS = {
    "url": 2048, "ssid": 32,  "password": 63,  "name": 128,
    "phone": 20, "email": 254, "org": 128,      "message": 160,
    "subject": 256, "body": 1000, "text": 2000,
}

# Security headers attached to every response
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}

# ── rate limiter ─────────────────────────────────────────────────────────────
_rate_lock:  threading.Lock       = threading.Lock()
_rate_store: dict[str, list[float]] = {}


def _check_rate_limit(ip: str) -> tuple[bool, int]:
    """Sliding-window counter. Returns (allowed, retry_after_seconds)."""
    now    = time.monotonic()
    cutoff = now - RATE_WINDOW
    with _rate_lock:
        window = [t for t in _rate_store.get(ip, []) if t > cutoff]
        if len(window) >= RATE_LIMIT:
            retry_after = int(RATE_WINDOW - (now - window[0])) + 1
            _rate_store[ip] = window          # store pruned list (don't add)
            return False, retry_after
        window.append(now)
        _rate_store[ip] = window
        # Prune the whole store once it grows large to avoid unbounded memory
        if sum(len(v) for v in _rate_store.values()) > 50_000:
            _rate_store.clear()
        return True, 0


# ── input helpers ─────────────────────────────────────────────────────────────
def _is_hex_color(s: str) -> bool:
    return bool(re.match(r'^#[0-9A-Fa-f]{6}$', s))


def _esc_wifi(s: str) -> str:
    """Escape special characters in WiFi SSID/password per IEEE 802.11 QR spec."""
    for ch in ('\\', ';', ',', '"'):
        s = s.replace(ch, '\\' + ch)
    return s


def _build_data(qr_type: str, body: dict) -> str:
    """Return the string to encode, or raise ValueError with a user-facing message."""

    def req(key: str, label: str) -> str:
        raw = (body.get(key) or "").strip()
        if not raw:
            raise ValueError(f"Missing required field: {label}")
        limit = _FIELD_LIMITS.get(key, 500)
        if len(raw) > limit:
            raise ValueError(f"{label} must be {limit} characters or fewer.")
        return raw

    def opt(key: str) -> str:
        raw = (body.get(key) or "").strip()
        return raw[:_FIELD_LIMITS.get(key, 500)]

    if qr_type == "url":
        return req("url", "URL")

    elif qr_type == "wifi":
        ssid     = req("ssid", "network name (SSID)")
        password = opt("password")
        security = opt("security").upper() or "WPA"
        if security not in ("WPA", "WEP", ""):
            security = "WPA"
        hidden = "true" if body.get("hidden") else "false"
        return f"WIFI:S:{_esc_wifi(ssid)};T:{security};P:{_esc_wifi(password)};H:{hidden};;"

    elif qr_type == "vcard":
        name  = req("name", "full name")
        lines = ["BEGIN:VCARD", "VERSION:3.0", f"FN:{name}"]
        phone = opt("phone")
        email = opt("email")
        org   = opt("org")
        url   = opt("url")
        if phone: lines.append(f"TEL:{phone}")
        if email: lines.append(f"EMAIL:{email}")
        if org:   lines.append(f"ORG:{org}")
        if url:   lines.append(f"URL:{url}")
        lines.append("END:VCARD")
        return "\n".join(lines)

    elif qr_type == "sms":
        phone   = req("phone", "phone number")
        message = opt("message")
        return f"SMSTO:{phone}:{message}"

    elif qr_type == "email":
        email     = req("email", "email address")
        subject   = opt("subject")
        body_text = opt("body")
        params    = []
        if subject:   params.append(f"subject={quote(subject)}")
        if body_text: params.append(f"body={quote(body_text)}")
        data = f"mailto:{email}"
        if params:
            data += "?" + "&".join(params)
        return data

    elif qr_type == "text":
        return req("text", "text content")

    elif qr_type == "phone":
        return f"tel:{req('phone', 'phone number')}"

    else:
        raise ValueError(f"Unknown QR type: {qr_type!r}")


# ── handler ───────────────────────────────────────────────────────────────────
@functions_framework.http
def qr_handler(request):
    origin      = request.headers.get("Origin", "")
    cors_origin = origin if origin in ALLOWED_ORIGINS else "https://qrhub.tech"

    base_headers = {
        "Access-Control-Allow-Origin": cors_origin,
        **_SECURITY_HEADERS,
    }

    # ── CORS preflight ────────────────────────────────────────────────────
    if request.method == "OPTIONS":
        return ("", 204, {
            **base_headers,
            "Access-Control-Allow-Methods": "POST",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "3600",
        })

    if request.method != "POST":
        return ("Method not allowed.", 405, base_headers)

    # ── rate limiting ─────────────────────────────────────────────────────
    xff       = request.headers.get("X-Forwarded-For", "")
    client_ip = xff.split(",")[0].strip() if xff else (request.remote_addr or "unknown")

    allowed, retry_after = _check_rate_limit(client_ip)
    if not allowed:
        logging.warning("rate_limited ip=%s", client_ip)
        return ("Too many requests — please slow down.", 429, {
            **base_headers,
            "Retry-After": str(retry_after),
        })

    # ── content-type guard ────────────────────────────────────────────────
    if not (request.content_type or "").startswith("application/json"):
        return ("Content-Type must be application/json.", 415, base_headers)

    # ── body size guard ───────────────────────────────────────────────────
    raw_body = request.get_data(as_text=False)
    if len(raw_body) > MAX_REQUEST_BODY:
        logging.warning("oversized_body ip=%s bytes=%d", client_ip, len(raw_body))
        return ("Request body too large.", 413, base_headers)

    # ── JSON parse ────────────────────────────────────────────────────────
    try:
        body = json.loads(raw_body)
    except (json.JSONDecodeError, ValueError):
        return ("Invalid JSON.", 400, base_headers)

    if not isinstance(body, dict):
        return ("Request body must be a JSON object.", 400, base_headers)

    # ── main logic ────────────────────────────────────────────────────────
    try:
        qr_type = (body.get("type") or "url").strip().lower()
        data    = _build_data(qr_type, body)

        if len(data) > MAX_DATA_LEN:
            return ("Encoded data is too long.", 400, base_headers)

        try:
            box_size = max(4, min(int(body.get("size", 10)), 30))
            border   = max(0, min(int(body.get("border", 4)), 10))
        except (TypeError, ValueError):
            return ("size and border must be integers.", 400, base_headers)

        fg_color = (body.get("fg_color") or "#000000").strip()
        bg_color = (body.get("bg_color") or "#ffffff").strip()
        if not _is_hex_color(fg_color): fg_color = "#000000"
        if not _is_hex_color(bg_color): bg_color = "#ffffff"

        logo_b64 = (body.get("logo") or "").strip()
        has_logo = bool(logo_b64)
        error_correction = (
            qrcode.constants.ERROR_CORRECT_H if has_logo
            else qrcode.constants.ERROR_CORRECT_L
        )

        qr = qrcode.QRCode(
            version=None,
            error_correction=error_correction,
            box_size=box_size,
            border=border,
        )
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(
            image_factory=PilImage,
            fill_color=fg_color,
            back_color=bg_color,
        ).get_image()

        if has_logo:
            try:
                logo_bytes = base64.b64decode(logo_b64, validate=True)
            except Exception:
                return ("Logo is not valid base64.", 400, base_headers)

            if len(logo_bytes) > MAX_LOGO_BYTES:
                return ("Logo exceeds 512 KB.", 400, base_headers)

            # Validate format before full decode (catches non-image payloads)
            probe = Image.open(io.BytesIO(logo_bytes))
            if probe.format not in ALLOWED_IMG_FORMATS:
                return (
                    "Unsupported logo format. Use PNG, JPEG, GIF, WEBP, or BMP.",
                    400, base_headers,
                )
            probe.close()

            logo  = Image.open(io.BytesIO(logo_bytes)).convert("RGBA")
            qr_w  = img.size[0]
            logo.thumbnail((int(qr_w * 0.28), int(qr_w * 0.28)), Image.LANCZOS)

            pad    = max(4, int(qr_w * 0.015))
            bg_pad = Image.new("RGBA",
                (logo.width + 2 * pad, logo.height + 2 * pad),
                (255, 255, 255, 255))
            bg_pad.paste(logo, (pad, pad), logo)

            pos      = ((qr_w - bg_pad.width) // 2, (qr_w - bg_pad.height) // 2)
            img_rgba = img.convert("RGBA")
            img_rgba.paste(bg_pad, pos, bg_pad)
            img = img_rgba.convert("RGB")

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        return (buf.read(), 200, {"Content-Type": "image/png", **base_headers})

    except ValueError as exc:
        return (str(exc), 400, base_headers)
    except Exception:
        # Never leak internal details — log server-side only
        logging.exception("internal_error ip=%s", client_ip)
        return ("An internal error occurred.", 500, base_headers)
