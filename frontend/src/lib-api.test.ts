import { describe, expect, it } from "vitest";
import { normalizeExtractedOffer, extractOffer, ApiError } from "./lib-api";

const sampleExtraction = {
  input_type: "text",
  extraction_status: "complete",
  company_name: "Nexora Technologies Pvt. Ltd.",
  claimed_company_website: "www.nexora-careers.example",
  role_title: "Software Developer Intern",
  salary_claim: "₹25,000",
  claimed_issue_date: null,
  claimed_joining_date: "15 November 2026",
  recruiter_name: "Rahul Sharma",
  sender_email: "rahul@nexora-careers.example",
  sender_phone: "+91 9876543210",
  domains: ["www.nexora-careers.example"],
  urls: [],
  phone_numbers: ["+91 9876543210"],
  upi_ids: ["nexora.hr@okaxis"],
  payment_demand: true,
  payment_amount: "₹2,499",
  payment_demand_phrases: ["you must pay a refundable registration and onboarding fee of ₹2,499 within 24 hours."],
  urgency_phrases: ["within 24 hours."],
  evidence_excerpts: [
    { field_name: "company_name", quote: "Nexora Technologies Pvt. Ltd.", page_number: null },
    { field_name: "upi_ids", quote: "UPI ID: nexora.hr@okaxis", page_number: null },
  ],
  extraction_warnings: [],
};

describe("normalizeExtractedOffer", () => {
  it("normalizes the current API extraction response", () => {
    const result = normalizeExtractedOffer(sampleExtraction);
    expect(result.company_name).toBe("Nexora Technologies Pvt. Ltd.");
    expect(result.payment_demand).toBe(true);
    expect(result.upi_ids).toEqual(["nexora.hr@okaxis"]);
    expect(result.evidence_excerpts).toHaveLength(2);
  });

  it("accepts the downloadable report wrapper without confusing it with a verdict", () => {
    const result = normalizeExtractedOffer({
      product: "ScamScope",
      report_type: "extraction_record_only",
      notice: "Not a fraud verdict",
      extraction: sampleExtraction,
    });
    expect(result.extraction_status).toBe("complete");
    expect(result.company_name).toBe("Nexora Technologies Pvt. Ltd.");
  });

  it("defaults missing nullable and list properties safely", () => {
    const result = normalizeExtractedOffer({
      input_type: "text",
      extraction_status: "partial",
      payment_demand: false,
    });
    expect(result.company_name).toBeNull();
    expect(result.domains).toEqual([]);
    expect(result.urls).toEqual([]);
    expect(result.evidence_excerpts).toEqual([]);
    expect(result.extraction_warnings).toEqual([]);
  });

  it("drops malformed evidence excerpts rather than crashing the report", () => {
    const result = normalizeExtractedOffer({
      ...sampleExtraction,
      evidence_excerpts: [
        { field_name: "role_title", quote: "Software Developer Intern", page_number: null },
        { field_name: "invalid quote", quote: "   ", page_number: 0 },
        null,
      ],
    });
    expect(result.evidence_excerpts).toHaveLength(1);
  });

  it("rejects a non-object response", () => {
    expect(() => normalizeExtractedOffer(null)).toThrow(ApiError);
  });

  it("rejects a response with no extraction status instead of claiming success", () => {
    expect(() => normalizeExtractedOffer({ input_type: "text" })).toThrow(/extraction_status/);
  });

  it("rejects a response with an unsupported input type", () => {
    expect(() => normalizeExtractedOffer({ input_type: "docx", extraction_status: "complete" })).toThrow(/input_type/);
  });

  it("rejects a request with neither a file nor text", async () => {
    await expect(extractOffer({})).rejects.toBeInstanceOf(ApiError);
  });

  it("rejects a request with both a file and text", async () => {
    const file = new File(["offer"], "offer.txt", { type: "text/plain" });
    await expect(extractOffer({ file, text: "This is some offer text." })).rejects.toBeInstanceOf(ApiError);
  });
});
