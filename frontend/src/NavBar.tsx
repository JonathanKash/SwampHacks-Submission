import { NavLink } from "react-router-dom";

/** Shared top navigation so every page explains where you are and where to go next. */
export default function NavBar({ compact = false }: { compact?: boolean }) {
  return (
    <nav className={`nav-bar ${compact ? "is-compact" : ""}`} aria-label="Main">
      <NavLink to="/" className="nav-brand" end>
        <span className="brand-mark" aria-hidden="true">L</span>
        {!compact && <span className="nav-title">Lineage</span>}
      </NavLink>
      <div className="nav-links">
        <NavLink to="/" end className={({ isActive }) => (isActive ? "is-active" : "")}>
          About
        </NavLink>
        <NavLink to="/edit" className={({ isActive }) => (isActive ? "is-active" : "")}>
          Make an edit
        </NavLink>
        <NavLink to="/tree" className={({ isActive }) => (isActive ? "is-active" : "")}>
          Live tree
        </NavLink>
        <NavLink to="/audit" className={({ isActive }) => (isActive ? "is-active" : "")}>
          Audit
        </NavLink>
      </div>
    </nav>
  );
}
