# Promotion Templates

Ready-to-paste copy for directory submissions. Replace any `[...]` placeholders before submitting.

---

## Product Hunt

**Name:** QR Hub

**Tagline:** Free QR code generator — 7 types, custom colors, logo overlay

**Description:**
QR Hub lets you generate QR codes for URLs, WiFi networks, vCards, SMS, email, phone numbers, and plain text — all free, no signup, no watermark.

What makes it different:
- **Logo overlay** — center your brand logo on any QR code; error correction auto-upgrades to stay scannable
- **Live preview** — QR updates as you type, no extra clicks needed
- **Custom colors** — match your brand's exact color scheme
- **Privacy-first** — nothing is stored server-side; codes are generated and discarded instantly

Built with Python (Cloud Functions) + plain HTML/CSS/JS. Under 1 second to generate, print-ready PNG output.

**URL:** https://qrhub.tech

**Topics:** Productivity, Design Tools, Developer Tools

---

## AlternativeTo

**App name:** QR Hub

**Description:**
Free online QR code generator supporting 7 types: URL, WiFi, vCard (contact), SMS, email, phone, and plain text. Customize colors and add a logo overlay. No account required, no watermarks. Instant PNG download.

**URL:** https://qrhub.tech

**Alternatives to:** QRCode Monkey, QR Code Generator (qr-code-generator.com), Bitly QR

---

## Reddit Posts

### r/entrepreneur / r/SideProject

**Title:** I built a free QR code generator — 7 types, logo overlay, custom colors. Looking for feedback.

**Body:**
Hey everyone, I built [QR Hub](https://qrhub.tech) — a free QR code generator that supports 7 types: URL, WiFi, vCard (contact card), SMS, email, phone, and plain text.

A few things I'm proud of:
- **Logo overlay** — upload your logo and it centers it on the QR code; error correction automatically bumps up to 30% so it stays scannable
- **Live preview** — the QR code updates as you type, no clicking Generate each time
- **Custom colors** — foreground and background color pickers for branded QR codes
- No signup, no watermark, no limits

I'd love honest feedback — is there a type you'd want added? Anything feel clunky?

Tech stack: Python Cloud Functions for the API, plain HTML/CSS/JS for the frontend. Deployed on GCP + Vercel.

---

### r/webdev

**Title:** Built a QR code generator using Python Cloud Functions + vanilla JS — here's what I learned

**Body:**
I built [QR Hub](https://qrhub.tech) as a side project to learn GCP Cloud Functions. A few things worth sharing:

1. **Logo overlay on QR codes** — you need to auto-upgrade error correction to H (30%) when a logo is present, otherwise it won't scan reliably at smaller sizes. I let the `qrcode` library handle this.

2. **Decompression bombs** — set `Image.MAX_IMAGE_PIXELS = 10_000_000` in Pillow before opening any user-uploaded image, or a crafted PNG can exhaust server memory.

3. **Rate limiting without Redis** — I implemented a sliding-window counter in a module-level dict with a threading lock. Works fine for a single Cloud Function instance; wouldn't scale to multiple replicas without a shared store.

4. **CORS on error responses** — easy to miss: if you return a 405 or 429 before setting CORS headers, the browser blocks the error text and shows a generic network error instead.

Happy to answer questions. Live at https://qrhub.tech.

---

## Futurepedia / There's An AI For That

*(Submit once business card scan feature is live)*

**Name:** QR Hub

**Description:** Free QR code generator with AI-powered business card scanning. Upload a photo of any business card and QR Hub extracts the contact details and generates a vCard QR code instantly — powered by Gemini.

**Category:** Productivity, Image-to-Text

**URL:** https://qrhub.tech

---

## "Best QR Code Generator" Roundup Blogs

Search Google for: `"best free qr code generator" 2024 OR 2025`

For each result, find the author's contact or "suggest a tool" page and send:

> Hi [Name],
>
> I came across your roundup of free QR code generators and wanted to suggest QR Hub (https://qrhub.tech).
>
> It supports 7 QR types (URL, WiFi, vCard, SMS, email, phone, text), lets users add a custom logo overlay with automatic error correction, and requires no signup or watermark. It's completely free.
>
> Happy to provide a screenshot or any other details if helpful.
>
> Best,
> [Your name]
