import { useId, useState } from "react";
import type { CompareReportResponse } from "./api";
import ConfidenceChip from "./ConfidenceChip";

interface CompareReportProps {
  report: CompareReportResponse;
}

const DECISIVE_CUE_NAMES: Record<string, string> = {
  coverage: "coverage",
  color_residual: "colour fit",
  blockiness: "JPEG grid energy",
  resolution: "resolution",
  chroma: "colour gained from gray",
  entropy: "histogram entropy",
  blobs: "compact content difference",
  caption_removed: "caption removed",
  edit_ops: "number of edit operations",
};

function percent(value: number): string {
  const amount = value * 100;
  return `${Number.isInteger(amount) ? amount.toFixed(0) : amount.toFixed(1)}%`;
}

function verdictText(report: CompareReportResponse): string {
  if (report.verdict === "parent-child" && report.parent && report.child) {
    return `${report.parent} is the parent of ${report.child}`;
  }
  if (report.verdict === "siblings") return "Siblings: two copies of a common source";
  if (report.verdict === "unrelated") return "Unrelated: these two do not line up";
  // "which came first" is the question the page asks; answer it in the same words
  return "Inconclusive: the pixels cannot tell which came first";
}

function shortHash(value: string | null): string {
  return value ? `${value.slice(0, 16)}…` : "unavailable";
}

function confidenceText(report: CompareReportResponse): string {
  const { confidence } = report;
  if (confidence.bucket === "caption-side cue") {
    return `≥ ${percent(confidence.precision)} (Wilson lower bound) · caption-side cue, observed ${percent(confidence.observed)} on n=${confidence.n} benchmark pairs`;
  }
  if (confidence.bucket?.startsWith("margin") && confidence.precision !== null) {
    return `${percent(confidence.precision)} empirical precision (n=${confidence.n})`;
  }
  return report.costs.margin !== null ? `margin ${report.costs.margin}` : "no direction claimed";
}

function DetailList({ items, empty }: { items: string[]; empty?: string }) {
  if (items.length === 0) return <p className="compare-empty">{empty ?? "None"}</p>;
  return (
    <ul>
      {items.map((item) => <li key={item}>{item}</li>)}
    </ul>
  );
}

