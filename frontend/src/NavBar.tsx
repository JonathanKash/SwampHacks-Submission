import { useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { BriefcaseIcon, InfoIcon, NetworkIcon, PencilIcon, TextLinesIcon } from "./icons";

const NAV_ITEMS = [
  { to: "/", label: "About", icon: InfoIcon, end: true },
  { to: "/edit", label: "Make an edit", icon: PencilIcon, end: false },
  { to: "/tree", label: "Live tree", icon: NetworkIcon, end: false },
  { to: "/audit", label: "Audit", icon: BriefcaseIcon, end: false },
  { to: "/text", label: "Text", icon: TextLinesIcon, end: false },
] as const;

/** Shared top navigation so every page explains where you are and where to go next. */
export default function NavBar({ compact = false }: { compact?: boolean }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();

  useEffect(() => setMenuOpen(false), [location.pathname]);

  return (
    <nav className={`nav-bar ${compact ? "is-compact" : ""}`} aria-label="Main">
      <div className="nav-row">
        <NavLink to="/" className="nav-brand" end>
          <span className="brand-mark" aria-hidden="true">L</span>
          {!compact && <span className="nav-title">Lineage</span>}
        </NavLink>
        <button
          className="secondary-button nav-menu-button"
          type="button"
          aria-pressed={menuOpen}
          aria-expanded={menuOpen}
          aria-controls="main-navigation"
          onClick={() => setMenuOpen((open) => !open)}
        >
          Menu
        </button>
      </div>
      <div className={`nav-links ${menuOpen ? "is-open" : ""}`} id="main-navigation">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              to={item.to}
              end={item.end}
              className={({ isActive }) => (isActive ? "is-active" : "")}
              key={item.to}
            >
              <Icon />
              <span>{item.label}</span>
            </NavLink>
          );
        })}
      </div>
    </nav>
  );
}
