
# ScamScope API Contract

## Base URL

http://127.0.0.1:8000

---

## 1. Health Check

GET /health

Returns:

- status
- project
- message

---

## 2. Input Ingestion

POST /api/ingest

Content-Type: multipart/form-data

Accepts exactly one input:

- file: PNG, JPEG, WEBP or PDF
- text: Pasted recruitment offer

Returns an IngestionSummary containing:

- input_type
- source_filename
- mime_type
- text_characters
- text_preview
- page_count
- pdf_metadata
- visual_assets
- warnings

No binary image content is returned.

---

## 3. Gemini Extraction

POST /api/extract

Content-Type: multipart/form-data

Accepts exactly one input:

- file: Screenshot or PDF
- text: Pasted internship/job offer

Processing:

1. Validates and preprocesses input.
2. Creates a multimodal Gemini request.
3. Extracts structured entities.
4. Validates the result using Pydantic.
5. Returns an ExtractedOffer.

### ExtractedOffer fields

- input_type
- company_name
- claimed_company_website
- role_title
- salary_claim
- claimed_issue_date
- claimed_joining_date
- recruiter_name
- sender_email
- sender_phone
- domains
- urls
- phone_numbers
- upi_ids
- payment_demand
- payment_amount
- payment_demand_phrases
- urgency_phrases
- evidence_excerpts
- extraction_warnings
- extraction_status (`complete`, `partial`, or `deterministic_fallback`)

`extraction_status` is authoritative about how the result was produced:

- `complete`: every extraction task completed successfully with Gemini.
- `partial`: some tasks completed, while one or more tasks failed.
- `deterministic_fallback`: Gemini was unavailable and only explicit,
  high-confidence text patterns were extracted. Fields that could not be
  confidently identified remain null/empty. This is not equivalent to AI extraction.

### Error responses

400: Multiple inputs supplied.

413: File or input exceeds configured limits.

415: Unsupported file type.

422: Invalid input.

429: Gemini quota/rate limit reached.

502: Gemini/provider extraction failure.

503: Gemini credentials or configuration missing.

504: Gemini request timed out.

---

## 4. Planned Investigation Endpoint

POST /api/analyze

This will be implemented in later phases.

It will:

1. Accept an offer.
2. Prepare and extract its content.
3. Perform domain, SSL, DNS and reputation checks.
4. Aggregate deterministic evidence.
5. Calculate a risk score.
6. Generate an evidence-grounded explanation.
7. Return an InvestigationReport.

---

## 5. Planned History Endpoint

GET /api/history

Retrieve previous investigations.

---

## 6. Planned Individual Investigation

GET /api/investigations/{id}

Retrieve a stored investigation report.

---

## Important semantics

- Gemini extraction is not proof that a claim is true.
- User-provided company names and recruiter identities
  are claims, not independently verified facts.
- A missing field is represented as null or an empty list.
- Unreadable content must be disclosed.
- AI-transcribed quotations from images must be
  verified against the original visual document.
- No extraction result is a fraud verdict.
- Risk scores are calculated separately by Python.
