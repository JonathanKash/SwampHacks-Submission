import { useEffect, useState } from "react";
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
  const words = value.replace(/[-_]+/g, " ").trim().toLowerCase();
  return words ? `${words[0].toUpperCase()}${words.slice(1)}` : value;
}

function resultText(result: CalibrationCount | undefined): string {
  if (!result || result.n === 0) return "—";
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
