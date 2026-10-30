# ScamScope

AI-assisted, evidence-led investigation of suspicious internship and job offers.

The backend currently supports validated text/image/PDF ingestion and Gemini-assisted
structured extraction. Extraction results distinguish complete AI extraction, partial
extraction, and deterministic text fallback. A fallback is never presented as a
completed AI analysis. Fraud scoring and external verification are separate later phases.

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

Add a Gemini API key to the root `.env` file. Keep `.env` private; never commit it.

Start the API from `backend`:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Swagger: http://127.0.0.1:8000/docs

Before using Swagger for the first real model call, run the one-request smoke test
from `backend`:

```powershell
python -m scripts.smoke_test_gemini
```

The smoke test uses a synthetic offer and exits non-zero if the result is only a
deterministic fallback or any expected field is missing. Gemini requests use the
configured `GEMINI_TIMEOUT_SECONDS` (120 seconds by default) and retry a transient
gateway failure once, including HTTP 504.

## Tests

From `backend` with the virtual environment activated:

```powershell
python -m pytest -v
```

The automated test suite mocks Gemini; it does not consume API quota. Live provider
behavior still depends on Google API availability, account quota, the configured model,
and the quality of the submitted document.
