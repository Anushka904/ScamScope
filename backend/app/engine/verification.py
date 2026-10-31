"""Phase 4 independent verification orchestration.

This module does not assign a fraud score or verdict. It returns individual
checks, provenance and limitations so a later risk-scoring phase can reason
from the actual evidence instead of from missing data.
"""

from __future__ import annotations

import re
import ssl
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.models.evidence import Evidence, EvidenceSeverity, EvidenceSourceType, EvidenceStatus
from app.models.extraction import ExtractedOffer, InputType
from app.models.pdf import PDFMetadata
from app.models.verification import (
    VerificationCheck,
    VerificationCheckId,
    VerificationOverallStatus,
    VerificationReport,
)
from app.tools.domain_checks import (
    DomainCheckError,
    UnsafeTargetError,
    check_ssl_certificate,
    check_website_availability,
    is_reserved_domain,
    lookup_domain_registration,
    normalize_domain,
)

FREE_EMAIL_PROVIDERS = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.in", "outlook.com",
    "hotmail.com", "live.com", "aol.com", "icloud.com", "me.com", "proton.me",
    "protonmail.com", "rediffmail.com", "mail.com", "gmx.com", "yandex.com",
}

CHECK_LABELS = {
    VerificationCheckId.DOMAIN_AGE: "Domain age / RDAP",
    VerificationCheckId.WEBSITE_AVAILABILITY: "Website availability",
    VerificationCheckId.SSL_CERTIFICATE: "SSL / certificate",
    VerificationCheckId.SENDER_DOMAIN_MATCH: "Sender-domain match",
    VerificationCheckId.PDF_METADATA: "PDF metadata",
    VerificationCheckId.PAYMENT_RED_FLAGS: "Payment red flags",
}


def _candidate_domains(extracted: ExtractedOffer) -> list[str]:
    candidates: list[str] = []
    raw_values = []
    if extracted.claimed_company_website:
        raw_values.append(extracted.claimed_company_website)
    raw_values.extend(extracted.domains)
    raw_values.extend(extracted.urls)
    for raw in raw_values:
        normalized = normalize_domain(raw)
        if normalized and normalized not in candidates:
            candidates.append(normalized)
    return candidates[:5]


def _primary_domain(extracted: ExtractedOffer) -> str | None:
    domains = _candidate_domains(extracted)
    if not domains:
        return None
    # Prefer an explicit claimed website when it is present.
    explicit = normalize_domain(extracted.claimed_company_website)
    return explicit or domains[0]


def _domain_match(email_domain: str, company_domain: str) -> bool:
    email_domain = email_domain.lower().removeprefix("www.").rstrip(".")
    company_domain = company_domain.lower().removeprefix("www.").rstrip(".")
    return (
        email_domain == company_domain
        or email_domain.endswith("." + company_domain)
        or company_domain.endswith("." + email_domain)
    )


def _pdf_date(value: str | None) -> datetime | None:
    """Parse common PDF date strings (D:YYYYMMDDHHmmSS+05'30') and ISO dates."""
    if not value:
        return None
    raw = value.strip()
    if raw.startswith("D:"):
        raw = raw[2:]
        match = re.match(
            r"^(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?(Z|[+-]\d{2}'?\d{2}'?)?$",
            raw,
        )
        if not match:
            return None
        year, month, day, hour, minute, second, zone = match.groups()
        month, day = month or "01", day or "01"
        hour, minute, second = hour or "00", minute or "00", second or "00"
        try:
            parsed = datetime(
                int(year), int(month), int(day), int(hour), int(minute), int(second),
                tzinfo=timezone.utc,
            )
            if zone and zone != "Z":
                zone_match = re.match(r"([+-])(\d{2})'?((?:\d{2}))'?", zone)
                if zone_match:
                    sign, hours, minutes = zone_match.groups()
                    from datetime import timedelta
                    offset = timedelta(hours=int(hours), minutes=int(minutes))
                    if sign == "-":
                        offset = -offset
                    from datetime import timezone as dt_timezone
                    parsed = parsed.replace(tzinfo=dt_timezone(offset))
            return parsed.astimezone(timezone.utc)
        except ValueError:
            return None
    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _check_result(
    check_id: VerificationCheckId,
    status: EvidenceStatus,
    finding: str,
    source_type: EvidenceSourceType,
    *,
    severity: EvidenceSeverity = EvidenceSeverity.INFORMATIONAL,
    observed_value: str | None = None,
    source_url: str | None = None,
    limitation: str | None = None,
    details: dict[str, Any] | None = None,
    source_excerpt: str | None = None,
    evidence_id: str,
    checked_at: datetime,
) -> tuple[VerificationCheck, Evidence]:
    check = VerificationCheck(
        check_id=check_id,
        label=CHECK_LABELS[check_id],
        status=status,
        severity=severity,
        finding=finding,
        observed_value=observed_value,
        source_type=source_type.value,
        source_url=source_url,
        checked_at=checked_at,
        limitation=limitation,
        details=details or {},
        evidence_ids=[evidence_id],
    )
    evidence = Evidence(
        evidence_id=evidence_id,
        check_name=check_id.value,
        status=status,
        severity=severity,
        finding=finding[:500],
        observed_value=observed_value,
        source_type=source_type,
        source_name="ScamScope Phase 4 verification",
        source_url=source_url,
        source_excerpt=source_excerpt,
        checked_at=checked_at,
        limitation=limitation,
        details=details or {},
    )
    return check, evidence


