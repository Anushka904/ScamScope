import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowDown, ArrowUpRight, BadgeCheck, Braces, Building2,
  ChevronRight, CircleAlert, FileSearch, Fingerprint, Globe2, Mail,
  ShieldAlert, Sparkles, Wallet,
} from "lucide-react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import Lenis from "lenis";

const evidenceFields = [
  { icon: Building2, label: "Company identity", value: "Example Robotics", code: "FIELD / 01" },
  { icon: Mail, label: "Sender address", value: "hr@example.com", code: "FIELD / 02" },
  { icon: Globe2, label: "Claimed domain", value: "example-careers.test", code: "FIELD / 03" },
  { icon: Wallet, label: "Payment request", value: "₹2,000 registration fee", code: "FIELD / 04" },
];

const checks = [
  { title: "Domain registration", state: "Not connected", note: "Domain age lookup is part of the next verification phase.", icon: Globe2 },
  { title: "Sender consistency", state: "Not connected", note: "The sender and claimed company domain have not been compared.", icon: Mail },
  { title: "Document metadata", state: "Not connected", note: "Metadata is not exposed by the current extraction response.", icon: FileSearch },
  { title: "Payment language", state: "Extracted", note: "Payment requests can be surfaced from the submitted wording.", icon: Wallet },
  { title: "External reputation", state: "Not connected", note: "No reputation provider is called by the current backend.", icon: Fingerprint },
];

