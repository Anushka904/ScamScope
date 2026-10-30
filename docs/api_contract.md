# ScamScope API Contract

## Base URL

http://127.0.0.1:8000

## Health

GET /health

Returns backend health status.

## Analyze Offer

POST /api/analyze

Content-Type: multipart/form-data

Inputs:
- file: Optional uploaded screenshot or PDF
- text: Optional pasted offer text

Exactly one input should be provided.

The backend will return an InvestigationReport.

## InvestigationReport

Fields:

- investigation_id
- created_at
- input_type
- mode
- status
- extracted
- risk
- evidence
- explanation
- notes

## RiskAssessment

Fields:

- risk_score: integer from 0 to 100
- risk_band
- verification_status
- completed_checks
- total_checks
- coverage_percent
- evidence_ids
- caveats

## Evidence

Each evidence item contains:

- evidence_id
- check_name
- status
- severity
- finding
- observed_value
- source_type
- source_name
- source_url
- source_excerpt
- page_number
- checked_at
- limitation
- details

## Important semantics

A CLEAR result does not mean an offer is safe.

UNAVAILABLE and ERROR must never be treated as clean results.

Risk scores are indicator scores, not fraud probabilities.

Every risk evidence reference must correspond to an actual evidence item.