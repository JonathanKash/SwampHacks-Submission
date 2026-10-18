import { type ReactElement, useMemo, useState } from "react";
import { ApiError, type TextTreeResponse, buildTextTree } from "./api";
import EvidenceList from "./EvidenceList";
import NavBar from "./NavBar";
import { tokenDiff } from "./textDiff";
import { usePageTitle } from "./usePageTitle";

const ORIGINAL_EXAMPLE = "A photograph begins its journey across the web when a visitor uploads it to a small community website after a local event. The site stores the image, creates a smaller preview, and places that preview beside a descriptive caption. A reader downloads the file and shares it in a public forum, where other people repost it with new filenames of their own. Search engines index those public copies while social platforms compress the image and remove its metadata. Eventually, the scene appears across blogs and forums, often without a link to its upload.";

const EXAMPLE = [
  ORIGINAL_EXAMPLE,
  "A photograph begins its journey across the web when a visitor uploads it to a small community website after a local event. The site stores the image, creates a smaller preview, and places that preview beside a descriptive caption. A reader downloads the file and shares it in a public forum, where other people repost it with new filenames of their own.",
  "A photograph begins its path across the web when a visitor posts it to a modest community website after a local event. The site saves the image, creates a reduced preview, and places that preview beside a descriptive caption. A reader retrieves the file and circulates it in a public forum, where other people repost it with fresh filenames of their own. Search engines index those public copies while social platforms shrink the image and remove its metadata. Eventually, the scene surfaces across blogs and forums, often without a connection to its upload.",
  `${ORIGINAL_EXAMPLE} Each new host leaves another record of where the photograph has traveled.`,
];

function messageFrom(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "Something went wrong. Please try again.";
}

function words(text: string): string[] {
  return text.trim().split(/\s+/).filter(Boolean);
}

/** Second media type, same core: paste versions of a paragraph, get the edit tree. */
export default function TextPage() {
  usePageTitle("Text · Lineage");

  const [versions, setVersions] = useState<string[]>(["", ""]);
  const [result, setResult] = useState<TextTreeResponse | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [showDiff, setShowDiff] = useState(false);
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
          <button
            type="button"
            onClick={() => {
              setSelected(id);
              setShowDiff(false);
            }}
          >
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
  const parentNode = result?.nodes.find((node) => node.id === selectedNode?.predicted_parent) ?? null;
  const diff = selectedNode && parentNode ? tokenDiff(words(parentNode.text), words(selectedNode.text)) : [];
  const removed = diff.filter((part) => part.kind === "removed").length;
  const added = diff.filter((part) => part.kind === "added").length;

  return (
    <main className="landing text-page">
      <NavBar />
      <section className="hero text-hero">
        <p className="eyebrow">Not just images</p>
        <h1>Paragraphs have lineage too.</h1>
        <p className="lede">
          Paste several versions of the same text: the original, a trimmed copy, a reworded copy, a summary. The
          same candidate search, asymmetric cost and arborescence rebuild the family tree, with the image
          plug-ins swapped for text ones: MinHash fingerprints, a word-loss cost, and explanations in words.
        </p>
        <p className="hint">
          One honest caveat: deleting words is cheap and inventing them is expensive, so the most complete
          version is treated as the original. An expanded copy will sit above the text it was expanded from.
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
          {result.note && <p className="hint">{result.note}</p>}
          <div className="text-result-grid">
            <div>
              <ul className="text-tree">{renderBranch(null, 0)}</ul>
              {result.edges.some((edge) => edge.explain) && (
                <div aria-label="Edge readings">
                  {result.edges.filter((edge) => edge.explain).map((edge) => (
                    <p className="hint" key={`${edge.src}-${edge.dst}`}>
                      {edge.src} → {edge.dst} · {edge.label}: {edge.explain}
                    </p>
                  ))}
                </div>
              )}
              <p className="hint">
                Legend: -sentence = trimmed / reworded = reworded / +sentence = extended
              </p>
              <p className="hint">
                Text mode shows the same core on paragraphs. No precision figure is shown here because calibration exists only for images.
              </p>
            </div>
            <aside className="text-detail">
              {selectedNode ? (
                <>
                  <p className="eyebrow">{selectedNode.root ? "Original" : "Derived version"}</p>
                  <h3>{selectedEdge ? selectedEdge.explain : "root of its family"}</h3>
                  <blockquote>{selectedNode.text}</blockquote>
                  {parentNode && (
                    <div className="text-diff-block">
                      <button
                        className="secondary-button text-diff-toggle"
                        type="button"
                        aria-pressed={showDiff}
                        onClick={() => setShowDiff((visible) => !visible)}
                      >
                        {showDiff ? "Hide word diff" : "Show word diff"}
                      </button>
                      {showDiff && (
                        <div className="text-word-diff">
                          <p className="sr-only">
                            struck-through = removed from the source, highlighted = added in this version
                          </p>
                          <p>
                            {diff.map((part, index) => {
                              const text = `${index === 0 ? "" : " "}${part.text}`;
                              if (part.kind === "removed") {
                                return <del className="tok-removed" key={`${part.kind}-${index}`}>{text}</del>;
                              }
                              if (part.kind === "added") {
                                return <ins className="tok-added" key={`${part.kind}-${index}`}>{text}</ins>;
                              }
                              return <span key={`${part.kind}-${index}`}>{text}</span>;
                            })}
                          </p>
                          <small>{removed} words removed · {added} words added</small>
                        </div>
                      )}
                    </div>
                  )}
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