def _metadata_check(
    extracted: ExtractedOffer,
    metadata: PDFMetadata | None,
    checked_at: datetime,
    evidence_id: str,
) -> tuple[VerificationCheck, Evidence]:
    if extracted.input_type != InputType.PDF:
        return _check_result(
            VerificationCheckId.PDF_METADATA, EvidenceStatus.NOT_APPLICABLE,
            "PDF metadata analysis does not apply to pasted text or image uploads.",
            EvidenceSourceType.PDF_METADATA,
            limitation="Only PDF files contain the metadata fields inspected by this check.",
            evidence_id=evidence_id, checked_at=checked_at,
        )
    if metadata is None:
        return _check_result(
            VerificationCheckId.PDF_METADATA, EvidenceStatus.UNAVAILABLE,
            "The uploaded PDF metadata was not available to the verification engine.",
            EvidenceSourceType.PDF_METADATA,
            limitation="Re-extract the original PDF with the current backend and retry.",
            evidence_id=evidence_id, checked_at=checked_at,
        )

    creation = _pdf_date(metadata.creation_date_raw)
    modified = _pdf_date(metadata.modification_date_raw)
    details = metadata.model_dump(exclude_none=True)
    details["creation_date_parsed"] = creation.isoformat() if creation else None
    details["modification_date_parsed"] = modified.isoformat() if modified else None

    if creation and modified and creation > modified:
        finding = (
            "PDF creation timestamp is later than its modification timestamp. "
            "This is a metadata chronology inconsistency and should be reviewed."
        )
        return _check_result(
            VerificationCheckId.PDF_METADATA, EvidenceStatus.FLAG, finding,
            EvidenceSourceType.PDF_METADATA,
            severity=EvidenceSeverity.WEAK,
            observed_value=f"Created {creation.isoformat()} / modified {modified.isoformat()}",
            limitation="PDF metadata can be edited or rewritten by legitimate software; this is not proof of tampering.",
            details=details,
            evidence_id=evidence_id, checked_at=checked_at,
        )

    if not any((metadata.title, metadata.author, metadata.subject, metadata.creator, metadata.producer,
                metadata.creation_date_raw, metadata.modification_date_raw)):
        finding = "No embedded PDF metadata fields were present. Missing metadata alone is not a fraud indicator."
    else:
        finding = "Embedded PDF metadata was inspected; no creation/modification chronology inconsistency was detected."
    return _check_result(
        VerificationCheckId.PDF_METADATA, EvidenceStatus.CLEAR, finding,
        EvidenceSourceType.PDF_METADATA,
        observed_value=f"{metadata.page_count} page(s); metadata fields present: " + ", ".join(
            key for key in ("title", "author", "creator", "producer", "creation_date_raw", "modification_date_raw")
            if getattr(metadata, key)
        ),
        limitation="Metadata describes the file but can be edited and does not authenticate the sender or document.",
        details=details,
        evidence_id=evidence_id, checked_at=checked_at,
    )


