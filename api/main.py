import io
from urllib.parse import quote

import functions_framework
import qrcode
from qrcode.image.pil import PilImage

ALLOWED_ORIGINS = {"https://qrhub.tech", "https://www.qrhub.tech"}
MAX_DATA_LEN = 2048


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

        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=box_size,
            border=border,
        )
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(image_factory=PilImage).get_image()

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        return (buf.read(), 200, {"Content-Type": "image/png", **cors_headers})

    except ValueError as exc:
        return (str(exc), 400, cors_headers)
    except Exception as exc:
        return (str(exc), 500, cors_headers)
