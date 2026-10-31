import { useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { ArrowUpRight, Menu, ScanLine, X } from "lucide-react";

export function SiteHeader({ compact = false }: { compact?: boolean }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const closeMenu = () => setMenuOpen(false);

  return (
    <header className="site-header">
      <Link to="/" className="brand" aria-label="ScamScope home" onClick={closeMenu}>
        <span className="brand-mark"><ScanLine size={17} strokeWidth={1.8} /></span>
        <span>SCAM<span className="brand-light">SCOPE</span></span>
      </Link>
      <nav id="primary-navigation" className={`header-nav ${menuOpen ? "menu-open" : ""}`} aria-label="Main navigation">
        {!compact && <a href="/#method" onClick={closeMenu}>Method</a>}
        <NavLink to="/accuracy" onClick={closeMenu} className={({ isActive }) => isActive ? "active" : ""}>Accuracy</NavLink>
        <NavLink to="/cases" onClick={closeMenu} className={({ isActive }) => isActive ? "active" : ""}>Case board</NavLink>
      </nav>
      <Link to="/investigate" className="header-cta" onClick={closeMenu}>
        Examine an offer <ArrowUpRight size={15} />
      </Link>
      <button
        type="button"
        className="mobile-nav-toggle"
        aria-label={menuOpen ? "Close navigation" : "Open navigation"}
        aria-expanded={menuOpen}
        aria-controls="primary-navigation"
        onClick={() => setMenuOpen((open) => !open)}
      >
        {menuOpen ? <X size={18} /> : <Menu size={18} />}
      </button>
    </header>
  );
}
