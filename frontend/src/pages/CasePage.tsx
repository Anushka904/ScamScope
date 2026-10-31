import { useEffect, useMemo, useState, type ComponentType } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  AlertTriangle, ArrowLeft, ArrowUpRight, ChevronDown, CircleHelp,
  Clipboard, Download, FileText, Fingerprint, Globe2, LockKeyhole,
  Mail, Printer, RefreshCw, ShieldAlert, Wallet, CalendarDays,
  Phone, UserRound, Link2, Quote, Info,
} from "lucide-react";
import type { ExtractionSession, ExtractedOffer, SourceExcerpt, VerificationCheck } from "../types";
import { ApiError, buildInvestigationRecord, verifyOffer } from "../lib-api";

const checkIcons = {
  domain_age: Globe2,
  website_availability: Globe2,
  ssl_certificate: LockKeyhole,
  sender_domain_match: Mail,
  pdf_metadata: FileText,
  payment_red_flags: Wallet,
} as const;

function statusLabel(status: VerificationCheck["status"]) {
  const labels = { flag: "FLAGGED", clear: "CLEAR", unavailable: "UNAVAILABLE", error: "ERROR", not_applicable: "N/A" };
  return labels[status];
}

function safeValue(value: string | null | undefined) {
  return value?.trim() || "Not found in submitted material";
}

function Field({ label, value, icon: Icon }: { label: string; value: string | null | undefined; icon?: ComponentType<{ size?: number }> }) {
  return (
    <div className="result-field">
      <span className="result-field-label">{Icon && <Icon size={13} />}{label}</span>
      <b>{safeValue(value)}</b>
    </div>
  );
}

function ListField({ label, values, icon: Icon }: { label: string; values: string[]; icon?: ComponentType<{ size?: number }> }) {
  return <Field label={label} value={values.length ? values.join(", ") : null} icon={Icon} />;
}