def _sender_domain_check(
    extracted: ExtractedOffer,
    candidates: list[str],
    checked_at: datetime,
    evidence_id: str,
) -> tuple[VerificationCheck, Evidence]:
    email = (extracted.sender_email or "").strip()
    if "@" not in email or email.count("@") != 1:
        return _check_result(
            VerificationCheckId.SENDER_DOMAIN_MATCH, EvidenceStatus.UNAVAILABLE,
            "No usable sender email address was extracted, so domain alignment could not be checked.",
            EvidenceSourceType.USER_CONTENT,
            limitation="A sender address was not clearly identified in the submitted material.",
            evidence_id=evidence_id, checked_at=checked_at,
        )
    sender_domain = normalize_domain(email.rsplit("@", 1)[1])
    if not sender_domain:
        return _check_result(
            VerificationCheckId.SENDER_DOMAIN_MATCH, EvidenceStatus.UNAVAILABLE,
            "The sender email domain could not be normalized.",
            EvidenceSourceType.USER_CONTENT,
            observed_value=email,
            evidence_id=evidence_id, checked_at=checked_at,
        )
    if not candidates:
        if sender_domain in FREE_EMAIL_PROVIDERS:
            return _check_result(
                VerificationCheckId.SENDER_DOMAIN_MATCH, EvidenceStatus.FLAG,
                "The sender uses a consumer email provider and no company domain was available for comparison. Verify through an independently sourced official channel.",
                EvidenceSourceType.USER_CONTENT,
                severity=EvidenceSeverity.WEAK,
                observed_value=f"{email} (consumer mailbox provider)",
                limitation="A consumer mailbox is not proof of fraud; no claimed company domain was available for comparison.",
                evidence_id=evidence_id, checked_at=checked_at,
            )
        return _check_result(
            VerificationCheckId.SENDER_DOMAIN_MATCH, EvidenceStatus.UNAVAILABLE,
            "No company website/domain was extracted, so sender-domain alignment could not be compared.",
            EvidenceSourceType.USER_CONTENT,
            observed_value=email,
            limitation="The email's domain alone does not establish which domain the company officially uses.",
            evidence_id=evidence_id, checked_at=checked_at,
        )

    matched = [domain for domain in candidates if _domain_match(sender_domain, domain)]
    excerpt = next((item.quote for item in extracted.evidence_excerpts if item.field_name == "sender_email"), None)
    if matched:
        return _check_result(
            VerificationCheckId.SENDER_DOMAIN_MATCH, EvidenceStatus.CLEAR,
            "The sender email domain matches a company domain stated in the submitted material.",
            EvidenceSourceType.USER_CONTENT,
            observed_value=f"{email} ↔ {', '.join(matched)}",
            limitation="This is an internal consistency check only; scammers can use lookalike domains and matching domains are not proof of authenticity.",
            details={"sender_domain": sender_domain, "matched_company_domains": matched, "compared_domains": candidates},
            source_excerpt=excerpt,
            evidence_id=evidence_id, checked_at=checked_at,
        )
    return _check_result(
        VerificationCheckId.SENDER_DOMAIN_MATCH, EvidenceStatus.FLAG,
        "The sender email domain does not match the company website/domain stated in the submitted material.",
        EvidenceSourceType.USER_CONTENT,
        severity=EvidenceSeverity.MEDIUM,
        observed_value=f"Sender: {sender_domain}; claimed company domain(s): {', '.join(candidates)}",
        limitation="Organizations may use separate recruiting or subsidiary domains. Confirm through a contact independently obtained from the official company website.",
        details={"sender_domain": sender_domain, "compared_domains": candidates},
        source_excerpt=excerpt,
        evidence_id=evidence_id, checked_at=checked_at,
    )