/** Complete pairwise decision report, reusable for uploads and existing tree nodes. */
export default function CompareReport({ report }: CompareReportProps) {
  const [expanded, setExpanded] = useState(false);
  const evidenceId = useId();
  const benchmark = report.benchmark_for_edit_type;
  const noParentClaimed = report.verdict === "inconclusive" || report.verdict === "unrelated";
  const hasDecisionDetails = report.decisive_cues.length > 0
    || report.verdict === "parent-child"
    || report.caption_side !== null;

  const downloadReport = () => {
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "compare-report.json";
    anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 0);
  };

  return (
    <article className={`compare-report verdict-${report.verdict}`}>
      <div className="compare-verdict-card">
        <p className="eyebrow">Pairwise verdict</p>
        <h2>
          {verdictText(report)}
          {report.rerendered && (
            <span
              className="signal-kind is-indicator"
              title="The two align, but every pixel differs after the best colour fit: restyle, background swap or generative re-draw. Direction is not measurable from pixels."
            >
              Re-rendered copy
            </span>
          )}
        </h2>
        {report.verdict === "inconclusive" && (
          <h3 className="compare-relation">{report.relation}</h3>
        )}
        <p className="compare-summary">{report.summary}</p>
        {hasDecisionDetails && (
          <div className="compare-decision" aria-label="What decided the verdict">
            <strong>What decided it</strong>
            <div className="compare-decision-chips">
              {report.decisive_cues.map((cue) => (
                <span className="compare-decision-chip" key={cue}>
                  {DECISIVE_CUE_NAMES[cue] ?? cue}
                </span>
              ))}
              {report.decisive_cues.length === 0 && report.verdict === "parent-child" && (
                <span className="compare-decision-note">
                  several cues agree (no single cue is decisive)
                </span>
              )}
              {report.caption_side && (
                <span className="compare-decision-chip is-caption">
                  caption-like content on {report.caption_side}
                </span>
              )}
            </div>
          </div>
        )}
        {noParentClaimed && <p className="compare-no-parent">No parent is claimed.</p>}
        <div className="compare-confidence-row">
          <ConfidenceChip
            confidence={report.confidence}
            className={`confidence ${report.confidence.precision === null ? "muted" : ""}`}
            legacy={confidenceText(report)}
            legacyTitle={report.confidence.bucket === "caption-side cue"
              ? report.confidence.source
              : undefined}
          />
          {benchmark.edit_type !== null && benchmark.accuracy !== null && (
            <span className="compare-benchmark">
              Benchmark for {benchmark.edit_type} edits: {percent(benchmark.accuracy)} (n={benchmark.n})
            </span>
          )}
        </div>
        <div className="compare-report-actions">
          <button
            className="primary-button"
            type="button"
            aria-expanded={expanded}
            aria-controls={evidenceId}
            onClick={() => setExpanded((open) => !open)}
          >
            {expanded
              ? "Hide evidence"
              : report.verdict === "parent-child"
                ? "Why is this the parent?"
                : "Why this verdict?"}
          </button>
          <button className="secondary-button" type="button" onClick={downloadReport}>
            Download report (JSON)
          </button>
        </div>
      </div>

      {expanded && (
        <div className="compare-evidence evidence" id={evidenceId}>
          <section>
            <h3>Measured signals</h3>
            <div className="compare-table-wrap">
              <table className="compare-signals-table">
                <caption className="sr-only">Signals used to reach the pairwise verdict</caption>
                <thead>
                  <tr>
                    <th scope="col">Signal</th>
                    <th scope="col">What it found</th>
                    <th scope="col">Direction</th>
                    <th scope="col">Weight</th>
                  </tr>
                </thead>
                <tbody>
                  {report.signals.map((signal, index) => (
                    <tr
                      className={signal.kind === "metadata" || signal.kind === "indicator"
                        ? `is-${signal.kind}`
                        : ""}
                      key={`${signal.signal}-${index}`}
                    >
                      <th scope="row">
                        {signal.signal}
                        <span className={`signal-kind is-${signal.kind}`}>{signal.kind}</span>
                        {signal.kind === "metadata" && <small>hint, not evidence</small>}
                      </th>
                      <td>{signal.found}</td>
                      <td>{signal.direction}</td>
                      <td>{signal.weight}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="compare-indicator-note">
              Indicators are measured and shown; they never decide a verdict unless listed under
              {" \u201cWhat decided it\u201d."}
            </p>
          </section>

          <section>
            <h3>Visual evidence</h3>
            <div className="compare-plates">
              <figure>
                <img
                  src={report.plates.a_to_b.png}
                  alt="A aligned onto B, followed by B and the residual difference"
                />
                <figcaption>
                  <span>A aligned onto B · B · residual</span>
                  <small>
                    {report.plates.a_to_b.inliers} inliers · {report.plates.a_to_b.registered ? "registered" : "not registered"}
                  </small>
                </figcaption>
              </figure>
              <figure>
                <img
                  src={report.plates.b_to_a.png}
                  alt="B aligned onto A, followed by A and the residual difference"
                />
                <figcaption>
                  <span>B aligned onto A · A · residual</span>
                  <small>
                    {report.plates.b_to_a.inliers} inliers · {report.plates.b_to_a.registered ? "registered" : "not registered"}
                  </small>
                </figcaption>
              </figure>
            </div>
          </section>

          <div className="compare-detail-grid">
            <section>
              <h3>Conflicts</h3>
              <DetailList items={report.conflicts} empty="No conflicting signals" />
            </section>
            <section>
              <h3>Unavailable signals</h3>
              <DetailList items={report.unavailable} />
            </section>
            <section>
              <h3>AI-edit indicators (measured only)</h3>
              <DetailList items={report.ai_edit_indicators} empty="None measured" />
            </section>
            <section>
              <h3>Limitations</h3>
              <DetailList items={report.limitations} />
            </section>
          </div>

          <section className="compare-reproducibility">
            <h3>Reproducibility</h3>
            <dl>
              <dt>Tool version</dt>
              <dd>{report.reproducibility.tool_version}</dd>
              <dt>Weights hash</dt>
              <dd>{report.reproducibility.weights_sha256_12}</dd>
              <dt>SHA-256 A</dt>
              <dd title={report.reproducibility.input_sha256.A ?? undefined}>
                {shortHash(report.reproducibility.input_sha256.A)}
              </dd>
              <dt>SHA-256 B</dt>
              <dd title={report.reproducibility.input_sha256.B ?? undefined}>
                {shortHash(report.reproducibility.input_sha256.B)}
              </dd>
              <dt>Calibration runs</dt>
              <dd>{report.reproducibility.calibration_runs.join(", ") || "none recorded"}</dd>
            </dl>
          </section>
        </div>
      )}
    </article>
  );
}
