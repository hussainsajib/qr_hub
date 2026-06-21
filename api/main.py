import base64
import io
import re
from urllib.parse import quote

import functions_framework
import qrcode
from PIL import Image
from qrcode.image.pil import PilImage

ALLOWED_ORIGINS = {"https://qrhub.tech", "https://www.qrhub.tech"}
MAX_DATA_LEN = 2048
MAX_LOGO_BYTES = 512 * 1024  # 512 KB decoded


def _is_hex_color(s):
    return bool(re.match(r'^#[0-9A-Fa-f]{6}$', s))


def _esc_wifi(s):
    """Escape special characters in WiFi SSID/password per IEEE 802.11 QR spec."""
    for ch in ('\\', ';', ',', '"'):
        s = s.replace(ch, '\\' + ch)
    return s


def _build_data(qr_type, body):
    """Return the string to encode, or raise ValueError with a user-facing message."""
    def req(key, label):
        val = (body.get(key) or "").strip()
        if not val:
            raise ValueError(f"Missing required field: {label}")
        return val

    def opt(key):
        return (body.get(key) or "").strip()

    if qr_type == "url":
        return req("url", "URL")

    elif qr_type == "wifi":
        ssid = req("ssid", "network name (SSID)")
        password = opt("password")
        security = opt("security").upper() or "WPA"
        if security not in ("WPA", "WEP", ""):
            security = "WPA"
        hidden = "true" if body.get("hidden") else "false"
        return f"WIFI:S:{_esc_wifi(ssid)};T:{security};P:{_esc_wifi(password)};H:{hidden};;"

    elif qr_type == "vcard":
        name = req("name", "full name")
        lines = ["BEGIN:VCARD", "VERSION:3.0", f"FN:{name}"]
        phone = opt("phone")
        email = opt("email")
        org = opt("org")
        url = opt("url")
        if phone: lines.append(f"TEL:{phone}")
        if email: lines.append(f"EMAIL:{email}")
        if org:   lines.append(f"ORG:{org}")
        if url:   lines.append(f"URL:{url}")
        lines.append("END:VCARD")
        return "\n".join(lines)

    elif qr_type == "sms":
        phone = req("phone", "phone number")
        message = opt("message")
        return f"SMSTO:{phone}:{message}"

    elif qr_type == "email":
        email = req("email", "email address")
        subject = opt("subject")
        body_text = opt("body")
        params = []
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


@functions_framework.http
def qr_handler(request):
    origin = request.headers.get("Origin", "")
    cors_origin = origin if origin in ALLOWED_ORIGINS else "https://qrhub.tech"

    if request.method == "OPTIONS":
        return (
            "",
            204,
            {
                "Access-Control-Allow-Origin": cors_origin,
                "Access-Control-Allow-Methods": "POST",
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Max-Age": "3600",
            },
        )

    if request.method != "POST":
        return ("Method not allowed.", 405)

    cors_headers = {"Access-Control-Allow-Origin": cors_origin}

    try:
        body = request.get_json(silent=True) or {}
        qr_type = (body.get("type") or "url").strip().lower()

        data = _build_data(qr_type, body)
        if len(data) > MAX_DATA_LEN:
            return ("Input data is too long.", 400, cors_headers)

        box_size = max(4, min(int(body.get("size", 10)), 30))
        border   = max(0, min(int(body.get("border", 4)), 10))

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
            logo_bytes = base64.b64decode(logo_b64)
            if len(logo_bytes) > MAX_LOGO_BYTES:
                return ("Logo exceeds 512 KB.", 400, cors_headers)
            logo = Image.open(io.BytesIO(logo_bytes)).convert("RGBA")

            qr_w = img.size[0]
            max_size = int(qr_w * 0.28)
            logo.thumbnail((max_size, max_size), Image.LANCZOS)

            # White padded background behind logo for scan contrast
            pad = max(4, int(qr_w * 0.015))
            bg_pad = Image.new("RGBA",
                (logo.width + 2 * pad, logo.height + 2 * pad),
                (255, 255, 255, 255))
            bg_pad.paste(logo, (pad, pad), logo)

            pos = ((qr_w - bg_pad.width) // 2, (qr_w - bg_pad.height) // 2)
            img_rgba = img.convert("RGBA")
            img_rgba.paste(bg_pad, pos, bg_pad)
            img = img_rgba.convert("RGB")

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        return (buf.read(), 200, {"Content-Type": "image/png", **cors_headers})

    except ValueError as exc:
        return (str(exc), 400, cors_headers)
    except Exception as exc:
        return (str(exc), 500, cors_headers)
