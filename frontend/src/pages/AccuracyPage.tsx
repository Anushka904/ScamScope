import { useEffect, useState } from "react";
import { Activity, AlertTriangle, Braces, Database, FileCheck2, Gauge, Info, ShieldCheck } from "lucide-react";

interface AccuracyMetrics {
  status: "not_published" | "published";
  precision: number | null;
  recall: number | null;
  sample_count: number | null;
  evaluated_at: string | null;
  dataset: string | null;
  note: string;
}

const emptyMetrics: AccuracyMetrics = {
  status: "not_published",
  precision: null,
  recall: null,
  sample_count: null,
  evaluated_at: null,
  dataset: null,
  note: "No validated evaluation metrics have been published yet. Do not interpret missing metrics as 100% accuracy.",
};

function Metric({ label, value, hint }: { label: string; value: number | null; hint: string }) {
  return <div className="metric-card"><span>{label}</span><strong>{value === null ? "—" : `${(value * 100).toFixed(1)}%`}</strong><small>{value === null ? "Not published" : hint}</small></div>;
}

export function AccuracyPage() {
  const [metrics, setMetrics] = useState<AccuracyMetrics>(emptyMetrics);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    fetch("/data/accuracy.json")
      .then((response) => {
        if (!response.ok) throw new Error("Unable to load evaluation file");
        return response.json() as Promise<AccuracyMetrics>;
      })
      .then((data) => setMetrics(data))
      .catch(() => setMetrics(emptyMetrics))
      .finally(() => setLoaded(true));
  }, []);

  return (
    <main className="app-page accuracy-page">
      <div className="page-heading">
        <div><p className="eyebrow">METHOD / TRANSPARENCY</p><h1>Show the method.<br /><em>Show the limits.</em></h1><p className="page-intro">A useful investigator should make it clear what it checked, what it could not check, and how its performance was measured.</p></div>
        <div className="accuracy-stamp"><ShieldCheck size={21} /><span>TRANSPARENCY<br />PROTOCOL / 01</span></div>
      </div>

      <section className="panel metrics-panel">
        <div className="panel-heading"><div><span className="panel-index">01</span><h2>Evaluation metrics</h2></div><span className="panel-caption">SOURCE / PUBLIC DATA JSON</span></div>
        <div className="metrics-grid">
          <Metric label="PRECISION" value={metrics.precision} hint="Of flagged cases, proportion that were correct." />
          <Metric label="RECALL" value={metrics.recall} hint="Of positive cases, proportion correctly identified." />
          <div className="metric-card"><span>EVALUATION SET</span><strong>{metrics.sample_count ?? "—"}</strong><small>{metrics.dataset || "No published dataset"}</small></div>
        </div>
        <div className={`metrics-note ${metrics.status === "published" ? "metrics-published" : ""}`}><Info size={16} /><p>{loaded ? metrics.note : "Loading accuracy record…"}</p></div>
        {metrics.evaluated_at && <p className="field-footnote">Last evaluated: {metrics.evaluated_at}</p>}
      </section>

      <section className="method-cards">
        <article className="panel method-card"><span className="method-card-icon"><Braces size={19} /></span><p className="eyebrow">LAYER 01</p><h2>Rule-based extraction</h2><p>The default engine runs locally without an API key or model quota. It extracts explicit claims from selectable text, including company and role labels, contact details, payment language and source excerpts.</p><ul><li>No Gemini quota or billing required</li><li>Unknown fields remain unknown</li><li>Evidence excerpts are tied to source text</li><li>Image-only OCR is not included in this mode</li></ul></article>
        <article className="panel method-card"><span className="method-card-icon"><Database size={19} /></span><p className="eyebrow">LAYER 02</p><h2>Independent checks</h2><p>The next verification phase will gather observable evidence from domain registration, DNS, TLS, document metadata and reputation providers.</p><ul><li>Each check should retain source and timestamp</li><li>Unavailable is different from clear</li><li>Provider errors are disclosed</li></ul><span className="future-label">PLANNED / NOT CONNECTED</span></article>
        <article className="panel method-card"><span className="method-card-icon"><Gauge size={19} /></span><p className="eyebrow">LAYER 03</p><h2>Evidence-based scoring</h2><p>A separate investigation engine will combine verified evidence into an indicator score, coverage and caveats—not a probability that someone is a scammer.</p><ul><li>Explainable indicator weights</li><li>Coverage-aware caveats</li><li>No flat “safe” verdict</li></ul><span className="future-label">PLANNED / NOT CONNECTED</span></article>
      </section>

      <section className="panel limits-panel">
        <div className="panel-heading"><div><span className="panel-index">02</span><h2>What this system does not claim</h2></div><span className="panel-caption">IMPORTANT LIMITS</span></div>
        <div className="limits-grid"><p><AlertTriangle size={15} /> It does not certify that a company or offer is genuine.</p><p><FileCheck2 size={15} /> It does not treat missing information as proof of safety.</p><p><Activity size={15} /> It does not yet calculate a validated risk score.</p></div>
      </section>
    </main>
  );
}
