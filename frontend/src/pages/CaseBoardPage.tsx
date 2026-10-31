import { Link } from "react-router-dom";
import { ArrowUpRight, GitBranch, Network } from "lucide-react";

export function CaseBoardPage() {
  return (
    <main className="app-page board-page">
      <div className="page-heading">
        <div><p className="eyebrow">CASE BOARD / NETWORK VIEW</p><h1>Follow the<br /><em>connections.</em></h1><p className="page-intro">A future investigation board for cases that share a domain, phone number or payment identifier.</p></div>
        <span className="future-label">STRETCH FEATURE</span>
      </div>
      <section className="board-canvas panel">
        <div className="board-toolbar"><span><Network size={15} /> LINK ANALYSIS / 0 CASES</span><span>DOMAIN · PHONE · UPI</span></div>
        <svg className="board-graph" viewBox="0 0 900 430" role="img" aria-label="Illustration of an empty case connection graph, with no real case data">
          <defs><pattern id="boardDots" width="24" height="24" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1" fill="#28313a" /></pattern><radialGradient id="boardGlow"><stop stopColor="#f17d3f" stopOpacity=".22" /><stop offset="1" stopColor="#f17d3f" stopOpacity="0" /></radialGradient></defs>
          <rect width="900" height="430" fill="url(#boardDots)" /><circle cx="450" cy="215" r="210" fill="url(#boardGlow)" />
          <g stroke="#5b6670" strokeOpacity=".35" strokeDasharray="4 9" fill="none"><path d="M450 215 L245 110 L120 225" /><path d="M450 215 L670 95 L790 225" /><path d="M450 215 L300 335 L580 350" /><path d="M245 110 L670 95" /><path d="M120 225 L300 335 L580 350 L790 225" /></g>
          <g fill="#111820" stroke="#65717c" strokeWidth="1.3"><circle cx="450" cy="215" r="44" /><circle cx="245" cy="110" r="25" /><circle cx="120" cy="225" r="18" /><circle cx="670" cy="95" r="25" /><circle cx="790" cy="225" r="18" /><circle cx="300" cy="335" r="20" /><circle cx="580" cy="350" r="20" /></g>
          <circle cx="450" cy="215" r="7" fill="#f17d3f" /><g fill="#7d8993" fontSize="11" fontFamily="monospace"><text x="450" y="274" textAnchor="middle">NO ACTIVE CASES</text><text x="245" y="115" textAnchor="middle">DOMAIN</text><text x="670" y="100" textAnchor="middle">UPI</text></g>
        </svg>
        <div className="board-empty"><span className="board-empty-icon"><GitBranch size={21} /></span><p className="eyebrow">NETWORK DATA NOT AVAILABLE</p><h2>No case links to display.</h2><p>The current backend does not store investigation cases or correlate shared identifiers. No connections have been fabricated for this preview.</p><Link to="/investigate" className="text-button">Create an extraction record <ArrowUpRight size={14} /></Link></div>
        <div className="board-legend"><span><i className="legend-dot dot-muted" /> Domain match</span><span><i className="legend-dot dot-flag" /> Shared payment ID</span><span><i className="legend-dot dot-clear" /> Shared phone</span></div>
      </section>
    </main>
  );
}