def _payment_check(
    extracted: ExtractedOffer,
    checked_at: datetime,
    evidence_id: str,
) -> tuple[VerificationCheck, Evidence]:
    payment_phrases = extracted.payment_demand_phrases[:5]
    urgency_phrases = extracted.urgency_phrases[:5]
    upi_ids = extracted.upi_ids[:10]
    if extracted.payment_demand:
        parts = ["The submitted offer explicitly requests or requires a payment."]
        if extracted.payment_amount:
            parts.append(f"Requested amount: {extracted.payment_amount}.")
        if upi_ids:
            parts.append(f"A UPI destination is included: {', '.join(upi_ids)}.")
        if urgency_phrases:
            parts.append(f"{len(urgency_phrases)} urgency/pressure phrase(s) were extracted.")
        finding = " ".join(parts)
        return _check_result(
            VerificationCheckId.PAYMENT_RED_FLAGS, EvidenceStatus.FLAG, finding,
            EvidenceSourceType.USER_CONTENT,
            severity=EvidenceSeverity.STRONG,
            observed_value="; ".join(filter(None, [extracted.payment_amount, ", ".join(upi_ids), f"{len(urgency_phrases)} urgency phrase(s)" if urgency_phrases else None])),
            limitation="An explicit upfront payment request is a strong warning indicator, but this check does not determine legal status or issue a fraud verdict.",
            details={"payment_demand": True, "payment_amount": extracted.payment_amount, "upi_ids": upi_ids,
                     "payment_phrases": payment_phrases, "urgency_phrases": urgency_phrases},
            source_excerpt=payment_phrases[0] if payment_phrases else (urgency_phrases[0] if urgency_phrases else None),
            evidence_id=evidence_id, checked_at=checked_at,
        )
    if upi_ids:
        return _check_result(
            VerificationCheckId.PAYMENT_RED_FLAGS, EvidenceStatus.FLAG,
            "A UPI identifier appears in the submitted material, but no explicit payment demand was extracted. Review the surrounding context manually.",
            EvidenceSourceType.USER_CONTENT,
            severity=EvidenceSeverity.WEAK,
            observed_value=", ".join(upi_ids),
            limitation="A UPI identifier on its own does not establish that money was requested or that the recipient is fraudulent.",
            details={"payment_demand": False, "upi_ids": upi_ids, "urgency_phrases": urgency_phrases},
            evidence_id=evidence_id, checked_at=checked_at,
        )
    if urgency_phrases:
        return _check_result(
            VerificationCheckId.PAYMENT_RED_FLAGS, EvidenceStatus.FLAG,
            "Urgency or pressure language was extracted, but no payment demand was identified.",
            EvidenceSourceType.USER_CONTENT,
            severity=EvidenceSeverity.WEAK,
            observed_value=f"{len(urgency_phrases)} urgency phrase(s)",
            limitation="Deadlines can be legitimate; review the full context rather than treating urgency alone as proof of fraud.",
            details={"payment_demand": False, "urgency_phrases": urgency_phrases},
            source_excerpt=urgency_phrases[0],
            evidence_id=evidence_id, checked_at=checked_at,
        )
    return _check_result(
        VerificationCheckId.PAYMENT_RED_FLAGS, EvidenceStatus.CLEAR,
        "No explicit payment demand, UPI payment destination or extracted urgency phrase was identified.",
        EvidenceSourceType.USER_CONTENT,
        limitation="Rule-based extraction can miss language that is implicit, image-only or poorly OCR-readable.",
        details={"payment_demand": False, "upi_ids": [], "urgency_phrases": []},
        evidence_id=evidence_id, checked_at=checked_at,
    )


