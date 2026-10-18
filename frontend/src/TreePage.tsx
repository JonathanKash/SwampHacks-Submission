import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { type CompareReportResponse, type TreeNode, type TreeResponse, compareIds, deleteItem } from "./api";
import CompareReport from "./CompareReport";
import ConfidenceChip from "./ConfidenceChip";
import EvidenceList from "./EvidenceList";
import NewestOverlay from "./NewestOverlay";
import RemoveButton from "./RemoveButton";
import QrCode from "./QrCode";
import ReplayOverlay from "./ReplayOverlay";
import { provenancePath } from "./provenance";
import TreeView from "./TreeView";
import { usePageTitle } from "./usePageTitle";
import { useHealth } from "./useHealth";
import { useTreePolling } from "./useTreePolling";
import VisualDiff from "./VisualDiff";

function formatPercent(value: number | null): string {
  if (value === null) return "—";
  return Number.isInteger(value) ? value.toFixed(0) : value.toFixed(1);
}

/** Big-screen page: the live forest, a scoreboard, and enough legend to read it from across a room. */
export default function TreePage() {
  usePageTitle("Live tree · Lineage");

  const { tree, loading, fetching, error } = useTreePolling();
  const health = useHealth();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [parentReport, setParentReport] = useState<CompareReportResponse | null>(null);
  const [parentReportOpen, setParentReportOpen] = useState(false);
  const [parentReportLoading, setParentReportLoading] = useState(false);
  const [parentReportError, setParentReportError] = useState<string | null>(null);
  const [replayTree, setReplayTree] = useState<TreeResponse | null>(null);
  const pageRef = useRef<HTMLElement>(null);
  const headerRef = useRef<HTMLElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const replayButtonRef = useRef<HTMLButtonElement>(null);
  const returnFocusRef = useRef<SVGGElement | null>(null);
  const compareRequestRef = useRef<AbortController | null>(null);
  const selectNode = useCallback((node: TreeNode, target: SVGGElement) => {
    returnFocusRef.current = target;
    setSelectedId(node.id);
  }, []);
  const closeDetails = useCallback(() => {
    setSelectedId(null);
    window.requestAnimationFrame(() => returnFocusRef.current?.focus({ preventScroll: true }));
  }, []);

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

  useEffect(() => {
    compareRequestRef.current?.abort();
    setParentReport(null);
    setParentReportOpen(false);
    setParentReportLoading(false);
    setParentReportError(null);
  }, [selectedId]);

  useEffect(() => () => compareRequestRef.current?.abort(), []);

  useEffect(() => {
    const page = pageRef.current;
    const header = headerRef.current;
    if (!page || !header) return;

    // The responsive header owns its height; the canvas uses whatever remains.
    const syncHeaderHeight = () => {
      page.style.setProperty("--tree-header-height", `${header.getBoundingClientRect().height}px`);
    };
    const observer = new ResizeObserver(syncHeaderHeight);
    observer.observe(header);
    syncHeaderHeight();
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (selectedId) closeButtonRef.current?.focus({ preventScroll: true });
  }, [selectedId]);

  useEffect(() => {
    if (!selectedId) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      closeDetails();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [closeDetails, selectedId]);

  const accuracy = tree?.accuracy;
  const demoMode = tree?.mode !== "audit";
  const closeReplay = useCallback(() => {
    setReplayTree(null);
    window.requestAnimationFrame(() => replayButtonRef.current?.focus());
  }, []);

  const handleCompareParent = async () => {
    if (!selectedNode?.predicted_parent || parentReportLoading) return;
    if (parentReport) {
      setParentReportOpen((open) => !open);
      return;
    }

    const controller = new AbortController();
    compareRequestRef.current?.abort();
    compareRequestRef.current = controller;
    setParentReportLoading(true);
    setParentReportError(null);
    try {
      const next = await compareIds(selectedNode.predicted_parent, selectedNode.id, undefined, controller.signal);
      if (!controller.signal.aborted) {
        setParentReport(next);
        setParentReportOpen(true);
      }
    } catch (compareError) {
      if (!(compareError instanceof DOMException && compareError.name === "AbortError")) {
        setParentReportError(compareError instanceof Error ? compareError.message : "Could not compare this pair.");
      }
    } finally {
      if (!controller.signal.aborted) setParentReportLoading(false);
    }
  };

  return (
    <main className="tree-page" ref={pageRef}>
      <header className="tree-header" ref={headerRef}>
        <Link to="/" className="tree-brand" title="About Lineage">
          <span className="brand-mark" aria-hidden="true">L</span>
          <div>
            <p>Live reconstruction · edit at <strong>/edit</strong></p>
            <h1>Lineage</h1>
          </div>
        </Link>
        <QrCode size={84} baseUrl={health?.lan_url ?? null} />
        <div className="scoreboard">
          {demoMode ? (
            <div className="fool-score" aria-live="polite" aria-atomic="true">
              <p>
                <strong>Fool Lineage</strong>
                {accuracy && accuracy.total > 0 ? (
                  <span>
                    {` · ${accuracy.total - accuracy.correct} of ${accuracy.total} edits fooled it · ${formatPercent(accuracy.pct)}% placed correctly`}
                  </span>
                ) : (
                  <span> · No edits yet</span>
                )}
              </p>
              <span className="fool-score-sub">
                Make an edit on the tablet (/edit). If your version lands under the wrong parent, you fooled it.
              </span>
            </div>
          ) : (
            <div className="score-main" aria-live="polite" aria-atomic="true">
              <span className="score-label">tree accuracy</span>
              <strong>{accuracy ? `${formatPercent(accuracy.pct)}%` : "—"}</strong>
              <span className="score-sub">
                {accuracy ? `${accuracy.correct} of ${accuracy.total} parents identified correctly` : "waiting for data"}
              </span>
            </div>
          )}
          <div className="score-side">
            {demoMode && (
              <button
                className="secondary-button replay-button"
                type="button"
                ref={replayButtonRef}
                disabled={!tree || tree.nodes.length === 0}
                onClick={() => tree && setReplayTree(tree)}
              >
                Replay
              </button>
            )}
            {health && !health.clip && (
              <span className="mode-badge" title="low-memory mode · pHash candidates">
                pHash mode
              </span>
            )}
            <span>{tree?.nodes.length ?? 0} images</span>
            <span>{tree?.nodes.filter((node) => node.root).length ?? 0} families</span>
            <details className="tree-export">
              <summary className="secondary-button tree-export-button">Export</summary>
              <div className="tree-export-menu">
                <a className="secondary-button tree-report-link" href="/api/report" download>
                  JSON
                </a>
                <a
                  className="secondary-button tree-report-link"
                  href="/api/report.html"
                  target="_blank"
                  rel="noreferrer"
                >
                  HTML report
                </a>
              </div>
            </details>
            <span
              className={`poll-dot ${fetching ? "is-fetching" : ""} ${error ? "has-error" : ""}`}
              title={error ? "reconnecting" : "server connected"}
              aria-label={error ? "reconnecting" : "server connected"}
            />
          </div>
        </div>
      </header>

      <section className="tree-body">
        {loading && !tree && (
          <div className="tree-empty">
            <div className="tree-loading-card" aria-hidden="true">
              <span />
              <span />
              <span />
            </div>
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
            <NewestOverlay tree={tree} />
            {replayTree && <ReplayOverlay tree={replayTree} onClose={closeReplay} />}

            {newest && (
              <div
                className={`newest-callout ${newest.node.root ? "" : newest.node.correct ? "is-ok" : "is-bad"}`}
                role="status"
              >
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
                      {newest.node.evidence.confidence.precision !== null && (
                        <>
                          {" · "}
                          <ConfidenceChip
                            confidence={newest.node.evidence.confidence}
                            className="confidence-inline"
                            legacy={`${Math.round(newest.node.evidence.confidence.precision * 100)}% empirical precision`}
                          />
                        </>
                      )}
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
                <button
                  className="panel-close"
                  type="button"
                  ref={closeButtonRef}
                  onClick={closeDetails}
                  aria-label="Close details"
                >
                  ×
                </button>
                <p className="eyebrow">{selectedNode.root ? "Original" : "Edited copy"}</p>
                {/* the full sentence ("re-saved as low-quality JPEG") reads better than the short pill label ("jpeg") */}
                <h2>{incomingEdge ? incomingEdge.explain || incomingEdge.label : "start of its family"}</h2>
                <img src={selectedNode.url} alt={`Full-size image ${selectedNode.id}`} />
                {selectedNode.root && selectedNode.explains.length > 0 && (
                  <div className="candidate-original-callout" role="note">
                    <strong>
                      Candidate original · explains {selectedNode.explains.length}{" "}
                      {selectedNode.explains.length === 1 ? "version" : "versions"}
                    </strong>
                    <p>
                      Every other version in this family costs less to derive from this image than the reverse.
                      {" "}If an earlier version is found later, upload it: the tree re-roots automatically.
                    </p>
                  </div>
                )}
                {!selectedNode.root && tree && (
                  <VisualDiff
                    key={`${selectedNode.id}-${tree.version}`}
                    src={`/api/diff/${encodeURIComponent(selectedNode.id)}?t=${tree.version}`}
                  />
                )}
                {!selectedNode.root && selectedNode.predicted_parent && (
                  <div className="compare-parent-control">
                    <button
                      className="primary-button"
                      type="button"
                      aria-expanded={parentReport ? parentReportOpen : undefined}
                      aria-controls="tree-parent-compare-report"
                      disabled={parentReportLoading}
                      onClick={() => void handleCompareParent()}
                    >
                      {parentReportLoading ? (
                        <>
                          <span className="spinner" aria-hidden="true" />
                          Aligning and measuring…
                        </>
                      ) : parentReport && parentReportOpen ? (
                        "Hide pairwise report"
                      ) : (
                        "Why is this the parent?"
                      )}
                    </button>
                    {parentReportError && <p className="compare-inline-error" role="alert">{parentReportError}</p>}
                    {parentReport && parentReportOpen && (
                      <div id="tree-parent-compare-report">
                        <CompareReport report={parentReport} />
                      </div>
                    )}
                  </div>
                )}
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
                {new URLSearchParams(window.location.search).get("admin") === "1" && (
                  <RemoveButton remove={(token) => deleteItem(selectedNode.id, token)} onRemoved={() => setSelectedId(null)} />
                )}
              </aside>
            )}
          </div>
        )}
        {error && tree && <div className="tree-error-toast">Live update retrying · {error}</div>}
      </section>
    </main>
  );
}
