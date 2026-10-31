export type InputType = "text" | "image" | "pdf";
export type ExtractionStatus = "complete" | "partial" | "deterministic_fallback";

export interface PDFMetadata {
  title: string | null;
  author: string | null;
  subject: string | null;
  creator: string | null;
  producer: string | null;
  creation_date_raw: string | null;
  modification_date_raw: string | null;
  page_count: number;
  is_encrypted: boolean;
}

export type EvidenceStatus = "flag" | "clear" | "unavailable" | "error" | "not_applicable";
export type EvidenceSeverity = "strong" | "medium" | "weak" | "informational";
export type VerificationCheckId =
  | "domain_age"
  | "website_availability"
  | "ssl_certificate"
  | "sender_domain_match"
  | "pdf_metadata"
  | "payment_red_flags";

export interface SourceExcerpt {
  field_name: string;
  quote: string;
  page_number: number | null;
}

/** Mirrors backend/app/models/extraction.py. Do not add inferred risk fields here. */
export interface ExtractedOffer {
  input_type: InputType;
  extraction_status: ExtractionStatus;
  company_name: string | null;
  claimed_company_website: string | null;
  role_title: string | null;
  salary_claim: string | null;
  claimed_issue_date: string | null;
  claimed_joining_date: string | null;
  recruiter_name: string | null;
  sender_email: string | null;
  sender_phone: string | null;
  domains: string[];
  urls: string[];
  phone_numbers: string[];
  upi_ids: string[];
  payment_demand: boolean;
  payment_amount: string | null;
  payment_demand_phrases: string[];
  urgency_phrases: string[];
  evidence_excerpts: SourceExcerpt[];
  extraction_warnings: string[];
  pdf_metadata: PDFMetadata | null;
}

export interface VerificationCheck {
  check_id: VerificationCheckId;
  label: string;
  status: EvidenceStatus;
  severity: EvidenceSeverity;
  finding: string;
  observed_value: string | null;
  source_type: string;
  source_url: string | null;
  checked_at: string;
  limitation: string | null;
  details: Record<string, unknown>;
  evidence_ids: string[];
}

export interface VerificationEvidence {
  evidence_id: string;
  check_name: string;
  status: EvidenceStatus;
  severity: EvidenceSeverity;
  finding: string;
  observed_value: string | null;
  source_type: string;
  source_name: string | null;
  source_url: string | null;
  source_excerpt: string | null;
  page_number: number | null;
  checked_at: string | null;
  limitation: string | null;
  details: Record<string, unknown>;
}

export interface VerificationReport {
  verification_id: string;
  checked_at: string;
  overall_status: "completed" | "partial";
  completed_checks: number;
  total_checks: number;
  coverage_percent: number;
  checks: VerificationCheck[];
  evidence: VerificationEvidence[];
  caveats: string[];
}

export interface ExtractionSession {
  extraction: ExtractedOffer;
  submittedText: string;
  fileName: string | null;
  filePreviewUrl: string | null;
  createdAt: string;
  durationMs: number;
}

export interface ApiErrorShape {
  detail?: string | { msg?: string; message?: string }[];
}
