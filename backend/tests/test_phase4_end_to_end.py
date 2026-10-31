"""Regression tests for the complete Phase 4 PDF -> extract -> verify flow."""

from io import BytesIO

import pymupdf
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def make_pdf_offer() -> bytes:
    """Build a selectable PDF with real embedded metadata and known claims."""
    document = pymupdf.open()
    page = document.new_page()
    page.insert_textbox(
        pymupdf.Rect(55, 55, 540, 770),
        """NORTHSTAR ANALYTICS PVT. LTD.
FICTIONAL INTERNSHIP OFFER - QA TEST
Date: 31 October 2026

Dear Candidate,
We are pleased to offer you the position of Data Analyst Intern at Northstar Analytics Pvt. Ltd.

Position: Data Analyst Intern
Monthly stipend: INR 30,000
Joining date: 1 December 2026
Claimed company website
https://northstar-analytics.example

There is no registration fee, training fee, security deposit, equipment charge, or other payment required.
No payment is requested from the candidate.

Recruiter: Priya Mehta
Email: northstar.recruitment@gmail.com
Phone: +91 9123456780

Regards,
Priya Mehta
Recruitment Team

TEST FIXTURE NOTICE: Northstar Analytics Pvt. Ltd. is fictional. The sender uses Gmail rather than a company-domain email. These deliberate inconsistencies are for QA only.""",
        fontsize=10,
        lineheight=1.35,
    )
    document.set_metadata({
        "title": "Northstar QA Offer",
        "author": "ScamScope QA Fixture",
        "subject": "Synthetic Phase 4 test offer",
        "creator": "ScamScope Test Generator",
        "producer": "PyMuPDF QA Fixture",
        "creationDate": "D:20261031103000Z",
        "modDate": "D:20261031103000Z",
        "keywords": "ScamScope, test, fictional",
    })
    pdf_bytes = document.tobytes()
    document.close()
    return pdf_bytes


def test_pdf_extract_and_verify_full_phase4_pipeline():
    pdf_bytes = make_pdf_offer()

    extraction_response = client.post(
        "/api/extract",
        files={"file": ("northstar-qa-offer.pdf", BytesIO(pdf_bytes), "application/pdf")},
    )
    assert extraction_response.status_code == 200, extraction_response.text
    extracted = extraction_response.json()

    # Company/website regression: do not misread "company-domain" in the
    # disclaimer as a company label, and handle a website value on the next PDF line.
    assert extracted["company_name"] == "NORTHSTAR ANALYTICS PVT. LTD."
    assert extracted["claimed_company_website"] == "https://northstar-analytics.example"
    website_evidence = next(
        item for item in extracted["evidence_excerpts"]
        if item["field_name"] == "claimed_company_website"
    )
    assert "https://northstar-analytics.example" in website_evidence["quote"]
    assert extracted["role_title"] == "Data Analyst Intern"
    assert extracted["salary_claim"] == "INR 30,000 / month"
    assert extracted["claimed_joining_date"] == "1 December 2026"
    assert extracted["recruiter_name"] == "Priya Mehta"
    assert extracted["sender_email"] == "northstar.recruitment@gmail.com"
    assert extracted["payment_demand"] is False

    metadata = extracted["pdf_metadata"]
    assert metadata is not None
    assert metadata["title"] == "Northstar QA Offer"
    assert metadata["author"] == "ScamScope QA Fixture"
    assert metadata["subject"] == "Synthetic Phase 4 test offer"
    assert metadata["creator"] == "ScamScope Test Generator"
    assert metadata["producer"] == "PyMuPDF QA Fixture"
    assert metadata["creation_date_raw"] == "D:20261031103000Z"
    assert metadata["modification_date_raw"] == "D:20261031103000Z"
    assert metadata["page_count"] == 1

    verification_response = client.post(
        "/api/verify",
        json={"extracted": extracted},
    )
    assert verification_response.status_code == 200, verification_response.text
    verification = verification_response.json()
    checks = {item["check_id"]: item for item in verification["checks"]}

    assert len(checks) == 6
    assert checks["domain_age"]["status"] == "not_applicable"
    assert checks["website_availability"]["status"] == "not_applicable"
    assert checks["ssl_certificate"]["status"] == "not_applicable"
    assert checks["sender_domain_match"]["status"] == "flag"
    assert checks["pdf_metadata"]["status"] == "clear"
    assert checks["pdf_metadata"]["details"]["title"] == "Northstar QA Offer"
    assert checks["pdf_metadata"]["details"]["author"] == "ScamScope QA Fixture"
    assert checks["pdf_metadata"]["details"]["subject"] == "Synthetic Phase 4 test offer"
    assert checks["pdf_metadata"]["details"]["creator"] == "ScamScope Test Generator"
    assert checks["pdf_metadata"]["details"]["producer"] == "PyMuPDF QA Fixture"
    assert checks["pdf_metadata"]["details"]["creation_date_parsed"] == "2026-10-31T10:30:00+00:00"
    assert checks["pdf_metadata"]["details"]["modification_date_parsed"] == "2026-10-31T10:30:00+00:00"
    assert checks["payment_red_flags"]["status"] == "clear"
    assert len(verification["evidence"]) == 6
    assert "risk_score" not in verification


def test_company_domain_phrase_cannot_be_mistaken_for_company_label():
    text = """NORTHSTAR ANALYTICS PVT. LTD.

The sender uses Gmail rather than a company-domain email.
These deliberate inconsistencies are included for test purposes.
"""
    response = client.post("/api/extract", data={"text": text})
    assert response.status_code == 200, response.text
    assert response.json()["company_name"] == "NORTHSTAR ANALYTICS PVT. LTD."