export function LandingPage() {
  const root = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState("top");
  const progressFill = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const host = root.current;
    if (!host) return;

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const mobile = window.matchMedia("(max-width: 820px)").matches;
    if (reduceMotion || mobile) {
      return;
    }

    gsap.registerPlugin(ScrollTrigger);
    const lenis = new Lenis({ duration: 1.05, smoothWheel: true });
    const raf = (time: number) => lenis.raf(time * 1000);
    lenis.on("scroll", ScrollTrigger.update);
    gsap.ticker.add(raf);
    gsap.ticker.lagSmoothing(0);

    const ctx = gsap.context(() => {
      gsap.to(".hero-orbit", {
        yPercent: 28, scale: 1.08,
        scrollTrigger: { trigger: "#top", start: "top top", end: "bottom top", scrub: true },
      });
      gsap.to(".hero-document", {
        yPercent: 32, rotate: 3,
        scrollTrigger: { trigger: "#top", start: "top top", end: "bottom top", scrub: true },
      });
      gsap.utils.toArray<HTMLElement>(".hero-stat-value").forEach((node) => {
        const target = Number(node.dataset.count || "0");
        gsap.fromTo(node, { textContent: 0 }, {
          textContent: target, duration: 1.1, snap: { textContent: 1 }, ease: "power2.out",
          scrollTrigger: { trigger: node, start: "top 92%", once: true },
        });
      });
      gsap.utils.toArray<HTMLElement>(".reveal-heading").forEach((heading) => {
        const lines = heading.querySelectorAll<HTMLElement>(".heading-line");
        gsap.fromTo(lines, { y: 24, opacity: 0.25, clipPath: "inset(0 0 45% 0)" }, {
          y: 0, opacity: 1, clipPath: "inset(0 0 0% 0)", stagger: 0.1, ease: "none",
          scrollTrigger: { trigger: heading, start: "top 88%", end: "top 54%", scrub: 0.6 },
        });
      });

      const extractTl = gsap.timeline({
        scrollTrigger: {
          trigger: "#extract",
          start: "top top",
          end: "+=1180",
          scrub: 1,
          pin: ".extract-visual",
          anticipatePin: 1,
        },
      });
      extractTl.fromTo(".scanner-beam", { y: -16, opacity: 0.35 }, { y: 380, opacity: 1, duration: 1.2, ease: "none" }, 0);
      extractTl.fromTo(".extract-tag", { opacity: 0, x: 18 }, { opacity: 1, x: 0, stagger: 0.18, duration: 0.22 }, 0.15);
      extractTl.to(".extract-doc", { boxShadow: "0 0 90px rgba(255,111,44,.20)", duration: 0.35 }, 0.5);

      const investigateTl = gsap.timeline({
        scrollTrigger: {
          trigger: "#investigate",
          start: "top top",
          end: "+=1500",
          scrub: 1,
          pin: ".investigate-visual",
          anticipatePin: 1,
        },
      });
      checks.forEach((_, index) => {
        investigateTl.fromTo(`.check-step-${index}`, { opacity: 0.22, x: 18 }, { opacity: 1, x: 0, duration: 0.2 }, index * 0.19);
        investigateTl.to(".investigate-light", { opacity: 0.12 + index * 0.11, duration: 0.2 }, index * 0.19);
      });
      investigateTl.to(".investigate-light", {
        background: "radial-gradient(ellipse at 55% 48%, rgba(231,173,85,.38), transparent 60%)",
        duration: 0.4,
      }, 0.42);
      investigateTl.to(".investigate-light", {
        background: "radial-gradient(ellipse at 55% 48%, rgba(207,77,54,.42), transparent 60%)",
        duration: 0.4,
      }, 0.76);

      gsap.fromTo(".proof-card", { y: 70, opacity: 0 }, {
        y: 0, opacity: 1, stagger: 0.14, ease: "power2.out",
        scrollTrigger: { trigger: "#prove", start: "top 68%", end: "center center", scrub: 0.8 },
      });
      gsap.fromTo(".verdict-word", { clipPath: "inset(100% 0 0 0)", y: 30 }, {
        clipPath: "inset(0% 0 0 0)", y: 0, ease: "none",
        scrollTrigger: { trigger: "#verdict", start: "top 72%", end: "center center", scrub: 0.8 },
      });

      const sections = ["top", "extract", "investigate", "prove", "verdict"];
      sections.forEach((id) => {
        ScrollTrigger.create({
          trigger: `#${id}`,
          start: "top 55%",
          end: "bottom 45%",
          onToggle: (self) => { if (self.isActive) setActive(id); },
        });
      });
      ScrollTrigger.create({
        trigger: document.documentElement,
        start: "top top",
        end: "bottom bottom",
        onUpdate: (self) => {
          if (progressFill.current) progressFill.current.style.height = `${self.progress * 100}%`;
        },
      });
      ScrollTrigger.refresh();
    }, host);

    return () => {
      ctx.revert();
      gsap.ticker.remove(raf);
      lenis.destroy();
      ScrollTrigger.getAll().forEach((trigger) => trigger.kill());
    };
  }, []);

  const jump = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  };

  return (
    <main ref={root} className="landing">
      <div className="scroll-rail" aria-label="Page progress">
        <div className="scroll-rail-line"><span ref={progressFill} /></div>
        {["top", "extract", "investigate", "prove", "verdict"].map((id, index) => (
          <button key={id} className={active === id ? "rail-dot active" : "rail-dot"} onClick={() => jump(id)} aria-label={`Go to ${["Introduction", "Extract", "Investigate", "Evidence", "Verdict"][index]}`} />
        ))}
      </div>

      <section id="top" className="hero-section">
        <div className="hero-grain" />
        <div className="hero-copy">
          <p className="eyebrow"><span className="eyebrow-dot" /> THE EVIDENCE LAB <span className="eyebrow-rule" /> FIELD NOTE 001</p>
          <h1 className="reveal-heading"><span className="heading-line">Is that offer real?</span><span className="heading-line"><em>Let's look at the evidence.</em></span></h1>
          <p className="hero-description">A job offer can look convincing. We examine what it says, extract the details, and make the evidence easier to verify—before you send a rupee or share another document.</p>
          <div className="hero-actions">
            <Link to="/investigate" className="button button-primary">Examine an offer <ArrowUpRight size={16} /></Link>
            <button className="text-button" onClick={() => jump("extract")}>See how it works <ArrowDown size={15} /></button>
          </div>
          <div className="hero-footnote"><span className="tiny-led" /> Built to question claims, not make assumptions.</div>
          <div className="hero-stats">
            <div><b className="hero-stat-value" data-count="3">0</b><span>SUPPORTED INPUT TYPES</span></div>
            <div><b className="hero-stat-value" data-count="1">0</b><span>STRUCTURED EXTRACTION API</span></div>
          </div>
        </div>
        <div className="hero-art" aria-label="Illustration of an offer letter under forensic examination">
          <div className="hero-orbit orbit-one" /><div className="hero-orbit orbit-two" />
          <div className="hero-glow" />
          <div className="hero-coordinate coord-one">SCAN FIELD / LOCAL PREVIEW</div>
          <div className="hero-coordinate coord-two">TRACE ACTIVE · 01:04</div>
          <article className="hero-document">
            <div className="doc-topline"><span>DOCUMENT / UNVERIFIED</span><span>SS—001</span></div>
            <div className="doc-company-mark"><span className="doc-monogram">ER</span><span>EXAMPLE ROBOTICS<small>PEOPLE & CULTURE</small></span></div>
            <p className="doc-date">OFFER LETTER · 14 OCT 2026</p>
            <h3>Internship<br />Appointment</h3>
            <div className="doc-lines"><i /><i /><i /><i /><i /></div>
            <div className="doc-highlight"><span>REGISTRATION FEE</span><b>₹ 2,000.00</b><small>Required to confirm selection</small></div>
            <div className="doc-sign"><span>Human Resources</span><span className="doc-stamp">PENDING<br />VERIFY</span></div>
            <div className="doc-bottom"><span>EXHIBIT A · SYNTHETIC SAMPLE</span><span>01 / 01</span></div>
            <div className="doc-scanline" />
          </article>
          <div className="hero-callout callout-a"><span className="callout-icon"><CircleAlert size={13} /></span><span>Payment request detected</span><b>E—04</b></div>
          <div className="hero-callout callout-b"><span className="callout-icon teal"><BadgeCheck size={13} /></span><span>Sender field extracted</span><b>E—02</b></div>
          <div className="hero-art-caption">VISUAL SAMPLE · NOT A REAL CASE</div>
        </div>
        <div className="hero-bottom"><span>01 / THE QUESTION</span><span>SCROLL TO INVESTIGATE <ArrowDown size={13} /></span><span>SCAMSCOPE / 2026</span></div>
      </section>

      <section id="extract" className="story-section extract-section">
        <div className="story-copy">
          <p className="eyebrow">01 — EXTRACT</p>
          <h2 className="reveal-heading"><span className="heading-line">First, separate</span><span className="heading-line"><em>the signal from the noise.</em></span></h2>
          <p>Offers hide important details inside polished layouts, hurried messages and attachments. ScamScope turns those fragments into structured fields you can inspect.</p>
          <ul className="micro-list">
            <li><span>01</span> Company and role claims</li>
            <li><span>02</span> Sender, domain and contact details</li>
            <li><span>03</span> Fees, payment identifiers and urgency</li>
          </ul>
          <p className="micro-note">Extraction identifies what is written. It does not prove that a claim is true.</p>
        </div>
        <div className="extract-visual">
          <div className="visual-corner corner-tl" /><div className="visual-corner corner-br" />
          <div className="visual-label"><span>EXTRACTION VIEW</span><span>INPUT → STRUCTURE</span></div>
          <div className="extract-doc">
            <div className="extract-doc-head"><span>EXAMPLE ROBOTICS</span><span>OFFER / 01</span></div>
            <h3>Software Developer<br />Internship</h3>
            <div className="extract-lines"><i /><i /><i /><i /></div>
            <div className="extract-data"><b>HR CONTACT</b><span>hr@example.com</span></div>
            <div className="extract-data"><b>JOINING</b><span>02 NOV 2026</span></div>
            <div className="extract-data danger"><b>FEE REQUEST</b><span>₹ 2,000</span></div>
            <div className="scanner-beam" />
          </div>
          <div className="extract-tag tag-company"><span className="tag-num">01</span> COMPANY</div>
          <div className="extract-tag tag-email"><span className="tag-num">02</span> SENDER EMAIL</div>
          <div className="extract-tag tag-fee"><span className="tag-num">03</span> PAYMENT ASK</div>
          <div className="visual-bottom"><span>RULE-BASED TEXT EXTRACTION</span><span><span className="tiny-led" /> SOURCE-MATCHED / STRUCTURED</span></div>
        </div>
      </section>

      <section id="investigate" className="story-section investigate-section">
        <div className="story-copy">
          <p className="eyebrow">02 — INVESTIGATE</p>
          <h2 className="reveal-heading"><span className="heading-line">A claim is not proof.</span><span className="heading-line"><em>Every check needs a source.</em></span></h2>
          <p>Once details are extracted, they can be compared with independent records. A missing check is not a clean result—and an unavailable source is not a pass.</p>
          <div className="legend">
            <span><i className="legend-dot dot-flag" /> Flagged</span>
            <span><i className="legend-dot dot-clear" /> Passed</span>
            <span><i className="legend-dot dot-muted" /> Not connected</span>
          </div>
          <p className="micro-note">The current backend performs extraction only. The checks shown here are a product roadmap, not live findings.</p>
        </div>
        <div className="investigate-visual">
          <div className="investigate-light" />
          <div className="visual-label"><span>INVESTIGATION TRACE</span><span>CHECKLIST / ROADMAP</span></div>
          <div className="trace-case"><span className="trace-pulse" /> CASE PREVIEW <b>UNVERIFIED</b></div>
          <div className="trace-list">
            {checks.map((check, index) => {
              const Icon = check.icon;
              return (
                <div key={check.title} className={`trace-step check-step-${index}`}>
                  <span className="trace-index">0{index + 1}</span>
                  <span className="trace-icon"><Icon size={15} /></span>
                  <span className="trace-text"><b>{check.title}</b><small>{check.note}</small></span>
                  <span className={`trace-state ${check.state === "Extracted" ? "state-extracted" : ""}`}>{check.state}</span>
                </div>
              );
            })}
          </div>
          <div className="visual-bottom"><span>NO CHECK = NO ASSUMPTION</span><span>TRACE / 05 STEPS</span></div>
        </div>
      </section>

      <section id="prove" className="proof-section">
        <div className="proof-heading">
          <p className="eyebrow">03 — PROVE</p>
          <h2 className="reveal-heading"><span className="heading-line">Make every finding</span><span className="heading-line"><em>traceable to its source.</em></span></h2>
          <p>Evidence should be inspectable, not just persuasive. Each extracted statement stays connected to the words that produced it.</p>
        </div>
        <div className="proof-grid">
          {evidenceFields.map((field) => {
            const Icon = field.icon;
            return (
              <article className="proof-card" key={field.label}>
                <div className="proof-card-head"><span>{field.code}</span><span className="proof-icon"><Icon size={17} /></span></div>
                <p>{field.label}</p>
                <h3>{field.value}</h3>
                <div className="proof-source"><span className="source-line" /> <span>EXTRACTED FIELD</span><ChevronRight size={14} /></div>
              </article>
            );
          })}
        </div>
        <p className="proof-disclaimer"><ShieldAlert size={15} /> Illustrative sample values only. A quoted claim is not independent verification.</p>
      </section>

      <section id="verdict" className="verdict-section">
        <div className="verdict-grid">
          <div>
            <p className="eyebrow">04 — THE STANDARD</p>
            <h2 className="reveal-heading"><span className="heading-line">Don't trust the polish.</span><span className="heading-line"><em>Inspect the proof.</em></span></h2>
            <p className="verdict-description">ScamScope helps you slow down, see what an offer is asking for, and identify what still needs independent verification.</p>
            <Link to="/investigate" className="button button-primary">Open the evidence lab <ArrowUpRight size={16} /></Link>
          </div>
          <div className="verdict-visual">
            <div className="verdict-orb" />
            <p className="verdict-kicker">CURRENT CASE STATE</p>
            <div className="verdict-word">UNVERIFIED</div>
            <p className="verdict-caveat">No risk score is generated yet.<br />A missing verdict is not a safety guarantee.</p>
            <div className="verdict-bar"><span>EXTRACTION</span><b>AVAILABLE</b><span>RISK SCORING</span><b className="pending">NEXT PHASE</b></div>
          </div>
        </div>
        <div className="verdict-bottom"><span>SCAMSCOPE / THE EVIDENCE LAB</span><span>QUESTION EVERYTHING THAT ASKS FOR PAYMENT.</span></div>
      </section>

      <section id="method" className="method-strip">
        <div><span className="method-number">01</span><Braces size={19} /><b>Extract</b><small>Turn the offer into structured claims.</small></div>
        <div><span className="method-number">02</span><Fingerprint size={19} /><b>Verify</b><small>Compare claims with independent sources.</small></div>
        <div><span className="method-number">03</span><Sparkles size={19} /><b>Explain</b><small>Show the evidence behind the assessment.</small></div>
      </section>
    </main>
  );
}
