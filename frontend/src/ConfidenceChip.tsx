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
  return key.replace(/-/g, " ");
}

function corpusEntries(confidence: ConfidenceValue) {
  return Object.entries(confidence.by_corpus ?? {});
}

export function hasCorpusConfidence(confidence: ConfidenceValue): boolean {
  return confidence.precision !== null && corpusEntries(confidence).length > 0;
}

function corpusLabel(confidence: ConfidenceValue): string | null {
  if (confidence.precision === null) return null;
  const entries = corpusEntries(confidence);
  if (entries.length === 0) return null;
  return [
    `${percent(confidence.precision)} on synthetic chains`,
    ...entries.map(([corpus, result]) => `${percent(result.precision)} on ${corpusName(corpus)}`),
  ].join(" · ");
}

function corpusTitle(confidence: ConfidenceValue): string {
  return [
    `n=${confidence.n} synthetic`,
    ...corpusEntries(confidence).map(([corpus, result]) => `n=${result.n} ${corpusName(corpus)}`),
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