def _external_domain_checks(
    domain: str | None,
    settings: Settings,
    checked_at: datetime,
    ids: list[str],
) -> list[tuple[VerificationCheck, Evidence]]:
    results: list[tuple[VerificationCheck, Evidence]] = []
    if not domain:
        for check_id, label in (
            (VerificationCheckId.DOMAIN_AGE, "No company domain was found for RDAP registration lookup."),
            (VerificationCheckId.WEBSITE_AVAILABILITY, "No explicit company website/domain was found to test."),
            (VerificationCheckId.SSL_CERTIFICATE, "No explicit company domain was found for TLS certificate inspection."),
        ):
            results.append(_check_result(
                check_id, EvidenceStatus.UNAVAILABLE, label,
                EvidenceSourceType.RDAP if check_id == VerificationCheckId.DOMAIN_AGE else (
                    EvidenceSourceType.TLS if check_id == VerificationCheckId.SSL_CERTIFICATE else EvidenceSourceType.COMPANY_WEBSITE
                ),
                limitation="The submitted material did not contain a domain that could be checked.",
                evidence_id=ids.pop(0), checked_at=checked_at,
            ))
        return results

    if is_reserved_domain(domain):
        reason = f"{domain} is a reserved documentation/test domain; live registration, website and TLS checks do not apply."
        for check_id, source in (
            (VerificationCheckId.DOMAIN_AGE, EvidenceSourceType.RDAP),
            (VerificationCheckId.WEBSITE_AVAILABILITY, EvidenceSourceType.COMPANY_WEBSITE),
            (VerificationCheckId.SSL_CERTIFICATE, EvidenceSourceType.TLS),
        ):
            results.append(_check_result(
                check_id, EvidenceStatus.NOT_APPLICABLE, reason, source,
                observed_value=domain,
                limitation="The .example/.test/.invalid/.localhost/.local suffix is reserved for documentation, testing or local use.",
                evidence_id=ids.pop(0), checked_at=checked_at,
            ))
        return results

    # Domain registration age via the authoritative IANA RDAP bootstrap.
    rdap_source = EvidenceSourceType.RDAP
    try:
        record = lookup_domain_registration(domain, settings.tool_timeout_seconds)
        age_days = int(record["age_days"])
        is_new = age_days < settings.new_domain_threshold_days
        results.append(_check_result(
            VerificationCheckId.DOMAIN_AGE,
            EvidenceStatus.FLAG if is_new else EvidenceStatus.CLEAR,
            (
                f"The domain was registered {age_days} day(s) ago, which is within the configured {settings.new_domain_threshold_days}-day new-domain window."
                if is_new else f"The RDAP registration record indicates the domain is {age_days} day(s) old."
            ),
            rdap_source,
            severity=EvidenceSeverity.MEDIUM if is_new else EvidenceSeverity.INFORMATIONAL,
            observed_value=f"{age_days} day(s); registered {record['registration_date']}",
            source_url=record.get("rdap_url"),
            limitation="A newly registered domain can be legitimate, and an old domain can still be abused. Domain age is only one indicator.",
            details=record,
            evidence_id=ids.pop(0), checked_at=checked_at,
        ))
    except (DomainCheckError, httpx.HTTPError, ValueError, KeyError) as exc:
        results.append(_check_result(
            VerificationCheckId.DOMAIN_AGE, EvidenceStatus.UNAVAILABLE,
            "Domain registration age could not be established from RDAP.", rdap_source,
            observed_value=domain,
            limitation=f"RDAP lookup unavailable: {type(exc).__name__}: {str(exc)[:250]}",
            details={"domain": domain},
            evidence_id=ids.pop(0), checked_at=checked_at,
        ))

    # Website reachability. A response means the host answered; it does not mean it is genuine.
    try:
        site = check_website_availability(domain, settings.tool_timeout_seconds)
        results.append(_check_result(
            VerificationCheckId.WEBSITE_AVAILABILITY, EvidenceStatus.CLEAR,
            f"The submitted website responded to an HTTP request (status {site['http_status']}). This confirms reachability only.",
            EvidenceSourceType.COMPANY_WEBSITE,
            observed_value=f"HTTP {site['http_status']} · {site['url']}",
            source_url=site.get("final_url", site["url"]),
            limitation="A reachable website is not proof that it belongs to the named company or that the offer is genuine.",
            details=site,
            evidence_id=ids.pop(0), checked_at=checked_at,
        ))
    except (DomainCheckError, httpx.HTTPError, ValueError) as exc:
        message = str(exc)
        results.append(_check_result(
            VerificationCheckId.WEBSITE_AVAILABILITY, EvidenceStatus.UNAVAILABLE,
            "Website reachability could not be confirmed.", EvidenceSourceType.COMPANY_WEBSITE,
            observed_value=domain,
            limitation=f"Website request was not completed: {type(exc).__name__}: {message[:250]}",
            details={"domain": domain, "target_blocked": isinstance(exc, UnsafeTargetError)},
            evidence_id=ids.pop(0), checked_at=checked_at,
        ))

    # Verified HTTPS/TLS connection.
    try:
        certificate = check_ssl_certificate(domain, settings.tool_timeout_seconds)
        remaining = certificate.get("days_remaining")
        expiring_soon = isinstance(remaining, int) and remaining < 30
        results.append(_check_result(
            VerificationCheckId.SSL_CERTIFICATE,
            EvidenceStatus.FLAG if expiring_soon else EvidenceStatus.CLEAR,
            (
                f"The TLS certificate is valid but expires in {remaining} day(s)."
                if expiring_soon else "The HTTPS certificate chain and hostname validated successfully."
            ),
            EvidenceSourceType.TLS,
            severity=EvidenceSeverity.WEAK if expiring_soon else EvidenceSeverity.INFORMATIONAL,
            observed_value=f"Valid until {certificate.get('not_after')}; {remaining} day(s) remaining" if remaining is not None else "Certificate validated",
            source_url=f"https://{domain}/",
            limitation="A valid TLS certificate secures a connection to this domain; it does not verify company ownership or offer authenticity.",
            details=certificate,
            evidence_id=ids.pop(0), checked_at=checked_at,
        ))
    except DomainCheckError as exc:
        is_certificate_failure = "TLS certificate validation failed" in str(exc)
        results.append(_check_result(
            VerificationCheckId.SSL_CERTIFICATE,
            EvidenceStatus.FLAG if is_certificate_failure else EvidenceStatus.UNAVAILABLE,
            "The HTTPS certificate did not validate." if is_certificate_failure else "TLS certificate status could not be checked.",
            EvidenceSourceType.TLS,
            severity=EvidenceSeverity.MEDIUM if is_certificate_failure else EvidenceSeverity.INFORMATIONAL,
            observed_value=domain,
            source_url=f"https://{domain}/",
            limitation=f"{str(exc)[:400]}",
            details={"domain": domain},
            evidence_id=ids.pop(0), checked_at=checked_at,
        ))
    except (OSError, ssl.SSLError, TimeoutError) as exc:
        results.append(_check_result(
            VerificationCheckId.SSL_CERTIFICATE, EvidenceStatus.UNAVAILABLE,
            "TLS certificate status could not be checked.", EvidenceSourceType.TLS,
            observed_value=domain,
            limitation=f"TLS connection failed: {type(exc).__name__}.",
            details={"domain": domain},
            evidence_id=ids.pop(0), checked_at=checked_at,
        ))
    return results


