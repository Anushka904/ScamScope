# ScamScope Frontend — The Evidence Lab

React + Vite + TypeScript frontend for the ScamScope FastAPI backend.

## Current product boundary

The frontend calls these implemented routes:

- `GET /health`
- `POST /api/extract` with `multipart/form-data` field `file` or `text`
- `POST /api/verify` with JSON body `{ "extracted": ExtractedOffer }`

The Case Report displays the six Phase 4 check categories: domain age/RDAP, website reachability, TLS certificate, sender-domain consistency, PDF metadata and payment red flags. It does not invent risk scores, confidence, company ownership verification, persistent case history or relationship graphs. The report remains labelled **UNVERIFIED**.

A `CLEAR` result means only that one specific check did not observe its warning condition. It does not mean the offer is genuine. `UNAVAILABLE` and `NOT APPLICABLE` are distinct from `CLEAR` and are not counted as completed evidence.

## Design system

- Ink/charcoal base with restrained ember-orange light.
- Amber, teal and blue-grey state colors; every state also has text and an icon.
- Fraunces headlines, Inter interface text, DM Mono evidence labels.
- GSAP ScrollTrigger + Lenis for desktop scroll moments; reduced-motion and small screens use static/stacked layouts.
- No external image assets. Main visuals are CSS/SVG/HTML.

## Requirements and install

- Node.js 20.19+ or 22.12+ and npm.
- Existing ScamScope backend. Deterministic extraction is the default and does not need Gemini quota.
- Never put provider API keys into frontend env files.

From the repository root:

```powershell
cd frontend
npm install
npm run typecheck
npm test
npm run build
```

The API URL defaults to `http://127.0.0.1:8000`. To change it, edit `frontend/.env.local`:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_REQUEST_TIMEOUT_MS=900000
```

## Run locally

Open two VS Code terminals.

**Terminal 1 — backend:**

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Terminal 2 — frontend:**

```powershell
cd frontend
npm run dev
```

Open `http://127.0.0.1:5173`. Keep both terminals open.

## User flow

1. Landing page → Examine an offer.
2. Upload PNG/JPG/WEBP/PDF or paste offer text.
3. The frontend sends one extraction request to `/api/extract`.
4. Case report shows extracted claims and source excerpts.
5. The Case Report automatically calls `/api/verify` and displays six verification results in Check Trace.
6. Edit mode changes a local draft only. Use **Re-run checks** to submit the edited draft for fresh verification.
7. Download JSON to save the extraction and verification record; print/save PDF uses the browser print dialog.

## Pages

- `/` — Evidence Lab landing page.
- `/investigate` — file/text intake, preview, sample cases, loading/cancel and API error handling.
- `/case` — session-only extraction report, evidence excerpts, editable draft, verification trace, verification email, JSON export and print layout.
- `/accuracy` — metrics loaded from `public/data/accuracy.json`.
- `/cases` — case-board empty state; persistent case history/graph is not implemented.

## Verification limitations

- RDAP and website/TLS checks require network access and may return `UNAVAILABLE` when providers or DNS are unavailable.
- Website reachability and TLS validity do not confirm that a company owns a website.
- Sender-domain comparison checks consistency only against the domain stated in the submitted material.
- New domain age is a warning indicator, not proof of fraud.
- PDF metadata can be modified and is not an authenticity guarantee.
- Payment-demand findings depend on the extraction result and source text. An explicit upfront fee is a warning indicator, not a final legal determination.
- Reserved `.example`, `.test`, `.invalid`, `.localhost` and `.local` names are not sent to live RDAP/website/TLS checks.
- Image-only files are not OCR-processed by the local default extraction engine.
- Case data remains in router navigation state only; refreshing the report clears the active case.

See `../docs/api_contract.md` and `../FRONTEND_TEST_PLAN.md` for API semantics and acceptance tests.
