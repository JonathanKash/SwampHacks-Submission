import { useEffect, useState } from "react";
import type { TreeEdge, TreeNode, TreeResponse } from "./api";

const SHOW_MS = 7000;

interface Arrival {
  node: TreeNode;
  parent: TreeNode | null;
  edge: TreeEdge | null;
  explained: TreeNode[];
  isOriginal: boolean;
}

/**
 * The big-screen moment: when a new image lands, show it large next to the image it
 * came from, with the reading and the verdict, then get out of the way. Skips the
 * first load so a cold start does not flash the oldest-newest image.
 */
export default function NewestOverlay({ tree }: { tree: TreeResponse | null }) {
  const [arrival, setArrival] = useState<Arrival | null>(null);
  const [seen, setSeen] = useState<string | null | undefined>(undefined);

  useEffect(() => {
    if (!tree) return;
    const id = tree.newest_id;
    if (seen === undefined) {
      setSeen(id); // first payload: remember, do not announce
      return;
    }
    if (!id || id === seen) return;
    setSeen(id);
    const node = tree.nodes.find((n) => n.id === id);
    if (!node) return;
    const edge = tree.edges.find((e) => e.dst === id) ?? null;
    const parent = tree.nodes.find((n) => n.id === node.predicted_parent) ?? null;
    const isOriginal = node.root && (node.explains.length > 0 || tree.newest_took_over);
    const explained = node.explains
      .slice(0, 3)
      .map((explainedId) => tree.nodes.find((candidate) => candidate.id === explainedId))
      .filter((candidate): candidate is TreeNode => candidate !== undefined);
    setArrival({ node, parent, edge, explained, isOriginal });
  }, [tree, seen]);

  // Dismiss timer lives in its own effect: the detection effect above re-runs when
  // `seen` changes and would otherwise cancel the timer it just started.
  useEffect(() => {
    if (!arrival) return;
    const timer = window.setTimeout(() => setArrival(null), SHOW_MS);
    return () => window.clearTimeout(timer);
  }, [arrival]);

  if (!arrival) return null;
  const { node, parent, edge, explained, isOriginal } = arrival;
  const precision = node.evidence.confidence.precision;
  const verdict = node.root ? "placed as a new original" : node.correct ? "parent identified correctly" : "wrong parent";
  const versionLabel = node.explains.length === 1 ? "version" : "versions";
  return (
    <div
      className={`arrival ${isOriginal ? "is-original" : node.root ? "" : node.correct ? "is-ok" : "is-bad"}`}
      role="status"
      aria-live="polite"
      onClick={() => setArrival(null)}
    >
      <p className="eyebrow">{isOriginal ? "Original recognised" : "New image just arrived"}</p>
      {isOriginal ? (
        <div className="arrival-pair is-original-pair">
          <figure className="is-new">
            <img src={node.url} alt="New candidate original" />
            <figcaption>
              This upload explains {node.explains.length} existing {versionLabel} and is now the candidate original
            </figcaption>
          </figure>
          {explained.length > 0 && <span className="arrival-arrow" aria-hidden="true">→</span>}
          {explained.length > 0 && (
            <div className="arrival-explained" aria-label="Existing versions explained by this upload">
              {explained.map((explainedNode, index) => (
                <img key={explainedNode.id} src={explainedNode.thumb} alt={`Existing version ${index + 1}`} />
              ))}
            </div>
          )}
        </div>
      ) : (
        <>
          <div className="arrival-pair">
            {parent && (
              <figure>
                <img src={parent.url} alt="" />
                <figcaption>derived from</figcaption>
              </figure>
            )}
            {parent && <span className="arrival-arrow" aria-hidden="true">→</span>}
            <figure className="is-new">
              <img src={node.url} alt="" />
              <figcaption>{edge ? edge.explain : "no parent found"}</figcaption>
            </figure>
          </div>
          <p className="arrival-verdict">
            {verdict}
            {precision !== null && !node.root && ` · ${Math.round(precision * 100)}% empirical precision`}
          </p>
        </>
      )}
    </div>
  );
}
