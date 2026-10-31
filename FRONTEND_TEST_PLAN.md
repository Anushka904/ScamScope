# ScamScope — Frontend and Phase 4 End-to-End Test Plan

Run automated checks from `frontend/`:

```powershell
npm run typecheck
npm test
npm run build
```

Run backend checks from `backend/` with `.venv` activated:

```powershell
python -m pytest -q
```

## Required manual end-to-end checks

| Test | Steps | Expected result |
|---|---|---|
| Pasted text success | Paste the fictional Nexora offer and start extraction | `/api/extract` returns expected fields, payment language, domains and evidence excerpts |
| Rule-based mode | Keep `GEMINI_ENABLED=false` and submit text | Extraction succeeds without a Gemini API key or quota |
| Phase 4 auto-run | Open the Case Report after extraction | The frontend calls `/api/verify`; Check Trace displays six categories |
| Reserved `.example` domain | Use the Nexora sample | RDAP, website and TLS show `N/A`; no live network request is made for the reserved domain |
| Sender-domain consistency | Use `rahul@nexora-careers.example` and `www.nexora-careers.example` | Sender-domain check is `CLEAR`, with a caveat that this is not independent proof of ownership |
| Payment red flags | Use the Nexora ₹2,499 upfront-fee text | Payment red flags show `FLAGGED`, the amount, UPI ID and urgency evidence |
| Text PDF metadata | Use pasted text | PDF metadata shows `N/A` |
| Public domain lookup | Use a public domain you control | RDAP lookup may return age or `UNAVAILABLE`; source URL and registration timestamp are visible in JSON |
| RDAP host-to-domain fallback | Use a website host such as `www.wikipedia.org` | RDAP first tries the host, then retries `wikipedia.org` if the registry rejects the host with HTTP 400/404; rate limits and 5xx remain `UNAVAILABLE` |
| Website unreachable | Test a domain that does not resolve or is offline | Website result is `UNAVAILABLE`, not `CLEAR` |
| Unsafe redirect | In automated backend tests, simulate a public URL redirecting to `127.0.0.1` | Request is blocked before following the redirect |
| SSL issue | Mock a hostname/certificate validation failure in backend tests | TLS check is `FLAG`; provider/network failures remain `UNAVAILABLE` |
| PDF metadata chronology | Use a PDF with creation timestamp later than modification timestamp | PDF metadata reports a weak flag with a non-authenticity caveat |
| Missing/invalid email | Submit an offer without a usable sender email | Sender-domain check is `UNAVAILABLE` |
| Backend offline | Stop Uvicorn and open/reload an investigation | Extraction/verification error is shown; no fake check result is produced |
| Local draft edit | Edit a field and select Re-run checks | The new draft is sent to `/api/verify`; report warns that local edits are not source-verified |
| JSON export | Download the report | JSON includes extraction, verification checks, evidence IDs, timestamps and caveats |
| Print | Select Print / Save PDF | Print layout includes the report without navigation/actions |
| Refresh report | Refresh `/case` | Session-only empty state appears; no case data is persisted |

## Interpretation rules

- `flag` = the stated warning condition was observed.
- `clear` = that specific check completed without observing its warning condition; this does not prove legitimacy.
- `unavailable` = required input/provider/network data could not be obtained.
- `error` = an unexpected attempted-check failure.
- `not_applicable` = the check does not apply.
- Only `flag` and `clear` contribute to `completed_checks` and coverage percentage. Missing/unavailable results are never counted as clean.
- Phase 4 does not generate a fraud probability, risk score or genuine/fake verdict.
