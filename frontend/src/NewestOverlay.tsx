import { useEffect, useState } from "react";
import type { TreeEdge, TreeNode, TreeResponse } from "./api";

const SHOW_MS = 7000;

interface Arrival {
  node: TreeNode;
  parent: TreeNode | null;
  edge: TreeEdge | null;
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
    setArrival({ node, parent, edge });
  }, [tree, seen]);

  // Dismiss timer lives in its own effect: the detection effect above re-runs when
  // `seen` changes and would otherwise cancel the timer it just started.
  useEffect(() => {
    if (!arrival) return;
    const timer = window.setTimeout(() => setArrival(null), SHOW_MS);
    return () => window.clearTimeout(timer);
  }, [arrival]);

  if (!arrival) return null;
  const { node, parent, edge } = arrival;
  const precision = node.evidence.confidence.precision;
  const verdict = node.root ? "placed as a new original" : node.correct ? "parent identified correctly" : "wrong parent";
  return (
    <div
      className={`arrival ${node.root ? "" : node.correct ? "is-ok" : "is-bad"}`}
      role="status"
      aria-live="polite"
      onClick={() => setArrival(null)}
    >
      <p className="eyebrow">New image just arrived</p>
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
    </div>
  );
}
