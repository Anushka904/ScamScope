export type InputType = "text" | "image" | "pdf";
export type ExtractionStatus = "complete" | "partial" | "deterministic_fallback";

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
