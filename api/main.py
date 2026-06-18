import io

import functions_framework
import qrcode
from qrcode.image.pil import PilImage

ALLOWED_ORIGINS = {"https://qrhub.tech", "https://www.qrhub.tech"}


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
        url = (body.get("url") or "").strip()
        if not url:
            return ("Missing 'url' in request body.", 400, cors_headers)

        box_size = max(4, min(int(body.get("size", 10)), 30))
        border   = max(0, min(int(body.get("border", 4)), 10))

        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=box_size,
            border=border,
        )
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(image_factory=PilImage).get_image()

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        return (buf.read(), 200, {"Content-Type": "image/png", **cors_headers})

    except Exception as exc:
        return (str(exc), 500, cors_headers)
