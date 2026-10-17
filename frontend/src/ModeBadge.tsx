import { useHealth } from "./useHealth";

/** Transparency: say so when the server runs without CLIP (pHash-only candidates). */
export default function ModeBadge() {
  const health = useHealth();
  if (!health || health.clip) return null;
  return (
    <span
      className="mode-badge"
      title="CLIP is off on this server; candidate search uses pHash only, so restyles may be matched less reliably."
    >
      low-memory mode · pHash candidates
    </span>
  );
}
