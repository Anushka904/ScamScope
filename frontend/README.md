# ScamScope Frontend — The Evidence Lab

React + Vite + TypeScript frontend for the existing ScamScope FastAPI backend.

## Current product boundary

The frontend calls only routes already present in the merged Phase 3 backend:

- `GET /health`
- `POST /api/extract` with `multipart/form-data` field `file` **or** `text`

The frontend does not modify the backend. It does not invent a risk score, confidence percentage, domain-age/SSL/sender-reputation results, PDF page coordinates, duration/work-mode fields, case persistence or a case graph. Those require future backend/API changes.

The report is explicitly labelled **UNVERIFIED**. An extraction being `complete` means the extraction request completed; it does not mean the offer is genuine.

## Design system

- Ink/charcoal base with restrained ember-orange light.
- Amber, teal and blue-grey state colors; every state also has text and an icon.
- Fraunces headlines, Inter interface text, DM Mono evidence labels.
- GSAP ScrollTrigger + Lenis for three desktop scroll moments: scanner sweep, investigation trace and verdict reveal.
- `prefers-reduced-motion` and small screens use static/stacked layouts.
- No external image assets. Main visuals are CSS/SVG/HTML document mockups.

## Requirements

- Node.js 20.19+ or 22.12+ and npm.
- Existing ScamScope backend remains in the repository root. Gemini is optional and disabled by default; no API key is required.
- Never put Gemini or other provider API keys into frontend env files.

## Install

From the repository root:

```powershell
cd frontend
if (!(Test-Path .env.local)) { Copy-Item .env.example .env.local }
npm install
```

Then run the checks:

```powershell
npm run typecheck
npm test
npm run build
```

The API URL defaults to `http://127.0.0.1:8000`. To change it, edit `frontend/.env.local`:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_REQUEST_TIMEOUT_MS=900000
```

`VITE_REQUEST_TIMEOUT_MS` is the browser's wait limit, not a provider timeout. The default local rule engine normally completes quickly. Stopping the browser wait does not guarantee the server-side request stopped.

## Run locally

Open two VS Code terminals.

**Terminal 1 — backend** (from repository root):

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Terminal 2 — frontend** (from repository root):

```powershell
cd frontend
npm run dev
```

Open `http://127.0.0.1:5173`.

## User flow

1. Landing page → Examine an offer.
2. Upload PNG/JPG/WEBP/PDF (10 MB frontend limit; backend remains authoritative) or paste offer text.
3. Optionally load one of the fictional sample messages.
4. The frontend sends exactly one request to `/api/extract`.
5. The case page renders the normalized extraction, payment/urgency phrases, source excerpts, warnings and the original input preview.
6. Edit mode changes a local draft only. JSON export marks local edits as not reverified. Print / Save PDF opens the browser print dialog.

## Pages

- `/` — cinematic Evidence Lab landing page and scroll story.
- `/investigate` — file/text intake, preview, API connection state, sample cases, loading/cancel state and API error handling.
- `/case` — session-only extraction report, payment/urgency phrases, evidence excerpts, editable local draft, verification email, JSON export and print layout.
- `/accuracy` — metrics loaded from `public/data/accuracy.json`.
- `/cases` — case-board empty state; persistent case graph is not implemented.

## Accuracy data

`public/data/accuracy.json` starts with null metrics and `status: "not_published"`. Replace null values only with metrics from a documented evaluation. `precision` and `recall` are proportions from `0` to `1`; for example, `0.91` means 91%. Never enter invented metrics.

## Privacy and limitations

- Case data is held in router navigation state only; refreshing the report clears the session.
- The uploaded document/text goes to the local FastAPI backend. By default, extraction is local and does not call an external AI provider. If `GEMINI_ENABLED=true` is deliberately set in the repository-root `.env`, the backend may forward submitted content to Google Gemini.
- Downloaded JSON may contain personal data from the submitted offer. Store and share it carefully.
- The current extraction schema does not include duration or work mode even when those appear in the text. The UI calls this out instead of deriving fields without backend evidence.
- No separate `/api/analyze`, `/api/history` or `/api/investigations/{id}` endpoint is called because these are not implemented in Phase 3.

See `../FRONTEND_TEST_PLAN.md` for manual end-to-end and edge-case checks.
