
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

## 3. Offer Extraction

POST /api/extract

Content-Type: multipart/form-data

Accepts exactly one input:

- file: Screenshot or PDF
- text: Pasted internship/job offer

Processing:

1. Validates and preprocesses input.
2. By default, runs local deterministic patterns over selectable text.
3. Optionally uses Gemini only when `GEMINI_ENABLED=true` and valid credentials are configured.
4. Validates model output using Pydantic when Gemini is enabled.
5. Returns an `ExtractedOffer` with source excerpts and explicit limitations.

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

- `complete`: every optional Gemini extraction task completed successfully.
- `partial`: some optional provider tasks completed, while one or more tasks failed.
- `deterministic_fallback`: local rule-based extraction was used. This is the default mode and is also used when the optional Gemini provider is unavailable. It identifies explicit patterns in selectable text; fields that cannot be confidently identified remain null/empty. This is not equivalent to AI extraction.

### Error responses

400: Multiple inputs supplied.

413: File or input exceeds configured limits.

415: Unsupported file type.

422: Invalid input.

The default local extraction path does not return provider quota errors. When optional Gemini mode is explicitly enabled, provider failures on readable text degrade to rule-based extraction. Input validation errors remain 4xx responses.

---

## 4. Planned Investigation Aggregation Endpoint (Phase 5)

POST /api/analyze

This endpoint is not implemented yet. Phase 5 will orchestrate extraction plus the existing `/api/verify` checks, then calculate an explainable risk assessment from supported evidence. Missing, unavailable, and not-applicable results must not be treated as clean signals. It will return an evidence-grounded explanation and will not claim certainty beyond the evidence.

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

## Phase 4 — Independent verification (`POST /api/verify`)

Request body:

```json
{
  "extracted": {
    "input_type": "text",
    "extraction_status": "deterministic_fallback",
    "company_name": "Example Company",
    "domains": ["example.com"],
    "sender_email": "hr@example.com",
    "payment_demand": false
  }
}
```

The `extracted` object follows the Phase 3 `ExtractedOffer` schema. PDF extraction responses additionally include a nullable `pdf_metadata` object. This is descriptive file metadata, not proof of authenticity.

The response contains six check categories:

- `domain_age`: uses the authoritative RDAP service discovered through the IANA DNS bootstrap registry (RFC 9224). If the supplied value is a host/subdomain (for example `www.wikipedia.org`) and a registry returns HTTP 400/404, the checker retries parent candidates and records the registered-domain name it actually queried. Rate-limit and server errors remain unavailable results.
- `website_availability`: checks whether the first explicit company website/domain responds over HTTP(S). The request is restricted to public destinations, non-standard ports are rejected, and redirects are revalidated.
- `ssl_certificate`: validates the TLS certificate chain and hostname for the primary claimed domain.
- `sender_domain_match`: compares the extracted sender email domain with the company domains explicitly present in the submitted material.
- `pdf_metadata`: reviews embedded metadata and checks whether a parseable creation timestamp occurs after the modification timestamp. Not applicable to text/image inputs.
- `payment_red_flags`: surfaces explicit payment demand, urgency/pressure phrases and UPI identifiers found during Phase 3 extraction.

Each check has an explicit `status`: `flag`, `clear`, `unavailable`, `error`, or `not_applicable`. External provider/network failures are `unavailable` and are never converted into clean results. Reserved test/documentation suffixes such as `.example` are `not_applicable` for RDAP, website and TLS checks; no live network request is made for them.

The response includes provenance, timestamp, observed values, limitations, evidence IDs and an `evidence` list suitable for future Phase 5 scoring. The frontend Check Trace automatically runs after extraction and reruns when local draft fields change. A complete JSON investigation export includes both extraction and verification; export remains disabled while verification is pending or unavailable. **Phase 4 does not produce a risk score, fraud probability, or genuine/fake verdict.** A `clear` result only means that a specific check did not observe its stated warning condition.

The service uses the existing `TOOL_TIMEOUT_SECONDS` setting. `NEW_DOMAIN_THRESHOLD_DAYS` defaults to `30`; a domain registered within that interval is surfaced as a medium warning indicator, not as proof of fraud.
