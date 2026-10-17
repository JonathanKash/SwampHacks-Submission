import type { ReactNode } from "react";
import type { ConfidenceByCorpus } from "./api";

interface ConfidenceValue {
  precision: number | null;
  n: number;
  by_corpus?: ConfidenceByCorpus;
}

interface ConfidenceChipProps {
  confidence: ConfidenceValue;
  legacy: ReactNode;
  className?: string;
  legacyTitle?: string;
}

function percent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function corpusName(key: string): string {
  if (key === "web-memes-clean-truth") return "web memes, clean truth";
  if (key === "web-memes") return "web memes, all pairs";
  return key.replace(/-/g, " ");
}

function corpusEntries(confidence: ConfidenceValue) {
  return Object.entries(confidence.by_corpus ?? {});
}

function reportableCorpusEntries(confidence: ConfidenceValue) {
  return corpusEntries(confidence).filter(([, result]) => result.n >= 5);
}

export function hasCorpusConfidence(confidence: ConfidenceValue): boolean {
  return confidence.precision !== null && reportableCorpusEntries(confidence).length > 0;
}

function corpusLabel(confidence: ConfidenceValue): string | null {
  if (confidence.precision === null) return null;
  const entries = reportableCorpusEntries(confidence);
  if (entries.length === 0) return null;
  const [corpus, result] = entries.reduce((lowest, entry) => (
    entry[1].precision < lowest[1].precision ? entry : lowest
  ));
  return [
    `${percent(confidence.precision)} on synthetic chains`,
    `${percent(result.precision)} on ${corpusName(corpus)}`,
  ].join(" · ");
}

function corpusTitle(confidence: ConfidenceValue): string {
  return [
    `n=${confidence.n} synthetic`,
    ...corpusEntries(confidence).map(([corpus, result]) => (
      `${percent(result.precision)} on ${corpusName(corpus)} (n=${result.n})`
    )),
  ].join(", ");
}

/** Keeps legacy confidence copy intact until cross-corpus calibration is available. */
export default function ConfidenceChip({ confidence, legacy, className = "", legacyTitle }: ConfidenceChipProps) {
  const label = corpusLabel(confidence);
  const classes = `${className}${label ? " has-corpora" : ""}`.trim();
  return (
    <span className={classes || undefined} title={label ? corpusTitle(confidence) : legacyTitle}>
      {label ?? legacy}
    </span>
  );
}
