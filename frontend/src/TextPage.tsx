import { type ReactElement, useMemo, useState } from "react";
import { ApiError, type TextTreeResponse, buildTextTree } from "./api";
import EvidenceList from "./EvidenceList";
import NavBar from "./NavBar";

const EXAMPLE = [
  "The city council voted on Tuesday night to approve the new riverside park after months of debate. The plan includes a playground, a boat launch and a small amphitheatre. Construction is expected to begin in the spring and finish within eighteen months, according to the parks director.",
  "The city council voted on Tuesday night to approve the new riverside park after months of debate. The plan includes a playground, a boat launch and a small amphitheatre.",
  "The city council voted Tuesday night to approve the new riverside park after months of argument. The plan includes a playground, a boat ramp and a small amphitheatre.",
  "Council approves riverside park after months of argument. Plan includes playground, boat ramp, amphitheatre.",
  "The city council voted on Tuesday night to approve the new riverside park after months of debate. The plan includes a playground, a boat launch and a small amphitheatre. Construction is expected to begin in the spring and finish within eighteen months, according to the parks director. Local businesses welcomed the decision.",
];

function messageFrom(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "Something went wrong. Please try again.";
}

/** Second media type, same core: paste versions of a paragraph, get the edit tree. */
export default function TextPage() {
  const [versions, setVersions] = useState<string[]>(["", ""]);
  const [result, setResult] = useState<TextTreeResponse | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const filled = versions.filter((v) => v.trim()).length;

  const children = useMemo(() => {
    const map = new Map<string | null, string[]>();
    result?.nodes.forEach((node) => {
      const list = map.get(node.predicted_parent) ?? [];
      list.push(node.id);
      map.set(node.predicted_parent, list);
    });
    return map;
  }, [result]);

  const run = async () => {
    setBusy(true);
    setError(null);
    setSelected(null);
    try {
      const payload = versions.filter((v) => v.trim()).map((text, i) => ({ id: `v${i + 1}`, text }));
      setResult(await buildTextTree(payload));
    } catch (runError) {
      setError(messageFrom(runError));
    } finally {
      setBusy(false);
    }
  };

  const renderBranch = (parentId: string | null, depth: number): ReactElement[] =>
    (children.get(parentId) ?? []).map((id) => {
      const node = result!.nodes.find((n) => n.id === id)!;
      const edge = result!.edges.find((e) => e.dst === id) ?? null;
      const precision = node.evidence.confidence.precision;
      return (
        <li key={id} className={`text-node ${selected === id ? "is-selected" : ""}`} style={{ marginLeft: depth * 26 }}>
          <button type="button" onClick={() => setSelected(id)}>
            <span className="text-node-label">{edge ? edge.label : "original"}</span>
            <span className="text-node-id">{id}</span>
            <span className="text-node-preview">{node.text.slice(0, 110)}{node.text.length > 110 ? "…" : ""}</span>
            {precision !== null && !node.root && <span className="confidence">{Math.round(precision * 100)}%</span>}
          </button>
          <ul>{renderBranch(id, depth + 1)}</ul>
        </li>
      );
    });

  const selectedNode = result?.nodes.find((n) => n.id === selected) ?? null;
  const selectedEdge = result?.edges.find((e) => e.dst === selected) ?? null;

  return (
    <main className="landing text-page">
      <NavBar />
      <section className="hero text-hero">
        <p className="eyebrow">Second media type · same core</p>
        <h1>Paragraphs have lineage too.</h1>
        <p className="lede">
          Paste several versions of the same text: the original, a trimmed copy, a reworded copy, a summary. The
          same candidate search, asymmetric cost and arborescence rebuild the family tree, with the image
          plug-ins swapped for text ones: MinHash fingerprints, a word-loss cost, and explanations in words.
        </p>
      </section>

      <section className="text-inputs">
        <div className="text-inputs-head">
          <h2>Versions</h2>
          <div className="text-inputs-actions">
            <button className="secondary-button" type="button" onClick={() => setVersions(EXAMPLE)}>
              Load example
            </button>
            <button className="secondary-button" type="button" onClick={() => setVersions([...versions, ""])}>
              + Add version
            </button>
          </div>
        </div>
        <div className="text-grid">
          {versions.map((value, i) => (
            <label key={i} className="text-version">
              <span>v{i + 1}</span>
              <textarea
                value={value}
                rows={5}
                placeholder="Paste one version of the text…"
                onChange={(event) => {
                  const next = [...versions];
                  next[i] = event.target.value;
                  setVersions(next);
                }}
              />
            </label>
          ))}
        </div>
        {error && <p className="error-banner" role="alert">{error}</p>}
        <button className="primary-button" type="button" disabled={filled < 2 || busy} onClick={() => void run()}>
          {busy ? "Measuring…" : `Build the tree from ${filled} versions`}
        </button>
      </section>

      {result && (
        <section className="text-result">
          <h2>
            {result.summary.families === 1 ? "One family" : `${result.summary.families} families`} ·{" "}
            {result.summary.versions} versions
          </h2>
          <div className="text-result-grid">
            <ul className="text-tree">{renderBranch(null, 0)}</ul>
            <aside className="text-detail">
              {selectedNode ? (
                <>
                  <p className="eyebrow">{selectedNode.root ? "Original" : "Derived version"}</p>
                  <h3>{selectedEdge ? selectedEdge.explain : "root of its family"}</h3>
                  <blockquote>{selectedNode.text}</blockquote>
                  <EvidenceList evidence={selectedNode.evidence} compact />
                </>
              ) : (
                <p className="hint">Select a version to see why it was placed there.</p>
              )}
            </aside>
          </div>
        </section>
      )}
    </main>
  );
}