function FieldEditor({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <label className="editor-field"><span>{label}</span><input value={value} onChange={(event) => onChange(event.target.value)} /></label>;
}

function PhraseList({ title, values, tone }: { title: string; values: string[]; tone: "ember" | "amber" }) {
  return (
    <section className={`phrase-card phrase-${tone}`}>
      <div className="phrase-card-title"><Quote size={14} /><b>{title}</b><span>{values.length.toString().padStart(2, "0")}</span></div>
      {values.length ? (
        <ul>{values.map((value, index) => <li key={`${index}-${value}`}>“{value}”</li>)}</ul>
      ) : <p className="phrase-empty">No {title.toLowerCase()} were returned by the extractor.</p>}
      <small>Extracted language only. Context and meaning should be reviewed manually.</small>
    </section>
  );
}

export function CasePage() {
  const location = useLocation();
  const session = location.state as ExtractionSession | null;
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState<number | null>(0);
  const [showEditor, setShowEditor] = useState(false);
  const [draft, setDraft] = useState<Partial<ExtractedOffer>>({});

  const extracted = session?.extraction;
  const merged = useMemo(() => extracted ? { ...extracted, ...draft } : null, [extracted, draft]);
  const [verification, setVerification] = useState<Awaited<ReturnType<typeof verifyOffer>> | null>(null);
  const [verificationError, setVerificationError] = useState("");
  const [isChecking, setIsChecking] = useState(false);

  useEffect(() => {
    if (!merged) return;
    const controller = new AbortController();
    // A verification result is valid only for the exact claims sent to the API.
    // Re-run automatically whenever a local draft field changes, and abort the
    // prior request so an older response cannot overwrite the newer result.
    setVerification(null);
    setVerificationError("");
    setIsChecking(true);
    verifyOffer(merged, controller.signal)
      .then((result) => { if (!controller.signal.aborted) setVerification(result); })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setVerificationError(error instanceof ApiError ? error.message : error instanceof Error ? error.message : "Verification could not be completed.");
      })
      .finally(() => { if (!controller.signal.aborted) setIsChecking(false); });
    return () => controller.abort();
  }, [merged]);

  if (!session || !extracted || !merged) {
    return (
      <main className="app-page empty-case">
        <div className="empty-case-card panel">
          <span className="empty-icon"><FileText size={24} /></span>
          <p className="eyebrow">NO ACTIVE CASE IN THIS TAB</p>
          <h1>Your evidence file<br /><em>hasn't been opened.</em></h1>
          <p>For privacy, this frontend keeps the active case in navigation state only. Refreshing or reopening the report clears the case from this tab.</p>
          <Link to="/investigate" className="button button-primary">Start an investigation <ArrowUpRight size={16} /></Link>
        </div>
      </main>
    );
  }

  const fallback = extracted.extraction_status === "deterministic_fallback";
  const partial = extracted.extraction_status === "partial";
  const excerpts: SourceExcerpt[] = merged.evidence_excerpts || [];

  const verificationEmail = `Subject: Request for verification of recruitment communication\n\nHello${merged.recruiter_name ? ` ${merged.recruiter_name}` : ""},\n\nI received a communication regarding the ${merged.role_title || "role"} position at ${merged.company_name || "your organization"}.\n\nBefore proceeding, could you please confirm:\n1. Whether this opportunity and the sender address ${merged.sender_email || "[sender email]"} are officially associated with your organization.\n2. Whether the stated compensation and joining details are accurate.\n3. Whether any registration, onboarding, training or document-verification payment is officially required.\n\nI will not share payment or sensitive identity details until I can independently verify the opportunity through an official company channel.\n\nThank you.`;

  const copyEmail = async () => {
    try {
      await navigator.clipboard.writeText(verificationEmail);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2200);
    } catch {
      window.prompt("Copy this verification email:", verificationEmail);
    }
  };

  const downloadReport = () => {
    const report = buildInvestigationRecord({
      submittedFile: session.fileName,
      submittedText: session.submittedText,
      extraction: merged,
      verification,
      localEditsWereIncluded: localEditCount > 0,
      extractionTimeMs: session.durationMs,
    });
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "scamscope-investigation-record.json";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  const setDraftValue = (key: keyof ExtractedOffer, value: string | boolean | string[] | null) => {
    // Never leave a result for the previous draft visible or exportable.
    setVerification(null);
    setVerificationError("");
    setDraft((current) => ({ ...current, [key]: value }) as Partial<ExtractedOffer>);
  };

  const rerunChecks = async () => {
    setIsChecking(true);
    setVerification(null);
    setVerificationError("");
    try {
      const result = await verifyOffer(merged);
      setVerification(result);
    } catch (error) {
      setVerificationError(error instanceof ApiError ? error.message : error instanceof Error ? error.message : "Verification could not be completed.");
    } finally {
      setIsChecking(false);
    }
  };

  const localEditCount = Object.keys(draft).length;

  return (
    <main className="app-page case-page">
      <div className="case-topline">
        <Link to="/investigate" className="back-link"><ArrowLeft size={15} /> New investigation</Link>
        <span>CASE FILE / INVESTIGATION RECORD</span>
        <div className="case-top-actions">
          <button className="button button-outline button-small print-button" onClick={() => window.print()}><Printer size={14} /> Print / Save PDF</button>
          <button className="button button-outline button-small" onClick={downloadReport} disabled={!verification || isChecking} title={!verification ? "Wait for all verification checks to finish before exporting the complete record." : "Download the complete investigation record"}><Download size={14} /> {isChecking || !verification ? "Verification pending" : "Download JSON"}</button>
        </div>
      </div>

      <section className={`case-verdict panel ${fallback ? "verdict-fallback" : ""}`}>
        <div className="case-verdict-mark"><CircleHelp size={20} /></div>
        <div className="case-verdict-copy">
          <p className="eyebrow">ASSESSMENT STATUS / NOT SCORED</p>
          <h1>UNVERIFIED</h1>
          <p>{fallback ? "Rule-based extraction was used. It captures explicit patterns in selectable text; fields may be incomplete." : partial ? "The extraction is partial. Some fields or evidence could not be extracted." : "Structured extraction completed. This is not a fraud verdict and does not establish that the offer is genuine."}</p>
        </div>
        <div className="case-verdict-side">
          <span className={`status-pill ${fallback ? "pill-warning" : partial ? "pill-muted" : "pill-teal"}`}>{fallback ? "Rule-based analysis" : partial ? "Partial extraction" : "Extraction complete"}</span>
          <small>RISK SCORE <b>NOT AVAILABLE</b></small>
          <small>CONFIDENCE <b>NOT PROVIDED BY API</b></small>
        </div>
      </section>

      <div className="case-grid">
        <div className="case-main-column">
          <section className="panel report-panel">
            <div className="panel-heading">
              <div><span className="panel-index">01</span><h2>Extracted details</h2></div>
              <div className="report-tools">
                <button className="text-button" onClick={() => setShowEditor((value) => !value)}><RefreshCw size={14} /> {showEditor ? "Close editor" : "Edit draft"}</button>
                <button className="text-button" onClick={rerunChecks} disabled={isChecking}><RefreshCw size={13} className={isChecking ? "spin" : ""} /> {isChecking ? "Running checks…" : verification ? "Re-run checks" : "Run checks"}</button>
              </div>
            </div>
            {showEditor && (
              <>
                <div className="editor-notice"><AlertTriangle size={15} /><span>These are local draft changes only; they do not change the submitted source text. Verification reruns automatically after an edit. {localEditCount ? `${localEditCount} field(s) edited.` : "No fields edited yet."}</span><button type="button" className="text-button" onClick={() => setDraft({})}>Reset draft</button></div>
                <div className="editor-grid">
                  <FieldEditor label="Company name" value={merged.company_name || ""} onChange={(value) => setDraftValue("company_name", value || null)} />
                  <FieldEditor label="Role title" value={merged.role_title || ""} onChange={(value) => setDraftValue("role_title", value || null)} />
                  <FieldEditor label="Claimed website" value={merged.claimed_company_website || ""} onChange={(value) => setDraftValue("claimed_company_website", value || null)} />
                  <FieldEditor label="Sender email" value={merged.sender_email || ""} onChange={(value) => setDraftValue("sender_email", value || null)} />
                  <FieldEditor label="Salary / stipend" value={merged.salary_claim || ""} onChange={(value) => setDraftValue("salary_claim", value || null)} />
                  <FieldEditor label="Payment amount" value={merged.payment_amount || ""} onChange={(value) => setDraftValue("payment_amount", value || null)} />
                  <FieldEditor label="UPI IDs (comma-separated)" value={(merged.upi_ids || []).join(", ")} onChange={(value) => setDraftValue("upi_ids", value.split(",").map((item) => item.trim()).filter(Boolean))} />
                  <FieldEditor label="Sender phone" value={merged.sender_phone || ""} onChange={(value) => setDraftValue("sender_phone", value || null)} />
                </div>
              </>
            )}
            <div className="result-fields">
              <Field label="Company" value={merged.company_name} />
              <Field label="Role" value={merged.role_title} />
              <Field label="Claimed company website" value={merged.claimed_company_website} icon={Globe2} />
              <Field label="Salary / stipend" value={merged.salary_claim} />
              <Field label="Recruiter" value={merged.recruiter_name} icon={UserRound} />
              <Field label="Sender email" value={merged.sender_email} icon={Mail} />
              <Field label="Sender phone" value={merged.sender_phone} icon={Phone} />
              <Field label="Payment demanded" value={merged.payment_demand ? "Yes — explicitly detected" : "No explicit payment request extracted"} icon={Wallet} />
              <Field label="Payment amount" value={merged.payment_amount} />
              <Field label="Claimed issue date" value={merged.claimed_issue_date} icon={CalendarDays} />
              <Field label="Claimed joining date" value={merged.claimed_joining_date} icon={CalendarDays} />
              <ListField label="Domains mentioned" values={merged.domains} icon={Globe2} />
              <ListField label="Full URLs returned" values={merged.urls} icon={Link2} />
              <ListField label="UPI identifiers" values={merged.upi_ids} icon={Fingerprint} />
              <ListField label="Phone numbers" values={merged.phone_numbers} icon={Phone} />
            </div>
            <div className="field-footnote">“Not found” means the extractor did not identify the field in the submitted material. It does not mean that the information does not exist. Websites, domains, phone numbers and identities are claims until independently verified.</div>
            <div className="schema-gap-note"><Info size={14} /><span><b>Not in the current API schema:</b> internship duration and work mode. They may appear in the source text but are not currently returned as structured extraction fields.</span></div>
          </section>

          <section className="panel language-panel">
            <div className="panel-heading"><div><span className="panel-index">02</span><h2>Payment & urgency language</h2></div><span className="panel-caption">EXTRACTED PHRASES</span></div>
            <div className="phrase-grid">
              <PhraseList title="Payment-demand phrases" values={merged.payment_demand_phrases || []} tone="ember" />
              <PhraseList title="Urgency phrases" values={merged.urgency_phrases || []} tone="amber" />
            </div>
          </section>

          <section className="panel evidence-panel">
            <div className="panel-heading"><div><span className="panel-index">03</span><h2>Source excerpts</h2></div><span className="panel-caption">{excerpts.length.toString().padStart(2, "0")} EXCERPTS</span></div>
            {excerpts.length > 0 ? (
              <div className="excerpt-list">
                {excerpts.map((excerpt, index) => (
                  <article className={`excerpt-item ${expanded === index ? "expanded" : ""}`} key={`${excerpt.field_name}-${index}`}>
                    <button className="excerpt-toggle" onClick={() => setExpanded(expanded === index ? null : index)} aria-expanded={expanded === index}>
                      <span className="excerpt-id">E-{String(index + 1).padStart(2, "0")}</span>
                      <span><b>{excerpt.field_name.replaceAll("_", " ")}</b><small>{excerpt.page_number ? `PDF page ${excerpt.page_number}` : "Submitted material"}</small></span>
                      <ChevronDown size={16} />
                    </button>
                    {expanded === index && <blockquote>“{excerpt.quote}”</blockquote>}
                  </article>
                ))}
              </div>
            ) : <div className="empty-evidence"><FileText size={20} /><p>No source excerpts were returned by the extractor for this case.</p></div>}
            <p className="field-footnote">These quotes come from the submitted offer. They are source references, not independent proof of authenticity.</p>
          </section>

          <section className="panel next-steps-panel">
            <div className="panel-heading"><div><span className="panel-index">04</span><h2>Safe next steps</h2></div><span className="panel-caption">BEFORE YOU RESPOND</span></div>
            <div className="safe-step"><span>01</span><p>Find the company's official website independently. Do not rely only on links or phone numbers included in the offer.</p></div>
            <div className="safe-step"><span>02</span><p>Contact HR using an address or phone number published on that official website.</p></div>
            <div className="safe-step"><span>03</span><p>Do not pay a registration, security, training or verification fee merely to secure an interview or offer.</p></div>
            <div className="email-draft">
              <div className="email-draft-head"><span><Mail size={15} /> VERIFICATION EMAIL DRAFT</span><button className="copy-button" onClick={copyEmail}><Clipboard size={13} /> {copied ? "Copied" : "Copy draft"}</button></div>
              <pre>{verificationEmail}</pre>
            </div>
          </section>
        </div>

        <aside className="case-side-column">
          <section className="panel trace-panel">
            <div className="panel-heading"><div><span className="panel-index">05</span><h2>Check trace</h2></div></div>
            <div className="trace-summary">
              <span className="trace-summary-icon"><LockKeyhole size={15} /></span>
              <div>
                <b>{isChecking ? "Verification running" : verification ? `${verification.completed_checks} / ${verification.total_checks} checks returned results` : "Verification not completed"}</b>
                <small>{verification ? `${verification.overall_status.toUpperCase()} · ${verification.coverage_percent.toFixed(0)}% result coverage · ${verification.checks.filter((item) => item.status === "flag").length} flagged` : "Domain, TLS, sender, PDF and payment checks are being prepared."}</small>
              </div>
            </div>
            {verification?.checks.map((check) => {
              const CheckIcon = checkIcons[check.check_id];
              return (
                <div className="verification-check" key={check.check_id}>
                  <div className="verification-check-head"><CheckIcon size={14} /><span>{check.label}</span><b className={`check-status status-${check.status}`}>{statusLabel(check.status)}</b></div>
                  <p>{check.finding}</p>
                  {check.observed_value && <small className="check-observed">{check.observed_value}</small>}
                  {check.limitation && <small className="check-limitation">{check.limitation}</small>}
                  {check.source_url && <a href={check.source_url} target="_blank" rel="noreferrer" className="check-source">Open source record <ArrowUpRight size={11} /></a>}
                </div>
              );
            })}
            {isChecking && !verification && <div className="verification-loading"><RefreshCw size={14} className="spin" /> Contacting public registries and checking local evidence…</div>}
            {verificationError && <div className="verification-error"><AlertTriangle size={14} /> {verificationError}</div>}
            {verification && verification.caveats.map((caveat, index) => <p className="field-footnote" key={index}>{caveat}</p>)}
            {!verification && !isChecking && !verificationError && <p className="field-footnote">Run the checks to inspect the claims. A missing or unavailable result is never treated as a clean result.</p>}
          </section>

          <section className="panel source-panel">
            <div className="panel-heading"><div><span className="panel-index">06</span><h2>Input record</h2></div></div>
            <div className="source-detail"><span>INPUT TYPE</span><b>{extracted.input_type.toUpperCase()}</b></div>
            <div className="source-detail"><span>FILE NAME</span><b>{session.fileName || "Pasted text"}</b></div>
            <div className="source-detail"><span>EXTRACTION TIME</span><b>{(session.durationMs / 1000).toFixed(1)} SEC</b></div>
            <div className="source-detail"><span>CREATED</span><b>{new Date(session.createdAt).toLocaleString()}</b></div>
            {session.filePreviewUrl && extracted.input_type === "image" && <img className="source-preview" src={session.filePreviewUrl} alt="Uploaded offer preview" />}
            {session.filePreviewUrl && extracted.input_type === "pdf" && <iframe className="source-pdf-preview" src={session.filePreviewUrl} title="Uploaded PDF preview" />}
            {session.filePreviewUrl && <p className="field-footnote">Preview is shown without document annotations because the current API does not return page coordinates for extracted fields.</p>}
            {session.submittedText && <details className="submitted-text"><summary>View submitted text</summary><pre>{session.submittedText}</pre></details>}
          </section>

          {(extracted.extraction_warnings.length > 0 || fallback || partial) && (
            <section className="panel warning-panel">
              <div className="panel-heading"><div><span className="panel-index">!</span><h2>Limitations</h2></div></div>
              {fallback && <p><AlertTriangle size={14} /> This report uses local rule-based extraction. Fields may be missing; image-only content cannot be read in this mode unless OCR text is provided.</p>}
              {partial && <p><AlertTriangle size={14} /> The extraction was partial. Review all fields manually.</p>}
              {extracted.extraction_warnings.map((warning, index) => <p key={index}><AlertTriangle size={14} />{warning}</p>)}
            </section>
          )}
          <div className="report-actions">
            <button className="button button-primary" onClick={downloadReport} disabled={!verification || isChecking} title={!verification ? "Wait for verification to finish before exporting." : "Download the complete investigation record"}><Download size={15} /> {isChecking || !verification ? "Verification pending" : "Download investigation JSON"}</button>
            <button className="button button-outline print-button" onClick={() => window.print()}><Printer size={15} /> Print / Save PDF</button>
            <Link to="/investigate" className="button button-outline">New case</Link>
          </div>
        </aside>
      </div>
      <div className="case-disclaimer"><ShieldAlert size={16} /><span>ScamScope is an assistance tool, not a law-enforcement or financial authority. This screen shows extracted claims only; it does not determine whether an offer is genuine.</span></div>
    </main>
  );
}
