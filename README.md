# QR Hub — Free QR Code Generator

> **Live at [qrhub.tech](https://qrhub.tech)** — no signup, no watermark, no limits.

Generate QR codes for URLs, WiFi networks, contacts, SMS, email, phone numbers, and plain text — directly in the browser. Customize colors, add a logo, and download a high-resolution PNG in seconds.

---

## Features

- **7 QR types** — URL · WiFi · vCard · SMS · Email · Text · Phone
- **Live preview** — QR updates as you type (debounced, no extra clicks)
- **Custom colors** — foreground and background color pickers
- **Logo overlay** — centered logo with auto-upgraded error correction (H-level)
- **High-res PNG download** — print-ready output, adjustable box size and border
- **Accessible** — ARIA roles, keyboard navigation, skip link, screen-reader support
- **No backend tracking** — QR data is processed server-side and immediately discarded; nothing is stored

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Static HTML / CSS / JS — hosted on Vercel |
| Backend | Python 3.11, Google Cloud Functions |
| QR generation | `qrcode` + `Pillow` |
| Security | Per-IP sliding-window rate limiting, input validation, security headers |

## Project Structure

```
qr_code_generator/
├── frontend/
│   ├── index.html          # Main page — SEO, tool UI, FAQ, structured data
│   ├── favicon.svg         # SVG favicon (inline gradient)
│   ├── privacy.html
│   ├── terms.html
│   ├── sitemap.xml
│   ├── robots.txt
│   └── vercel.json
└── api/
    ├── main.py             # Cloud Function handler
    └── requirements.txt
```

## Local Development

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r api/requirements.txt

cd api
functions-framework --target qr_handler --debug
# → http://localhost:8080
```

In `frontend/index.html`, temporarily point `API_URL` at `http://localhost:8080` to test end-to-end.

## Deployment

CI/CD via GitHub Actions (`.github/workflows/deploy.yml`). Push to `master` automatically deploys:
- `frontend/` changes → Vercel
- `api/` changes → Google Cloud Functions

### First-time: Vercel

1. Import repo at [vercel.com](https://vercel.com), set root directory to `frontend/`
2. Add custom domain `qrhub.tech` in project settings
3. Run `vercel link` inside `frontend/` to get org/project IDs
4. Add GitHub secrets: `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`

### First-time: Google Cloud Functions (Workload Identity — no long-lived keys)

```bash
# Service account
gcloud iam service-accounts create github-actions \
  --display-name "GitHub Actions deployer"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:github-actions@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/cloudfunctions.developer"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:github-actions@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"

# Workload Identity Pool
gcloud iam workload-identity-pools create github \
  --location=global --display-name="GitHub Actions pool"

gcloud iam workload-identity-pools providers create-oidc github-provider \
  --location=global \
  --workload-identity-pool=github \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository=='YOUR_GITHUB_USERNAME/YOUR_REPO_NAME'"

gcloud iam service-accounts add-iam-policy-binding \
  github-actions@YOUR_PROJECT_ID.iam.gserviceaccount.com \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/YOUR_PROJECT_NUMBER/locations/global/workloadIdentityPools/github/attribute.repository/YOUR_GITHUB_USERNAME/YOUR_REPO_NAME"
```

GitHub secrets needed: `GCP_PROJECT_ID`, `GCP_SERVICE_ACCOUNT`, `GCP_WORKLOAD_IDENTITY_PROVIDER`

## API Reference

### `POST /`

**Request (JSON):**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | `"url"` | `url` · `wifi` · `vcard` · `sms` · `email` · `text` · `phone` |
| `url` | string | — | URL to encode (required for `url` type) |
| `ssid` | string | — | Network name (required for `wifi`) |
| `password` | string | — | WiFi password |
| `security` | string | `"WPA"` | `WPA` · `WEP` · `""` |
| `name` | string | — | Full name (required for `vcard`) |
| `phone` | string | — | Phone number |
| `email` | string | — | Email address |
| `org` | string | — | Organisation |
| `message` | string | — | SMS body (for `sms`) |
| `subject` | string | — | Email subject |
| `body` | string | — | Email body |
| `text` | string | — | Plain text (required for `text`) |
| `size` | integer | `10` | Box size in pixels (4–30) |
| `border` | integer | `4` | Border width in modules (0–10) |
| `fg_color` | string | `"#000000"` | Foreground hex color |
| `bg_color` | string | `"#ffffff"` | Background hex color |
| `logo` | string | — | Base64-encoded logo image (max 512 KB) |

**Response:** `image/png`

**Rate limit:** 30 requests / 60 seconds per IP. Exceeding returns `429` with a `Retry-After` header.

## License

MIT — see [LICENSE](LICENSE)
