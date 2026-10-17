import { useId, useState } from "react";
import type { CompareReportResponse } from "./api";

interface CompareReportProps {
  report: CompareReportResponse;
}

function percent(value: number): string {
  const amount = value * 100;
  return `${Number.isInteger(amount) ? amount.toFixed(0) : amount.toFixed(1)}%`;
}

function verdictText(report: CompareReportResponse): string {
  if (report.verdict === "parent-child" && report.parent && report.child) {
    return `${report.parent} is the parent of ${report.child}`;
  }
  if (report.verdict === "siblings") return "Siblings: two copies of a common source";
  if (report.verdict === "unrelated") return "Unrelated";
  return `Inconclusive: ${report.relation}`;
}

function shortHash(value: string | null): string {
  return value ? `${value.slice(0, 16)}…` : "unavailable";
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
        <h2>{verdictText(report)}</h2>
        <p className="compare-summary">{report.summary}</p>
        {noParentClaimed && <p className="compare-no-parent">No parent is claimed.</p>}
        <div className="compare-confidence-row">
          <span className={`confidence ${report.confidence.precision === null ? "muted" : ""}`}>
            {report.confidence.precision !== null
              ? `${percent(report.confidence.precision)} empirical precision (n=${report.confidence.n})`
              : report.costs.margin !== null
                ? `margin ${report.costs.margin}`
                : "no direction claimed"}
          </span>
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
                      className={signal.kind === "metadata" ? "is-metadata" : ""}
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