def verify_extracted_offer(
    extracted: ExtractedOffer,
    settings: Settings | None = None,
) -> VerificationReport:
    """Run the six Phase 4 checks against extracted claims."""
    settings = settings or get_settings()
    checked_at = datetime.now(timezone.utc)
    candidates = _candidate_domains(extracted)
    primary_domain = _primary_domain(extracted)
    evidence_ids = [f"EV-{index:03d}" for index in range(1, 7)]

    checks_and_evidence = _external_domain_checks(
        primary_domain, settings, checked_at, evidence_ids[:3]
    )
    # The first helper consumes a copy; align the remaining IDs explicitly.
    # Its results already contain EV-001..EV-003.
    checks_and_evidence.append(_sender_domain_check(
        extracted, candidates, checked_at, "EV-004"
    ))
    checks_and_evidence.append(_metadata_check(
        extracted, extracted.pdf_metadata, checked_at, "EV-005"
    ))
    checks_and_evidence.append(_payment_check(
        extracted, checked_at, "EV-006"
    ))

    checks = [pair[0] for pair in checks_and_evidence]
    evidence = [pair[1] for pair in checks_and_evidence]
    completed_statuses = {EvidenceStatus.FLAG, EvidenceStatus.CLEAR}
    completed = sum(1 for check in checks if check.status in completed_statuses)
    incomplete = any(check.status in {EvidenceStatus.UNAVAILABLE, EvidenceStatus.ERROR} for check in checks)
    total = len(checks)
    return VerificationReport(
        checked_at=checked_at,
        overall_status=VerificationOverallStatus.PARTIAL if incomplete else VerificationOverallStatus.COMPLETED,
        completed_checks=completed,
        total_checks=total,
        coverage_percent=round((completed / total) * 100, 1) if total else 0.0,
        checks=checks,
        evidence=evidence,
        caveats=[
            "This phase reports independent check results and warning indicators; it does not calculate a fraud probability or genuine/fake verdict.",
            "A CLEAR result means only that this specific check did not observe its stated warning condition; it does not establish legitimacy.",
            "Unavailable and not-applicable checks are not treated as clean results.",
            "Website/domain checks depend on third-party registry, DNS and network availability and may vary between runs.",
        ],
    )
