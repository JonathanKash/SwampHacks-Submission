import type { Evidence } from "./api";

function pct(value: number | null): string {
  return value === null ? "—" : `${Math.round(value * 100)}%`;
}

export function reliabilityTier(value: number): string {
  if (value >= 0.9) return "high reliability";
  if (value >= 0.75) return "moderate";
  return "low";
}

/** The measurements behind a decision, as sentences, plus the calibrated confidence. */
export default function EvidenceList({ evidence, compact = false }: { evidence: Evidence; compact?: boolean }) {
  const { confidence, margin } = evidence;
  return (
    <div className={`evidence ${compact ? "is-compact" : ""}`}>
      <div className="evidence-head">
        <span className="eyebrow">Evidence</span>
        {confidence.precision !== null ? (
          <span
            className="confidence"
            title={`${reliabilityTier(confidence.precision)}; ${confidence.bucket}; n = ${confidence.n} evaluated decisions`}
          >
            {pct(confidence.precision)} empirical precision
          </span>
        ) : (
          margin !== null && <span className="confidence muted">margin {margin.toFixed(3)}</span>
        )}
      </div>
      <ul>
        {evidence.reasons.map((reason) => (
          <li key={reason}>{reason}</li>
        ))}
      </ul>
    </div>
  );
}
