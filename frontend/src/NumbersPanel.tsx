import { type ReactNode, useEffect, useState } from "react";
import { fetchCalibration, type CalibrationCount, type CalibrationResponse } from "./api";

const MARGIN_BUCKETS = [
  "margin ≥ 0.30",
  "margin 0.05–0.30",
  "margin 0.02–0.05",
  "margin < 0.02",
] as const;

interface NumbersPanelProps {
  compact?: boolean;
}

function humanise(value: string): string {
  if (value === "web-memes-clean-truth") return "Web memes, clean truth";
  if (value === "web-memes") return "Web memes, all pairs";
  const words = value.replace(/[-_]+/g, " ").trim().toLowerCase();
  return words ? `${words[0].toUpperCase()}${words.slice(1)}` : value;
}

function resultText(result: CalibrationCount | undefined): ReactNode {
  if (!result) return "—";
  if (result.n < 5) {
    return <span className="numbers-too-few" title="too few decisions to report a rate">n&lt;5</span>;
  }
  return `${Math.round((result.correct / result.n) * 100)}% (n=${result.n})`;
}

/** Reusable view of the empirical calibration data behind confidence labels. */
export default function NumbersPanel({ compact = false }: NumbersPanelProps) {
  const [calibration, setCalibration] = useState<CalibrationResponse | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    void fetchCalibration(controller.signal).then(setCalibration).catch(() => undefined);
    return () => controller.abort();
  }, []);

  if (!calibration) return null;

  const corpora = Object.entries(calibration.corpora ?? {});
  const edits = Object.entries(calibration.per_edit ?? {}).filter(([edit]) => edit !== "root");

  return (
    <div className={`numbers-panel${compact ? " numbers-panel--compact" : ""}`}>
      <h3 className="numbers-title">How often a decision with this margin was right</h3>
      <div className="numbers-table-wrap">
        <table className="numbers-table">
          <caption>
            Generated {calibration.generated_at} from {calibration.runs.join(", ")}. The lower number is the
            honest expectation for unknown files.
            <br />
            Clean truth = pairs whose documented original is at least as large as its variant; the all-pairs column
            includes ambiguous ground truth.
          </caption>
          <thead>
            <tr>
              <th scope="col">Margin</th>
              <th scope="col">Synthetic edit chains</th>
              {corpora.map(([key]) => (
                <th scope="col" key={key}>{humanise(key)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {MARGIN_BUCKETS.map((bucket) => (
              <tr key={bucket}>
                <th scope="row">{bucket}</th>
                <td>{resultText(calibration.buckets[bucket])}</td>
                {corpora.map(([key, corpus]) => (
                  <td key={key}>{resultText(corpus.buckets[bucket])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className="numbers-cards" aria-label="Accuracy by margin and corpus">
        {MARGIN_BUCKETS.map((bucket) => (
          <li className="numbers-card" key={bucket}>
            <h4>{bucket}</h4>
            <div className="numbers-card-synthetic">
              <span>Synthetic edit chains</span>
              <strong>{resultText(calibration.buckets[bucket])}</strong>
            </div>
            <dl className="numbers-card-corpora">
              {corpora.map(([key, corpus]) => (
                <div key={key}>
                  <dt>{humanise(key)}</dt>
                  <dd>{resultText(corpus.buckets[bucket])}</dd>
                </div>
              ))}
            </dl>
          </li>
        ))}
      </ul>
      <p className="numbers-cards-note">
        Generated {calibration.generated_at} from {calibration.runs.join(", ")}. The lower number is the
        honest expectation for unknown files. Clean truth means the documented original is at least as large
        as its variant; all pairs includes ambiguous ground truth.
      </p>

      {calibration.caption_side && (
        <p className="numbers-caption-cue" title={calibration.caption_side.source}>
          Caption-side cue: {calibration.caption_side.correct}/{calibration.caption_side.n} on the benchmark
        </p>
      )}

      {edits.length > 0 && (
        <div className="numbers-edits" aria-label="Accuracy by edit type">
          {edits.map(([edit, result]) => (
            <span key={edit}>{humanise(edit).toLowerCase()} {resultText(result)}</span>
          ))}
        </div>
      )}
    </div>
  );
}
