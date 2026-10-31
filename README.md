# ScamScope

Evidence-led analysis of suspicious internship and job offers. The current product includes deterministic extraction (Phase 3) and a provenance-aware independent verification layer (Phase 4). It deliberately does not assign a fraud probability or a genuine/fake verdict yet; transparent risk aggregation is a later phase.

## Current capabilities

- Text/pasted offer and text-selectable PDF ingestion.
- Local deterministic extraction by default. Gemini is optional and disabled unless explicitly enabled; no API key, billing or quota is required for default extraction.
- Extracted company, role, compensation, recruiter, sender contacts, domains, URLs, UPI identifiers, payment-demand/urgency phrases and source excerpts.
- `POST /api/verify` returns six verification categories: RDAP domain age, website reachability, TLS certificate, sender/company-domain consistency, PDF metadata chronology and payment red flags.
- Each check includes a status, severity, timestamp, source/provenance and limitations. Missing or unavailable evidence is never treated as a clean result.
- Frontend Check Trace displays each Phase 4 result. Editing a draft claim automatically reruns checks; stale results are cleared while the new request runs. Complete JSON export stays disabled until verification finishes and includes the six-check verification report.

## Important interpretation rules

- A `CLEAR` result applies only to that particular check. It does not prove that an offer is genuine.
- A newly registered domain is a warning indicator, not proof of fraud.
- A reachable website or valid TLS certificate does not prove company ownership.
- PDF metadata can be edited and does not authenticate a document.
- A sender-domain comparison is a consistency check against domains stated in the submitted material, not an independently confirmed company directory lookup.
- An explicit upfront payment demand is a strong warning indicator, but this service does not make a legal determination.
- Reserved documentation domains such as `.example` are marked `not_applicable`; the service does not attempt live registry or network checks for them.
- Image-only uploads are not OCR-processed in the default free-tier workflow. The report explains that limitation.

## Backend setup (Windows PowerShell)

From the repository root:

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cd ..
Copy-Item .env.example .env
```

If `.env` already exists, do not overwrite it; add or update the settings below as needed. Keep `.env` private and never commit it.

Relevant settings in the repository-root `.env`:

```dotenv
GEMINI_ENABLED=false
TOOL_TIMEOUT_SECONDS=8
NEW_DOMAIN_THRESHOLD_DAYS=30
```

The first setting keeps extraction independent of Gemini quota. `TOOL_TIMEOUT_SECONDS` bounds each external verification tool request. `NEW_DOMAIN_THRESHOLD_DAYS` controls the recent-registration warning window.

Start the API from `backend`:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Swagger: http://127.0.0.1:8000/docs

## Frontend setup (Windows PowerShell)

In a second VS Code terminal:

```powershell
cd frontend
npm install
npm run typecheck
npm test
npm run build
npm run dev
```

Open http://127.0.0.1:5173. Keep both terminals open while using the app.

## Tests (run before committing)

Backend, from `backend` with `.venv` activated:

```powershell
python -m pytest -v
```

Frontend, from `frontend`:

```powershell
npm run typecheck
npm test
npm run build
```

The Phase 4 backend tests mock RDAP, DNS, HTTP and TLS providers where appropriate. The PDF end-to-end regression test generates a PDF with embedded metadata, runs `/api/extract`, then passes the extracted response into `/api/verify`. Reserved `.example` domains keep the test offline and deterministic. No Gemini call is needed.

## API overview

- `GET /health` — backend health.
- `POST /api/ingest` — inspect a submitted input and its metadata.
- `POST /api/extract` — extract structured claims from exactly one file or text input.
- `POST /api/verify` — evaluate one `ExtractedOffer` using the six Phase 4 checks.

See [`docs/api_contract.md`](docs/api_contract.md) for request/response schemas, status meanings and limitations.

## Phase boundary

Phase 4 returns check-level evidence only. It does not implement weighted risk scoring, company registry verification, URL reputation feeds, historical case linking, graph intelligence, or persistent case storage. Those should be added in later phases without changing the semantics of existing check results.
