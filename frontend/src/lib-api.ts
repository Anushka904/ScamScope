import type { ApiErrorShape, ExtractedOffer, InputType, SourceExcerpt, PDFMetadata, VerificationReport, VerificationCheck, VerificationEvidence, EvidenceStatus, EvidenceSeverity, VerificationCheckId } from "./types";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
const configuredTimeout = Number(import.meta.env.VITE_REQUEST_TIMEOUT_MS || "900000");
export const REQUEST_TIMEOUT_MS = Number.isFinite(configuredTimeout) && configuredTimeout >= 30_000
  ? Math.min(configuredTimeout, 1_800_000)
  : 900_000;

export class ApiError extends Error {
  readonly status: number;
  readonly code: "validation" | "offline" | "timeout" | "cancelled" | "server" | "unexpected";

  constructor(
    message: string,
    status = 0,
    code: ApiError["code"] = "unexpected",
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const nullableString = (value: unknown): string | null =>
  typeof value === "string" && value.trim() ? value.trim() : null;

const stringArray = (value: unknown): string[] =>
  Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string").map((item) => item.trim()).filter(Boolean)
    : [];

function normalizePdfMetadata(value: unknown): PDFMetadata | null {
  if (!isRecord(value)) return null;
  const number = typeof value.page_count === "number" && Number.isInteger(value.page_count) && value.page_count >= 0 ? value.page_count : null;
  if (number === null) return null;
  return {
    title: nullableString(value.title),
    author: nullableString(value.author),
    subject: nullableString(value.subject),
    creator: nullableString(value.creator),
    producer: nullableString(value.producer),
    creation_date_raw: nullableString(value.creation_date_raw),
    modification_date_raw: nullableString(value.modification_date_raw),
    page_count: number,
    is_encrypted: value.is_encrypted === true,
  };
}

function normalizeExcerpt(value: unknown): SourceExcerpt | null {
  if (!isRecord(value)) return null;
  const fieldName = nullableString(value.field_name);
  const quote = nullableString(value.quote);
  if (!fieldName || !quote) return null;
  const page = typeof value.page_number === "number" && Number.isInteger(value.page_number) && value.page_number > 0
    ? value.page_number
    : null;
  return { field_name: fieldName, quote, page_number: page };
}

/**
 * Normalize the current FastAPI response and the downloadable report wrapper.
 * The API contract remains the source of truth; unknown fields are not inferred.
 */
export function normalizeExtractedOffer(payload: unknown): ExtractedOffer {
  if (!isRecord(payload)) {
    throw new ApiError("The backend returned an empty or invalid extraction response.", 502, "unexpected");
  }

  const candidate = isRecord(payload.extraction) ? payload.extraction : payload;
  const inputType = candidate.input_type;
  const status = candidate.extraction_status;
  if (inputType !== "text" && inputType !== "image" && inputType !== "pdf") {
    throw new ApiError("The backend response is missing a valid input_type.", 502, "unexpected");
  }
  if (status !== "complete" && status !== "partial" && status !== "deterministic_fallback") {
    throw new ApiError("The backend response is missing a valid extraction_status.", 502, "unexpected");
  }
  const validInputType: InputType = inputType;
  const validStatus = status;

  // The current backend is Pydantic validated. These defaults additionally keep
  // the UI resilient if an older response omits nullable/list fields.
  return {
    input_type: validInputType,
    extraction_status: validStatus,
    company_name: nullableString(candidate.company_name),
    claimed_company_website: nullableString(candidate.claimed_company_website),
    role_title: nullableString(candidate.role_title),
    salary_claim: nullableString(candidate.salary_claim),
    claimed_issue_date: nullableString(candidate.claimed_issue_date),
    claimed_joining_date: nullableString(candidate.claimed_joining_date),
    recruiter_name: nullableString(candidate.recruiter_name),
    sender_email: nullableString(candidate.sender_email),
    sender_phone: nullableString(candidate.sender_phone),
    domains: stringArray(candidate.domains),
    urls: stringArray(candidate.urls),
    phone_numbers: stringArray(candidate.phone_numbers),
    upi_ids: stringArray(candidate.upi_ids),
    payment_demand: candidate.payment_demand === true,
    payment_amount: nullableString(candidate.payment_amount),
    payment_demand_phrases: stringArray(candidate.payment_demand_phrases),
    urgency_phrases: stringArray(candidate.urgency_phrases),
    evidence_excerpts: Array.isArray(candidate.evidence_excerpts)
      ? candidate.evidence_excerpts.map(normalizeExcerpt).filter((item): item is SourceExcerpt => item !== null)
      : [],
    extraction_warnings: stringArray(candidate.extraction_warnings),
    pdf_metadata: normalizePdfMetadata(candidate.pdf_metadata),
  };
}

async function readError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as ApiErrorShape;
    if (typeof payload.detail === "string") return payload.detail;
    if (Array.isArray(payload.detail)) {
      return payload.detail.map((item) => item.msg || item.message || "Invalid input").join("; ");
    }
  } catch {
    // A non-JSON response is handled with the status-specific message below.
  }

