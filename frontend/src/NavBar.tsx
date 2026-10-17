import { useEffect, useRef, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import {
  BriefcaseIcon,
  CompareIcon,
  IdentifyIcon,
  InfoIcon,
  NetworkIcon,
  PencilIcon,
  TextLinesIcon,
} from "./icons";

const NAV_ITEMS = [
  { to: "/", label: "About", icon: InfoIcon, end: true },
  { to: "/edit", label: "Make an edit", icon: PencilIcon, end: false },
  { to: "/identify", label: "Identify", icon: IdentifyIcon, end: false },
  { to: "/compare", label: "Compare", icon: CompareIcon, end: false },
  { to: "/tree", label: "Live tree", icon: NetworkIcon, end: false },
  { to: "/audit", label: "Audit", icon: BriefcaseIcon, end: false },
  { to: "/text", label: "Text", icon: TextLinesIcon, end: false },
] as const;

/** Shared top navigation so every page explains where you are and where to go next. */
export default function NavBar({ compact = false }: { compact?: boolean }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const location = useLocation();

  useEffect(() => setMenuOpen(false), [location.key]);

  useEffect(() => {
    if (!menuOpen) return;

    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      setMenuOpen(false);
      menuButtonRef.current?.focus();
    };

    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [menuOpen]);

  return (
    <nav className={`nav-bar nav-m-root ${compact ? "is-compact" : ""}`} aria-label="Main">
      <style>{`
        @media (max-width: 899.98px) {
          .nav-m-root {
            min-height: 84px;
            padding: 16px 0;
            align-items: flex-start;
            justify-content: center;
            flex-direction: column;
            gap: 12px;
          }

          .nav-m-root .nav-m-row {
            width: 100%;
            justify-content: space-between;
          }

          .nav-m-root .nav-m-button {
            display: inline-flex;
          }

          .nav-m-root .nav-m-panel {
            display: none;
            width: 100%;
            padding: 8px;
            align-items: stretch;
            flex-direction: column;
            border-radius: 18px;
          }

          .nav-m-root .nav-m-panel.nav-m-open {
            display: flex;
          }

          .nav-m-root .nav-m-panel a {
            width: 100%;
            padding: 12px 14px;
            text-align: left;
          }
        }
      `}</style>
      <div className="nav-row nav-m-row">
        <NavLink to="/" className="nav-brand" end>
          <span className="brand-mark" aria-hidden="true">L</span>
          {!compact && <span className="nav-title">Lineage</span>}
        </NavLink>
        <button
          ref={menuButtonRef}
          className="secondary-button nav-menu-button nav-m-button"
          type="button"
          aria-expanded={menuOpen}
          aria-controls="main-navigation"
          onClick={() => setMenuOpen((open) => !open)}
        >
          Menu
        </button>
      </div>
      <div
        className={`nav-links nav-m-panel ${menuOpen ? "nav-m-open" : ""}`}
        id="main-navigation"
      >
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
