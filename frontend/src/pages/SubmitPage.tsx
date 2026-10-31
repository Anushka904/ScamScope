import { useEffect, useMemo, useRef, useState, type DragEvent } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertCircle, ArrowRight, Check, Clock3, FileImage, FileText, FileUp,
  LoaderCircle, LockKeyhole, RefreshCw, ShieldCheck, UploadCloud, X, Zap,
} from "lucide-react";
import { checkApiHealth, extractOffer, ApiError, REQUEST_TIMEOUT_MS } from "../lib-api";

const MAX_FILE_SIZE = 10 * 1024 * 1024;
const ACCEPTED_EXTENSIONS = [".png", ".jpg", ".jpeg", ".webp", ".pdf"];

const samples = [
  {
    label: "The fee-first offer",
    tag: "PAYMENT REQUEST",
    tone: "danger",
    text: "Hello Candidate, congratulations! You have been selected for the Software Developer Intern role at BrightPath Labs. Your stipend will be ₹25,000 per month. To confirm your seat, pay a refundable registration and verification fee of ₹1,499 today to brightpath.hr@okaxis. Reply immediately because only three seats are left. Contact: hiring@brightpath-careers.example",
  },
  {
    label: "The clean-looking offer",
    tag: "FEW DETAILS",
    tone: "neutral",
    text: "Dear Candidate, Northstar Research is pleased to invite you to interview for the Data Research Intern position. The interview will take place online next week. No payment is required at any stage of recruitment. Please reply to talent@northstar-research.example to confirm your availability. This is an anonymized training example.",
  },
  {
    label: "The urgent selection",
    tag: "URGENCY",
    tone: "warning",
    text: "FINAL NOTICE: Your profile is shortlisted for Asterbyte Solutions - AI Intern. Monthly stipend ₹18,000. Complete your onboarding by 6 PM today. A refundable document-verification deposit of ₹2,000 is required before we release the offer letter. UPI: asterbyte@okaxis. HR: careers@asterbyte-jobs.example",
  },
];

function formatBytes(bytes: number) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getExtension(name: string) {
  const dot = name.lastIndexOf(".");
  return dot >= 0 ? name.slice(dot).toLowerCase() : "";
}

function formatElapsed(seconds: number) {
  const minutes = Math.floor(seconds / 60).toString().padStart(2, "0");
  const remainder = (seconds % 60).toString().padStart(2, "0");
  return `${minutes}:${remainder}`;
}