  const messages: Record<number, string> = {
    400: "Submit either one file or pasted text—not both.",
    413: "The submitted file is larger than the backend upload limit.",
    415: "The backend does not support this file type.",
    422: "The backend could not process this input. Check that the document is readable.",
    429: "The optional Gemini provider rate limit was reached. The default local rule-based extraction does not require Gemini quota.",
    502: "The extraction provider failed. Check the backend terminal for details.",
    503: "The extraction provider is not configured or is temporarily unavailable. The local rule-based engine should remain available for readable text.",
    504: "The Gemini request timed out. Check the backend terminal before retrying.",
  };
  return messages[response.status] || `The API returned HTTP ${response.status}.`;
}

export async function checkApiHealth(signal?: AbortSignal): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/health`, {
      method: "GET",
      signal,
      headers: { Accept: "application/json" },
    });
    return response.ok;
  } catch {
    return false;
  }
}

export async function extractOffer(
  input: { file?: File | null; text?: string },
  externalSignal?: AbortSignal,
): Promise<ExtractedOffer> {
  const hasFile = Boolean(input.file);
  const hasText = Boolean(input.text?.trim());
  if (hasFile === hasText) {
    throw new ApiError("Choose exactly one input: upload a file or paste offer text.", 400, "validation");
  }

  const body = new FormData();
  if (input.file) body.append("file", input.file, input.file.name);
  if (hasText) body.append("text", input.text!.trim());

  const controller = new AbortController();
  let timedOut = false;
  const timeoutId = window.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, REQUEST_TIMEOUT_MS);
  const abortFromCaller = () => controller.abort();
  externalSignal?.addEventListener("abort", abortFromCaller, { once: true });
  if (externalSignal?.aborted) controller.abort();

  try {
    const response = await fetch(`${API_BASE_URL}/api/extract`, {
      method: "POST",
      body,
      signal: controller.signal,
      headers: { Accept: "application/json" },
    });

    if (!response.ok) {
      const message = await readError(response);
      const code = response.status >= 500 ? "server" : response.status === 400 || response.status === 413 || response.status === 415 || response.status === 422 ? "validation" : "unexpected";
      throw new ApiError(message, response.status, code);
    }

    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      throw new ApiError("The backend response was not valid JSON.", response.status, "unexpected");
    }
    return normalizeExtractedOffer(payload);
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (controller.signal.aborted) {
      if (externalSignal?.aborted) {
        throw new ApiError("You stopped waiting for this request. The backend may still be processing it; check its terminal before starting another request.", 0, "cancelled");
      }
      if (timedOut) {
        throw new ApiError(`The browser wait window (${Math.round(REQUEST_TIMEOUT_MS / 60_000)} minutes) expired. The backend may still be processing; check its terminal before retrying.`, 408, "timeout");
      }
    }
    if (error instanceof TypeError) {
      throw new ApiError(`ScamScope could not reach the backend at ${API_BASE_URL}. Start the FastAPI server and check its terminal.`, 0, "offline");
    }
    throw new ApiError(error instanceof Error ? error.message : "An unexpected network error occurred.", 0, "unexpected");
  } finally {
    window.clearTimeout(timeoutId);
    externalSignal?.removeEventListener("abort", abortFromCaller);
  }
}

const EVIDENCE_STATUSES: EvidenceStatus[] = ["flag", "clear", "unavailable", "error", "not_applicable"];
const EVIDENCE_SEVERITIES: EvidenceSeverity[] = ["strong", "medium", "weak", "informational"];
const CHECK_IDS: VerificationCheckId[] = ["domain_age", "website_availability", "ssl_certificate", "sender_domain_match", "pdf_metadata", "payment_red_flags"];

function normalizeVerificationCheck(value: unknown): VerificationCheck | null {
  if (!isRecord(value)) return null;
  if (!CHECK_IDS.includes(value.check_id as VerificationCheckId)) return null;
  if (!EVIDENCE_STATUSES.includes(value.status as EvidenceStatus)) return null;
  if (!EVIDENCE_SEVERITIES.includes(value.severity as EvidenceSeverity)) return null;
  const label = nullableString(value.label);
  const finding = nullableString(value.finding);
  const checkedAt = nullableString(value.checked_at);
  if (!label || !finding || !checkedAt) return null;
  return {
    check_id: value.check_id as VerificationCheckId,
    label,
    status: value.status as EvidenceStatus,
    severity: value.severity as EvidenceSeverity,
    finding,
    observed_value: nullableString(value.observed_value),
    source_type: nullableString(value.source_type) || "unknown",
    source_url: nullableString(value.source_url),
    checked_at: checkedAt,
    limitation: nullableString(value.limitation),
    details: isRecord(value.details) ? value.details : {},
    evidence_ids: stringArray(value.evidence_ids),
  };
}

function normalizeVerificationEvidence(value: unknown): VerificationEvidence | null {
  if (!isRecord(value)) return null;
  if (!EVIDENCE_STATUSES.includes(value.status as EvidenceStatus)) return null;
  if (!EVIDENCE_SEVERITIES.includes(value.severity as EvidenceSeverity)) return null;
  const evidenceId = nullableString(value.evidence_id);
  const checkName = nullableString(value.check_name);
  const finding = nullableString(value.finding);
  if (!evidenceId || !checkName || !finding) return null;
  return {
    evidence_id: evidenceId,
    check_name: checkName,
    status: value.status as EvidenceStatus,
    severity: value.severity as EvidenceSeverity,
    finding,
    observed_value: nullableString(value.observed_value),
    source_type: nullableString(value.source_type) || "unknown",
    source_name: nullableString(value.source_name),
    source_url: nullableString(value.source_url),
    source_excerpt: nullableString(value.source_excerpt),
    page_number: typeof value.page_number === "number" && Number.isInteger(value.page_number) && value.page_number > 0 ? value.page_number : null,
    checked_at: nullableString(value.checked_at),
    limitation: nullableString(value.limitation),
    details: isRecord(value.details) ? value.details : {},
  };
}

export function normalizeVerificationReport(payload: unknown): VerificationReport {
  if (!isRecord(payload)) throw new ApiError("The backend returned an invalid verification response.", 502, "unexpected");
  if (payload.overall_status !== "completed" && payload.overall_status !== "partial") {
    throw new ApiError("The verification response is missing a valid overall_status.", 502, "unexpected");
  }
  const checks = Array.isArray(payload.checks) ? payload.checks.map(normalizeVerificationCheck).filter((item): item is VerificationCheck => item !== null) : [];
  const evidence = Array.isArray(payload.evidence) ? payload.evidence.map(normalizeVerificationEvidence).filter((item): item is VerificationEvidence => item !== null) : [];
  if (checks.length !== 6) throw new ApiError("The verification response did not contain all six check categories.", 502, "unexpected");
  const verificationId = nullableString(payload.verification_id);
  const checkedAt = nullableString(payload.checked_at);
  if (!verificationId || !checkedAt) throw new ApiError("The verification response is missing its identifier or timestamp.", 502, "unexpected");
  const completed = typeof payload.completed_checks === "number" ? payload.completed_checks : 0;
  const total = typeof payload.total_checks === "number" ? payload.total_checks : checks.length;
  const coverage = typeof payload.coverage_percent === "number" ? payload.coverage_percent : 0;
  if (completed < 0 || total !== 6 || coverage < 0 || coverage > 100) throw new ApiError("The verification response has invalid coverage values.", 502, "unexpected");
  return {
    verification_id: verificationId,
    checked_at: checkedAt,
    overall_status: payload.overall_status,
    completed_checks: completed,
    total_checks: total,
    coverage_percent: coverage,
    checks,
    evidence,
    caveats: stringArray(payload.caveats),
  };
}


export interface InvestigationRecordInput {
  extraction: ExtractedOffer;
  verification: VerificationReport | null;
  submittedFile: string | null;
  submittedText?: string;
  localEditsWereIncluded: boolean;
  extractionTimeMs: number;
  generatedAt?: string;
}

/** Build a complete downloadable record. A report without verification is rejected. */
export function buildInvestigationRecord(input: InvestigationRecordInput) {
  if (!input.verification) {
    throw new ApiError("Verification must finish successfully before the complete investigation record can be exported.", 0, "unexpected");
  }
  return {
    product: "ScamScope",
    report_type: "phase-4-investigation-record" as const,
    schema_version: "phase-4-verification" as const,
    generated_at: input.generatedAt || new Date().toISOString(),
    notice: "This record contains extracted claims and individual verification check results. It is not a fraud probability or genuine/fake verdict.",
    submitted_file: input.submittedFile,
    ...(input.submittedText ? { submitted_text: input.submittedText } : {}),
    extraction: input.extraction,
    verification_status: "completed" as const,
    verification: input.verification,
    local_edits_were_included_in_verification: input.localEditsWereIncluded,
    extraction_time_ms: input.extractionTimeMs,
  };
}

export async function verifyOffer(
  extracted: ExtractedOffer,
  externalSignal?: AbortSignal,
): Promise<VerificationReport> {
  const controller = new AbortController();
  let timedOut = false;
  const timeoutId = window.setTimeout(() => { timedOut = true; controller.abort(); }, 60_000);
  const abortFromCaller = () => controller.abort();
  externalSignal?.addEventListener("abort", abortFromCaller, { once: true });
  if (externalSignal?.aborted) controller.abort();
  try {
    const response = await fetch(`${API_BASE_URL}/api/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ extracted }),
      signal: controller.signal,
    });
    if (!response.ok) {
      const message = await readError(response);
      throw new ApiError(message, response.status, response.status >= 500 ? "server" : "unexpected");
    }
    let payload: unknown;
    try { payload = await response.json(); }
    catch { throw new ApiError("The verification response was not valid JSON.", response.status, "unexpected"); }
    return normalizeVerificationReport(payload);
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (controller.signal.aborted) {
      if (externalSignal?.aborted) throw new ApiError("Verification was cancelled.", 0, "cancelled");
      if (timedOut) throw new ApiError("Verification exceeded its 60-second browser wait limit. The backend may still be processing the checks.", 408, "timeout");
    }
    if (error instanceof TypeError) throw new ApiError(`ScamScope could not reach the verification API at ${API_BASE_URL}.`, 0, "offline");
    throw new ApiError(error instanceof Error ? error.message : "An unexpected verification error occurred.", 0, "unexpected");
  } finally {
    window.clearTimeout(timeoutId);
    externalSignal?.removeEventListener("abort", abortFromCaller);
  }
}

export { API_BASE_URL };
