import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { TreeNode } from "./api";
import EvidenceList from "./EvidenceList";
import { provenancePath } from "./provenance";
import TreeView from "./TreeView";
import { useTreePolling } from "./useTreePolling";

function formatPercent(value: number | null): string {
  if (value === null) return "—";
  return Number.isInteger(value) ? value.toFixed(0) : value.toFixed(1);
}

/** Big-screen page: the live forest, a scoreboard, and enough legend to read it from across a room. */
export default function TreePage() {
  const { tree, loading, fetching, error } = useTreePolling();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selectNode = useCallback((node: TreeNode) => setSelectedId(node.id), []);

  const selectedNode = useMemo(
    () => tree?.nodes.find((node) => node.id === selectedId) ?? null,
    [selectedId, tree],
  );
  const incomingEdge = useMemo(
    () => tree?.edges.find((edge) => edge.dst === selectedId) ?? null,
    [selectedId, tree],
  );
  const newest = useMemo(() => {
    if (!tree?.newest_id) return null;
    const node = tree.nodes.find((candidate) => candidate.id === tree.newest_id);
    const edge = tree.edges.find((candidate) => candidate.dst === tree.newest_id) ?? null;
    return node ? { node, edge } : null;
  }, [tree]);

  useEffect(() => {
    if (selectedId && tree && !tree.nodes.some((node) => node.id === selectedId)) {
      setSelectedId(null);
    }
  }, [selectedId, tree]);

  const accuracy = tree?.accuracy;

  return (
    <main className="tree-page">
      <header className="tree-header">
        <Link to="/" className="tree-brand" title="About Lineage">
          <span className="brand-mark" aria-hidden="true">L</span>
          <div>
            <p>Live reconstruction · edit at <strong>/edit</strong></p>
            <h1>Lineage</h1>
          </div>
        </Link>
        <div className="scoreboard" aria-live="polite">
          <div className="score-main">
            <span className="score-label">tree accuracy</span>
            <strong>{accuracy ? `${formatPercent(accuracy.pct)}%` : "—"}</strong>
            <span className="score-sub">
              {accuracy ? `${accuracy.correct} of ${accuracy.total} parents identified correctly` : "waiting for data"}
            </span>
          </div>
          <div className="score-side">
            <span>{tree?.nodes.length ?? 0} images</span>
            <span>{tree?.nodes.filter((node) => node.root).length ?? 0} families</span>
            <span
              className={`poll-dot ${fetching ? "is-fetching" : ""} ${error ? "has-error" : ""}`}
              title={error ?? "Checking for new images every 2 seconds"}
              aria-label={error ? "Live updates retrying" : "Live updates active"}
            />
          </div>
        </div>
      </header>

      <section className="tree-body">
        {loading && !tree && (
          <div className="tree-empty">
            <span className="spinner large" aria-hidden="true" />
            <p>Reconstructing the tree…</p>
          </div>
        )}
        {!loading && tree && tree.nodes.length === 0 && (
          <div className="tree-empty">
            <span className="waiting-orbit" aria-hidden="true" />
            <p>Waiting for the first upload…</p>
            <small>Open /edit on the tablet to add one.</small>
          </div>
        )}
        {!loading && !tree && (
          <div className="tree-empty">
            <p>Could not load the tree.</p>
            {error && <small>{error}</small>}
          </div>
        )}
        {tree && tree.nodes.length > 0 && (
          <div className={`tree-canvas-wrap ${selectedNode ? "has-panel" : ""}`}>
            <TreeView data={tree} selectedId={selectedId} onSelect={selectNode} />

            {newest && (
              <div className={`newest-callout ${newest.node.root ? "" : newest.node.correct ? "is-ok" : "is-bad"}`}>
                <img src={newest.node.thumb} alt="" />
                <div>
                  <p className="eyebrow">Newest image</p>
                  <strong>
                    {newest.node.root
                      ? "placed as a new original"
                      : newest.edge
                        ? newest.edge.explain
                        : "placed in the tree"}
                  </strong>
                  {!newest.node.root && (
                    <span>
                      {newest.node.correct ? "parent identified correctly" : "wrong parent"}
                      {newest.node.evidence.confidence.precision !== null &&
                        ` · ${Math.round(newest.node.evidence.confidence.precision * 100)}% empirical precision`}
                    </span>
                  )}
                </div>
              </div>
            )}

            <div className="legend tree-legend" aria-label="How to read the tree">
              <span className="legend-item"><i className="swatch ok" /> correct parent</span>
              <span className="legend-item"><i className="swatch bad" /> wrong parent</span>
              <span className="legend-item"><i className="swatch dashed" /> matched by meaning</span>
              <span className="legend-item"><i className="swatch new" /> newest</span>
              <span className="legend-hint">tap a picture for details</span>
            </div>

            {selectedNode && (
              <aside className="node-panel" aria-label="Image details">
                <button className="panel-close" type="button" onClick={() => setSelectedId(null)} aria-label="Close details">
                  ×
                </button>
                <p className="eyebrow">{selectedNode.root ? "Original" : "Edited copy"}</p>
                <h2>{incomingEdge ? incomingEdge.label : "root of its family"}</h2>
                <img src={selectedNode.url} alt={`Full-size image ${selectedNode.id}`} />
                {incomingEdge ? (
                  <div className="edge-details">
                    <div className="detail-heading">
                      <span>Lineage's reading</span>
                      <strong>cost {incomingEdge.cost.toFixed(3)}</strong>
                    </div>
                    <p>{incomingEdge.explain}</p>
                    <div className="detail-tags">
                      <span className={incomingEdge.correct ? "correct-tag" : "wrong-tag"}>
                        {incomingEdge.correct ? "correct parent" : "wrong parent"}
                      </span>
                      {incomingEdge.semantic && <span>matched by meaning</span>}
                    </div>
                    <EvidenceList evidence={incomingEdge.evidence} compact />
                    <div className="provenance">
                      <h3>Provenance path</h3>
                      <ol>
                        {provenancePath(tree, selectedNode.id).map((step) => (
                          <li key={step.node.id} className={step.node.id === selectedNode.id ? "is-current" : ""}>
                            <img src={step.node.thumb} alt="" />
                            <span>{step.edge ? step.edge.explain : "original"}</span>
                          </li>
                        ))}
                      </ol>
                    </div>
                  </div>
                ) : (
                  <div className="root-details">
                    <span>No parent</span>
                    <p>Nothing in the pool explains this image more cheaply than calling it an original.</p>
                    <EvidenceList evidence={selectedNode.evidence} compact />
                  </div>
                )}
                <small className="node-id-small">id {selectedNode.id}</small>
              </aside>
            )}
          </div>
        )}
        {error && tree && <div className="tree-error-toast">Live update retrying · {error}</div>}
      </section>
    </main>
  );
}
