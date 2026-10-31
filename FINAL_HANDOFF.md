# ScamScope Phase 4 — Final handoff

This release contains the Phase 4 independent verification engine plus the regression fixes identified during the Northstar PDF test. It is intended to be extracted over the existing repository root on the `feat/phase-4-verification-engine` branch.

## What was fixed

- Company-name extraction now prefers explicit labels and standalone legal-name mastheads. The company label matcher is line-anchored and cannot mistake a phrase such as `company-domain email` in a disclaimer for a `Company:` field.
- Company website extraction handles both same-line labels (`Company Website: https://...`) and PDF layouts where `Claimed company website` and the URL are on adjacent lines.
- Website evidence excerpts point to the actual URL line when the PDF separates the label and value.
- The frontend automatically reruns verification when a local draft field changes, and aborts the stale in-flight request so an older result cannot overwrite a newer one.
- JSON export is disabled until all six check categories have returned a verification report. The export builder also rejects a null verification result, and the downloaded record contains the complete verification payload.
- Added a backend end-to-end PDF regression test which creates a PDF with real embedded metadata, calls `POST /api/extract`, then calls `POST /api/verify` with the exact extraction response. It asserts title, author, subject, creator, producer and both date fields survive into the verification evidence.
- Added frontend tests for the complete investigation JSON builder and its pending-verification guard.
- Fixed RDAP lookup for website hostnames: when a registry rejects a hostname/subdomain such as `www.wikipedia.org` with HTTP 400 or 404, the check retries progressively less-specific parent candidates and uses the first valid registered-domain object. HTTP 429 and 5xx errors are not retried as parent-domain successes.
- Added mocked RDAP regression coverage for the `www.wikipedia.org` → `wikipedia.org` lookup and for preserving rate-limit failures as unavailable results.

## Phase 4 checks

1. Domain age via IANA RDAP bootstrap.
2. Website reachability with URL validation and redirect checks.
3. TLS certificate chain and hostname validation.
4. Sender email-domain consistency with domains explicitly stated in the offer.
5. PDF metadata inspection and timestamp chronology.
6. Payment request, UPI and urgency indicators from extracted evidence.

Each result is `flag`, `clear`, `unavailable`, `error`, or `not_applicable`. Phase 4 does not generate a fraud probability or genuine/fake verdict. A clear result is limited to the exact check; it is not proof of legitimacy.

## Apply on Windows

1. Stop the backend and frontend dev servers with `Ctrl+C`.
2. Extract this ZIP into the existing repository root:

   `C:\Users\Anushka\OneDrive\Desktop\ScamScope\ScamScope`

3. Choose **Replace files in destination** when prompted.
4. Do not delete or replace `.git`, `.env`, `backend/.venv`, `frontend/.env.local`, or `frontend/node_modules`. These are local state/secrets/dependencies and are intentionally excluded from this release ZIP.
5. Keep the existing `stash@{0}` backup until Phase 4 is merged. Do not `stash pop` it; this release already contains the free-tier extraction changes captured in the uploaded source snapshot.

## Run the tests before committing

Open a PowerShell terminal at the repository root.

### Backend

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m pytest -q
```

Expected in this release: **121 passed**.

### Frontend

In a second terminal:

```powershell
cd frontend
npm install
npm run typecheck
npm test
npm run build
```

Expected frontend unit test count: **13 passed**. `npm run build` must finish with `built in ...` and no TypeScript/Vite errors.

### Local smoke test

With the tests passing, start the servers:

Backend terminal:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend terminal:

```powershell
cd frontend
npm run dev
```

Open `http://127.0.0.1:5173`, submit an offer PDF or pasted offer text, wait for the Check Trace to finish, and confirm all six rows are displayed. The Download JSON controls should remain disabled while the trace is pending and should enable after a verification response is received. Downloaded JSON must contain a non-null `verification` object with six checks.

## Commit only after the tests pass

From the repository root:

```powershell
git branch --show-current
git diff --check
git status --short
```

The branch should be `feat/phase-4-verification-engine`. Check that no local secrets, `.venv`, `node_modules`, or `dist` are staged. Then:

```powershell
git add -A
git diff --cached --stat
git diff --cached --name-only
git commit -m "feat: add Phase 4 independent verification engine"
git push -u origin feat/phase-4-verification-engine
```

Create a pull request from `feat/phase-4-verification-engine` into `main`.

## Verification performed for this handoff

- Backend: **121 tests passed** using Python 3.13 in the build environment.
- Frontend TypeScript project check: passed.
- Frontend Vitest and production build: not executable in this Linux build container because the supplied dependency tree lacks the Linux Rollup optional binary and outbound package installation is blocked. Run Vitest and the production build in the Windows project environment before committing.
- The end-to-end API regression test validates company-name extraction, adjacent-line website extraction, populated embedded PDF metadata, sender-domain mismatch, absence of a payment flag, six verification categories, and the complete extract-to-verify API flow.
- RDAP regression tests verify that a 400 on `www.wikipedia.org` is followed by a lookup for `wikipedia.org`, and that HTTP 429 is preserved as a provider failure. Live RDAP/DNS availability is environment-dependent; this build container has no outbound DNS resolution, so no live `.org` lookup is claimed as tested.

No user `.env`, `.env.local`, `.git`, virtual environment, node_modules, or production build output is included in the release ZIP.
