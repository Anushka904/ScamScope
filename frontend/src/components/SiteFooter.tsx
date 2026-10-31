import { Link } from "react-router-dom";
import { ScanLine } from "lucide-react";

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="brand footer-brand"><span className="brand-mark"><ScanLine size={16} /></span><span>SCAM<span className="brand-light">SCOPE</span></span></div>
      <p>Evidence before assumptions. Verification before payment.</p>
      <div className="footer-links"><Link to="/accuracy">Method & accuracy</Link><Link to="/cases">Case board</Link><span>© {new Date().getFullYear()} ScamScope</span></div>
    </footer>
  );
}
