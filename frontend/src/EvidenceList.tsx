import type { Evidence } from "./api";
import ConfidenceChip, { hasCorpusConfidence } from "./ConfidenceChip";

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
  const explainsCorpora = hasCorpusConfidence(confidence);
  return (
    <div className={`evidence ${compact ? "is-compact" : ""}`}>
      <div className="evidence-head">
        <span className="eyebrow">Evidence</span>
        {confidence.precision !== null ? (
          <ConfidenceChip
            confidence={confidence}
            className="confidence"
            legacy={`${pct(confidence.precision)} empirical precision`}
            legacyTitle={`${reliabilityTier(confidence.precision)}; ${confidence.bucket}; n = ${confidence.n} evaluated decisions`}
          />
        ) : (
          margin !== null && <span className="confidence muted">margin {margin.toFixed(3)}</span>
        )}
      </div>
      {explainsCorpora && (
        <p className="confidence-explanation">
          Two numbers: the calibration corpus and an independent corpus of real web images. The lower one is the
          honest expectation for unknown files.
        </p>
      )}
      <ul>
        {evidence.reasons.map((reason) => (
          <li key={reason}>{reason}</li>
        ))}
      </ul>
    </div>
  );
}
