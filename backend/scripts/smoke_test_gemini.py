"""One-call live smoke test for the Phase 3 Gemini extraction pipeline.

Run from backend after activating the project virtual environment:
    python -m scripts.smoke_test_gemini

This makes one real Gemini API request using the root .env credentials.
"""

from __future__ import annotations

import sys

from app.agents.extractor import ExtractionError, extract_offer
from app.config import get_settings
from app.models.extraction import ExtractionStatus, InputType
from app.models.input import PreparedInput


SAMPLE_TEXT = (
    "Example Robotics is hiring a Software Developer Intern. "
    "Monthly stipend: ₹25,000. Pay ₹2,000 as a registration fee "
    "to confirm selection. Contact: hr@example.com. "
    "UPI ID: example@okaxis."
)


def main() -> int:
    settings = get_settings()
    if not settings.gemini_configured:
        print("FAIL: Gemini is not configured. Check the root .env file.")
        return 2

    prepared = PreparedInput(
        input_type=InputType.TEXT,
        mime_type="text/plain",
        text_content=SAMPLE_TEXT,
        visual_assets=[],
        warnings=[],
    )

    print(f"Testing ScamScope extraction with model: {settings.gemini_model}")
    print("Submitting one synthetic text-only offer; API key will not be displayed.")

    try:
        result = extract_offer(prepared, settings=settings)
    except ExtractionError as exc:
        print(f"FAIL: extraction returned HTTP {exc.status_code}: {exc.detail}")
        return 1
    except Exception as exc:  # pragma: no cover - defensive CLI boundary
        print(f"FAIL: unexpected {type(exc).__name__}: {exc}")
        return 1

    print(f"Extraction status: {result.extraction_status.value}")
    print(f"Company: {result.company_name or 'NOT EXTRACTED'}")
    print(f"Role: {result.role_title or 'NOT EXTRACTED'}")
    print(f"Payment demand: {result.payment_demand}")
    print(f"Payment amount: {result.payment_amount or 'NOT EXTRACTED'}")
    print(f"Sender email: {result.sender_email or 'NOT EXTRACTED'}")
    print(f"UPI IDs: {', '.join(result.upi_ids) if result.upi_ids else 'NOT EXTRACTED'}")

    checks = {
        "company": bool(result.company_name and "example robotics" in result.company_name.casefold()),
        "role": bool(result.role_title and "software developer intern" in result.role_title.casefold()),
        "payment demand": result.payment_demand is True,
        "payment amount": bool(result.payment_amount and "2,000" in result.payment_amount),
        "email": result.sender_email == "hr@example.com",
        "UPI": result.upi_ids == ["example@okaxis"],
    }

    print("\nField checks:")
    for name, passed in checks.items():
        print(f"  {'PASS' if passed else 'FAIL'}  {name}")

    if result.extraction_warnings:
        print("\nWarnings:")
        for warning in result.extraction_warnings:
            print(f"  - {warning}")

    if result.extraction_status != ExtractionStatus.COMPLETE:
        print("\nFAIL: Gemini did not complete every extraction task; fallback/partial output is not an AI success.")
        return 1

    if not all(checks.values()):
        print("\nFAIL: Gemini responded, but one or more expected fields were not extracted.")
        return 1

    print("\nPASS: Gemini extraction and local Pydantic validation both succeeded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