export function SubmitPage() {
  const navigate = useNavigate();
  const fileInput = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const [mode, setMode] = useState<"upload" | "paste">("upload");
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);
  const [checkingApi, setCheckingApi] = useState(false);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [statusNote, setStatusNote] = useState("");

  const refreshApiHealth = async () => {
    setCheckingApi(true);
    const controller = new AbortController();
    const online = await checkApiHealth(controller.signal);
    setApiOnline(online);
    setCheckingApi(false);
  };

  useEffect(() => {
    const controller = new AbortController();
    checkApiHealth(controller.signal).then(setApiOnline);
    return () => {
      controller.abort();
      abortRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    if (!file) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  useEffect(() => {
    if (!isSubmitting || startedAt === null) return;
    const timer = window.setInterval(() => setElapsedSeconds(Math.floor((Date.now() - startedAt) / 1000)), 1000);
    return () => window.clearInterval(timer);
  }, [isSubmitting, startedAt]);

  const isReady = useMemo(
    () => mode === "upload" ? Boolean(file) && !error : text.trim().length >= 20 && !error,
    [mode, file, text, error],
  );
  const selectedExtension = file ? getExtension(file.name) : "";
  const selectedIsImage = [".png", ".jpg", ".jpeg", ".webp"].includes(selectedExtension);
  const selectedIsPdf = selectedExtension === ".pdf";

  const validateFile = (candidate: File | null) => {
    setError("");
    setStatusNote("");
    if (!candidate) return;
    const extension = getExtension(candidate.name);
    if (!ACCEPTED_EXTENSIONS.includes(extension)) {
      setFile(null);
      if (fileInput.current) fileInput.current.value = "";
      setError("Unsupported file type. Choose a PNG, JPG, WEBP or PDF file.");
      return;
    }
    if (candidate.size > MAX_FILE_SIZE) {
      setFile(null);
      if (fileInput.current) fileInput.current.value = "";
      setError("This file exceeds the 10 MB frontend limit. Choose a smaller document.");
      return;
    }
    if (candidate.size === 0) {
      setFile(null);
      if (fileInput.current) fileInput.current.value = "";
      setError("This file is empty. Choose another document.");
      return;
    }
    setFile(candidate);
  };

  const loadSample = (sampleText: string) => {
    setMode("paste");
    setText(sampleText);
    setFile(null);
    setError("");
    setStatusNote("Synthetic sample loaded. Review it, then start extraction.");
  };

  const cancelWait = () => {
    abortRef.current?.abort();
  };

  const submit = async () => {
    setError("");
    setStatusNote("");
    if (!isReady) {
      setError(mode === "upload" ? "Choose a supported file before starting." : "Paste at least 20 characters of offer text.");
      return;
    }

    const begin = Date.now();
    const controller = new AbortController();
    abortRef.current = controller;
    setStartedAt(begin);
    setElapsedSeconds(0);
    setIsSubmitting(true);

    try {
      const extraction = await extractOffer(mode === "upload" ? { file } : { text }, controller.signal);
      const reportPreviewUrl = mode === "upload" && file ? URL.createObjectURL(file) : null;
      navigate("/case", {
        state: {
          extraction,
          submittedText: mode === "paste" ? text : "",
          fileName: mode === "upload" ? file?.name ?? null : null,
          filePreviewUrl: reportPreviewUrl,
          createdAt: new Date().toISOString(),
          durationMs: Date.now() - begin,
        },
      });
    } catch (cause) {
      const apiError = cause instanceof ApiError ? cause : null;
      const message = apiError?.message || (cause instanceof Error ? cause.message : "Something went wrong.");
      setError(message);
      if (apiError?.code === "offline") setApiOnline(false);
      if (apiError?.code === "timeout" || apiError?.code === "cancelled") {
        setStatusNote("Important: stopping the browser wait does not guarantee that server-side extraction was cancelled. Check the backend terminal before retrying.");
      }
    } finally {
      setIsSubmitting(false);
      setStartedAt(null);
      abortRef.current = null;
    }
  };

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    if (event.dataTransfer.files.length > 1) {
      setError("Only one file can be examined at a time. Choose a single document.");
      return;
    }
    validateFile(event.dataTransfer.files.item(0));
  };

  return (
    <main className="app-page submit-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">NEW INVESTIGATION / INTAKE</p>
          <h1>Put the offer<br /><em>on the examination table.</em></h1>
          <p className="page-intro">Upload the document or paste the message. ScamScope extracts the claims and source excerpts that deserve a closer look.</p>
        </div>
        <div className={`api-status-wrap ${apiOnline ? "online" : apiOnline === false ? "offline" : ""}`}>
          <div className={`api-indicator ${apiOnline ? "online" : apiOnline === false ? "offline" : ""}`}>
            <span className="status-dot" /> {apiOnline === null ? "Checking API" : apiOnline ? "Backend connected" : "Backend offline"}
          </div>
          <button className="text-button api-retry" type="button" onClick={refreshApiHealth} disabled={checkingApi || isSubmitting}>
            <RefreshCw size={12} className={checkingApi ? "spin" : ""} /> {checkingApi ? "Checking…" : "Check connection"}
          </button>
        </div>
      </div>

      {isSubmitting && (
        <section className="live-investigation panel" aria-live="polite" aria-busy="true">
          <div className="live-document" aria-hidden="true">
            <div className="live-doc-top"><span>SCAMSCOPE / ACTIVE TRACE</span><span>INPUT 01</span></div>
            <div className="live-doc-lines"><i /><i /><i /><i /><i /></div>
            <div className="live-scan-beam" />
            <div className="live-doc-status"><span className="pulse-dot" /> SOURCE RECEIVED</div>
          </div>
          <div className="live-trace-copy">
            <p className="eyebrow">LIVE INVESTIGATION / EXTRACTION ONLY</p>
            <h2>Waiting for the<br /><em>structured response.</em></h2>
            <p>The request is being processed by your local ScamScope API. Multi-page documents and provider retries can take time. The browser wait window is configurable.</p>
            <div className="request-clock"><Clock3 size={15} /> ELAPSED <b>{formatElapsed(elapsedSeconds)}</b><span>WAIT LIMIT {Math.round(REQUEST_TIMEOUT_MS / 60_000)} MIN</span></div>
            <div className="live-progress-list">
              <div className="live-progress-row done"><span><Check size={13} /></span><b>Input submitted</b><small>Request sent</small></div>
              <div className="live-progress-row current"><span><LoaderCircle size={13} /></span><b>Structured extraction</b><small>Waiting for API response</small></div>
              <div className="live-progress-row"><span>03</span><b>Independent verification</b><small>Runs on the case report after extraction</small></div>
            </div>
            <div className="live-no-fake"><LockKeyhole size={14} /> External verification results are shown only after the backend returns them.</div>
            <button type="button" className="button button-outline cancel-wait" onClick={cancelWait}>Stop waiting</button>
          </div>
        </section>
      )}

      <div className="submit-layout">
        <section className="intake-panel panel">
          <div className="panel-heading"><div><span className="panel-index">01</span><h2>Submit material</h2></div><span className="panel-caption">ONE INPUT PER CASE</span></div>
          <div className="input-tabs" role="tablist" aria-label="Input method">
            <button type="button" className={mode === "upload" ? "input-tab selected" : "input-tab"} onClick={() => { setMode("upload"); setError(""); }} role="tab" aria-selected={mode === "upload"} disabled={isSubmitting}><FileUp size={16} /> Upload file</button>
            <button type="button" className={mode === "paste" ? "input-tab selected" : "input-tab"} onClick={() => { setMode("paste"); setError(""); }} role="tab" aria-selected={mode === "paste"} disabled={isSubmitting}><FileText size={16} /> Paste text</button>
          </div>

          {mode === "upload" ? (
            <div className={`drop-zone ${dragging ? "dragging" : ""} ${file ? "has-file" : ""}`} onDragOver={(event) => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={onDrop}>
              <input ref={fileInput} type="file" accept=".png,.jpg,.jpeg,.webp,.pdf,application/pdf,image/png,image/jpeg,image/webp" className="visually-hidden" onChange={(event) => validateFile(event.target.files?.[0] ?? null)} aria-label="Choose an offer file" disabled={isSubmitting} />
              {file ? (
                <>
                  <div className="file-selected">
                    {selectedIsImage && previewUrl
                      ? <img className="selected-image-preview" src={previewUrl} alt="Preview of selected offer screenshot" />
                      : <span className="file-icon">{selectedIsPdf ? <FileText size={24} /> : <FileImage size={24} />}</span>}
                    <div><b>{file.name}</b><small>{formatBytes(file.size)} · {file.type || selectedExtension}</small></div>
                    <button className="icon-button" type="button" onClick={() => { setFile(null); if (fileInput.current) fileInput.current.value = ""; }} aria-label="Remove selected file" disabled={isSubmitting}><X size={16} /></button>
                  </div>
                  {selectedIsPdf && previewUrl && <iframe className="selected-pdf-preview" src={previewUrl} title="Preview of selected PDF offer" />}
                </>
              ) : (
                <>
                  <div className="upload-emblem"><UploadCloud size={25} /></div>
                  <h3>Drop the document here</h3>
                  <p>or <button className="inline-link" type="button" onClick={() => fileInput.current?.click()} disabled={isSubmitting}>browse files</button> from your device</p>
                  <div className="file-specs"><span>PNG / JPG / WEBP</span><span>PDF / 5 PAGES MAX</span><span>UP TO 10 MB</span></div>
                </>
              )}
            </div>
          ) : (
            <div className="paste-zone">
              <div className="paste-label"><label htmlFor="offer-text">OFFER MESSAGE / EMAIL BODY</label><span>{text.length.toLocaleString()} characters</span></div>
              <textarea id="offer-text" value={text} disabled={isSubmitting} onChange={(event) => { setText(event.target.value); setError(""); setStatusNote(""); }} placeholder={"Paste the complete job or internship offer here…\n\nInclude sender email, company claims, payment instructions and links if visible."} rows={13} />
              <p className="input-hint">More context helps extraction. Remove passwords, OTPs and unrelated personal data before submitting.</p>
            </div>
          )}

          {error && <div className="inline-error" role="alert"><AlertCircle size={16} />{error}</div>}
          {statusNote && <div className="inline-note" role="status"><AlertCircle size={15} />{statusNote}</div>}
          <div className="privacy-note"><LockKeyhole size={15} /><span><b>Privacy by design.</b> Your file is sent to your local ScamScope backend. By default, extraction uses local text patterns and does not call an external AI provider. If you explicitly enable Gemini in backend settings, the backend may forward submitted content to Google. This frontend does not save cases to a database or browser storage. Exported JSON files are your responsibility to store securely.</span></div>
          <button className="button button-primary submit-button" onClick={submit} disabled={!isReady || isSubmitting}>
            {isSubmitting ? <><LoaderCircle className="spin" size={17} /> Waiting for extraction…</> : <>Start extraction <ArrowRight size={17} /></>}
          </button>
          {isSubmitting && <div className="request-live" aria-live="polite"><span className="pulse-dot" /> Keep this tab open until the backend responds, or stop waiting above.</div>}
        </section>

        <aside className="sample-panel">
          <div className="panel-heading"><div><span className="panel-index">02</span><h2>Try a sample</h2></div><span className="panel-caption">ANONYMIZED EXAMPLES</span></div>
          <p className="sample-intro">Explore the flow with fictional offer text. These are test inputs—not real companies or real cases.</p>
          <div className="sample-list">
            {samples.map((sample, index) => (
              <button key={sample.label} type="button" className="sample-card" onClick={() => loadSample(sample.text)} disabled={isSubmitting}>
                <div className="sample-card-top"><span className={`sample-tag ${sample.tone}`}>{sample.tag}</span><span>0{index + 1}</span></div>
                <b>{sample.label}</b>
                <p>{sample.text.slice(0, 112)}…</p>
                <span className="sample-use">Load example <ArrowRight size={13} /></span>
              </button>
            ))}
          </div>
          <div className="sample-footnote"><ShieldCheck size={16} /><span>Samples are synthetic and do not represent real investigation results.</span></div>
        </aside>
      </div>
      <div className="intake-bottom"><span>INPUT PIPELINE / PHASE 02</span><span><Zap size={13} /> EXTRACTION / PHASE 03</span><span>RISK SCORING / NOT CONNECTED YET</span></div>
    </main>
  );
}
