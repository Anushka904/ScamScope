# ScamScope API Contract

## Base URL

http://127.0.0.1:8000

## 1. Health Check

GET /health

Checks whether the backend is running.

## 2. Input Ingestion

POST /api/ingest

Content-Type: multipart/form-data

Accepts exactly one input.

### File input

Field name: file

Supported formats:
- PNG
- JPEG
- WEBP
- PDF

### Text input

Field name: text

Accepts a pasted job or internship offer.

### Response

Returns IngestionSummary:

- input_type
- source_filename
- mime_type
- text_characters
- text_preview
- page_count
- pdf_metadata
- visual_assets
- warnings

Binary image content is never included in this response.

## 3. Planned Investigation Endpoint

POST /api/analyze

This will be implemented in a later phase.

It will:
1. Accept an offer.
2. Prepare the input.
3. Extract entities using Gemini.
4. Run deterministic investigation tools.
5. Calculate a risk assessment.
6. Return an evidence-linked InvestigationReport.

## 4. Planned History Endpoint

GET /api/history

Retrieve previous investigations.

## 5. Planned Individual Investigation

GET /api/investigations/{id}

Retrieve a previously stored investigation.

## Important semantics

- A CLEAR result does not prove an offer is safe.
- UNAVAILABLE and ERROR are not equivalent to CLEAR.
- Risk scores are indicator scores, not fraud probabilities.
- Every risk evidence reference must point to an existing evidence record.
- User-submitted claims must be distinguished from independently verified facts.
- PDF metadata alone cannot establish that a document is forged.