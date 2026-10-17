import {
  type ChangeEvent,
  type DragEvent,
  type FormEvent,
  useEffect,
  useId,
  useState,
} from "react";
import { Link } from "react-router-dom";
import {
  ApiError,
  fetchIdentifyStats,
  identifyImage,
  type IdentifyMatchResponse,
  type IdentifyResponse,
  type IdentifyStatsResponse,
  type TreeNode,
} from "./api";
import CompareReport from "./CompareReport";
import NavBar from "./NavBar";
import { usePageTitle } from "./usePageTitle";

type CaseSummary = {
  id: string;
  name: string;
  items: number;
};

type SampleNode = {
  id: string;
  url: string;
  params: Record<string, unknown>;
};

function messageFrom(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "Something went wrong. Please try again.";
}

function isImage(file: File): boolean {
  return file.type.startsWith("image/") || /\.(avif|bmp|gif|heic|heif|jpe?g|png|tiff?|webp)$/i.test(file.name);
}

function usePreview(file: File | null): string | null {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!file) {
      setUrl(null);
      return;
    }
    const next = URL.createObjectURL(file);
    setUrl(next);
    return () => URL.revokeObjectURL(next);
  }, [file]);

  return url;
}

function stringParam(node: TreeNode, key: string): string | null {
  const value = node.params[key];
  return typeof value === "string" && value.trim() ? value : null;
}

function booleanParam(node: TreeNode, key: string): boolean | null {
  const value = node.params[key];
  return typeof value === "boolean" ? value : null;
}

function MatchedFamily({ match, preview, filename }: {
  match: IdentifyMatchResponse;
  preview: string;
  filename: string;
}) {
  const [showWhy, setShowWhy] = useState(false);
  const reportId = useId();
  const family = stringParam(match.root, "family") ?? "Meme family";
  const rootFilename = stringParam(match.root, "filename") ?? family;
  const rootDate = stringParam(match.root, "date");
  const sourceNote = stringParam(match.root, "source_note");
  const sourceUrl = stringParam(match.root, "source_url");
  const kymUrl = stringParam(match.root, "kym_url");
  const parentRole = stringParam(match.parent, "role") ?? "matched parent";
  const trueSourcePhoto = booleanParam(match.root, "is_true_source_photo");
  const rootBadge = trueSourcePhoto === false ? "Earliest template on record" : "Documented original";
  const depthLabel = `${match.depth_below_root} ${match.depth_below_root === 1 ? "step" : "steps"} below the original`;
  const matchedStoredCopy = parentRole.startsWith("variant");
  const treeRootFamily = match.tree_root ? stringParam(match.tree_root, "family") : null;

  return (
    <article className="identify-family-card">
      <div className="identify-family-overview">
        <figure className="identify-root-image">
          <img src={match.root.url} alt={`${rootFilename}, the documented source for ${family}`} />
          <figcaption>{rootBadge}</figcaption>
        </figure>
        <div className="identify-family-copy">
          <p className="eyebrow">Matched family</p>
          <div className="identify-family-heading">
            <h2>{family}</h2>
            <span
              className="identify-match-strength"
              title="1 - cost / threshold; 100% means a near-identical copy exists in the knowledge base"
            >
              Match strength {Math.round(match.match_strength * 100)}%
            </span>
          </div>
          <section className="identify-provenance" aria-label="Original image provenance">
            <h3>Provenance</h3>
            {rootDate && (
              <dl>
                <div>
                  <dt>Date</dt>
                  <dd>{rootDate}</dd>
                </div>
              </dl>
            )}
            {sourceNote && <p>{sourceNote}</p>}
            {(sourceUrl || kymUrl) && (
              <div className="identify-source-links">
                {sourceUrl && <a href={sourceUrl} target="_blank" rel="noopener">Source</a>}
                {kymUrl && <a href={kymUrl} target="_blank" rel="noopener">Know Your Meme</a>}
              </div>
            )}
          </section>
        </div>
      </div>

      <section className="identify-copy-section">
        <p className="eyebrow">Your copy</p>
        <div className="identify-copy-row">
          <figure>
            <img src={match.parent.thumb || match.parent.url} alt={`Matched parent: ${parentRole}`} />
            <figcaption>{parentRole}</figcaption>
          </figure>
          <div className="identify-relation">
            <span aria-hidden="true">→</span>
            <strong>derived from {parentRole} via {match.edit}</strong>
            {matchedStoredCopy && <small>(matched a stored copy, not the original itself)</small>}
            {match.depth_below_root > 0 && <small>{depthLabel}</small>}
          </div>
          <figure>
            <img src={preview} alt={`Your uploaded file, ${filename}`} />
            <figcaption>Your copy</figcaption>
          </figure>
        </div>

        {match.tree_disagrees && (
          <aside className="identify-tree-note">
            {match.tree_root && (
              <img
                src={match.tree_root.thumb || match.tree_root.url}
                alt={`Reconstructed tree root for ${treeRootFamily ?? "a different family"}`}
              />
            )}
            <p>
              Note: the reconstructed tree inside the knowledge base had linked this copy to a different family
              ({treeRootFamily ?? "unknown family"}); the family label of the matched item is used here.
            </p>
          </aside>
        )}

        {match.would_be_better_parent && (
          <aside className="identify-parent-callout">
            Your file explains the stored copy better than its current parent. It may be closer to the original:
            consider adding it to the case.
          </aside>
        )}

        <div className="identify-why">
          <button
            className="secondary-button"
            type="button"
            aria-expanded={showWhy}
            aria-controls={reportId}
            onClick={() => setShowWhy((open) => !open)}
          >
            {showWhy ? "Hide why" : "Why?"}
          </button>
          {showWhy && (
            <div id={reportId}>
              <p className="identify-report-key"><strong>A</strong> = matched parent · <strong>B</strong> = your copy</p>
              <CompareReport report={match.report} />
            </div>
          )}
        </div>
      </section>
    </article>
  );
}

/** Place one local image into the documented meme-family knowledge base. */
export default function IdentifyPage() {
  usePageTitle("Identify · Lineage");

  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [sampleLoading, setSampleLoading] = useState(false);
  const [isSample, setIsSample] = useState(false);
  const [sampleError, setSampleError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const [result, setResult] = useState<IdentifyResponse | null>(null);
  const [stats, setStats] = useState<IdentifyStatsResponse | null>(null);
  const preview = usePreview(file);
  const busy = loading || sampleLoading;

  useEffect(() => {
    const controller = new AbortController();
    void fetchIdentifyStats(controller.signal).then(setStats).catch(() => {});
    return () => controller.abort();
  }, []);

  const chooseFile = (nextFile: File | undefined) => {
    if (!nextFile || busy) return;
    if (!isImage(nextFile)) {
      setError(`${nextFile.name} is not a supported image file.`);
      return;
    }
    setFile(nextFile);
    setIsSample(false);
    setSampleError(null);
    setResult(null);
    setUnavailable(false);
    setError(null);
  };

  const handleInput = (event: ChangeEvent<HTMLInputElement>) => {
    chooseFile(event.currentTarget.files?.[0]);
    event.currentTarget.value = "";
  };

  const handleDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setDragging(false);
    chooseFile(event.dataTransfer.files[0]);
  };

  const identify = async (nextFile: File) => {
    const body = new FormData();
    body.append("file", nextFile);
    setFile(nextFile);
    setLoading(true);
    setError(null);
    setUnavailable(false);
    setResult(null);
    try {
      setResult(await identifyImage(body));
    } catch (identifyError) {
      if (identifyError instanceof ApiError && identifyError.status === 503) {
        setUnavailable(true);
      } else {
        setError(messageFrom(identifyError));
      }
    } finally {
      setLoading(false);
    }
  };

  const handleIdentify = async (event: FormEvent) => {
    event.preventDefault();
    if (!file || busy) return;
    await identify(file);
  };

  const handleSample = async () => {
    if (busy) return;
    setSampleLoading(true);
    setSampleError(null);
    setError(null);
    try {
      const casesResponse = await fetch("/api/cases");
      if (!casesResponse.ok) throw new Error("Could not load cases");
      const { cases } = await casesResponse.json() as { cases: CaseSummary[] };
      const memeCases = cases.filter((entry) => entry.name.includes("Meme"));
      const sampleCase = memeCases.reduce<CaseSummary | null>(
        (largest, entry) => !largest || entry.items > largest.items ? entry : largest,
        null,
      );
      if (!sampleCase) throw new Error("No meme case found");

      const treeResponse = await fetch(`/api/cases/${sampleCase.id}/tree`);
      if (!treeResponse.ok) throw new Error("Could not load sample tree");
      const { nodes } = await treeResponse.json() as { nodes: SampleNode[] };
      const variants = nodes.filter((node) => (
        typeof node.params.role === "string" && node.params.role.startsWith("variant")
      ));
      if (!variants.length) throw new Error("No sample variant found");

      const node = variants[Math.floor(Math.random() * variants.length)];
      const imageResponse = await fetch(node.url);
      if (!imageResponse.ok) throw new Error("Could not download sample image");
      const filename = node.params.filename;
      if (typeof filename !== "string" || !filename.trim()) throw new Error("Sample has no filename");
      const blob = await imageResponse.blob();
      const sampleFile = new File([blob], filename, { type: blob.type });
      setIsSample(true);
      setSampleLoading(false);
      await identify(sampleFile);
    } catch {
      setSampleError("Couldn’t load a sample. Please try again.");
    } finally {
      setSampleLoading(false);
    }
  };

  return (
    <main className="identify-page">
      <NavBar />
      <section className="compare-hero identify-hero">
        <p className="eyebrow">MEME PROVENANCE</p>
        <h1>Which meme is this, and where did it come from?</h1>
        <p>Upload any copy from your camera roll. Lineage places it in a family of 38 documented meme originals and shows the evidence.</p>
        {stats?.available && (
          <p
            className="identify-trust-note"
            title={`Knowledge base: ${stats.knowledge_base ?? "unknown"} · Generated: ${stats.generated_at ?? "unknown"}`}
          >
            On {stats.queries} held-out meme copies this feature named the right family {Math.round((stats.family_accuracy ?? 0) * 100)}% of the time, abstained {Math.round(((stats.abstained ?? 0) / (stats.queries || 1)) * 100)}% of the time, and named a wrong family {stats.wrong_family} times.
          </p>
        )}
      </section>

      <form className="compare-form identify-form" onSubmit={(event) => void handleIdentify(event)}>
        <label
          className={`compare-dropzone identify-dropzone ${dragging ? "is-dragging" : ""} ${file ? "has-file" : ""}`}
          htmlFor="identify-file"
          onDragEnter={(event) => { event.preventDefault(); setDragging(true); }}
          onDragOver={(event) => event.preventDefault()}
          onDragLeave={(event) => {
            if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragging(false);
          }}
          onDrop={handleDrop}
        >
          <input
            className="sr-only"
            id="identify-file"
            type="file"
            accept="image/*"
            aria-describedby="identify-file-help"
            disabled={busy}
            onChange={handleInput}
          />
          {file && preview ? (
            <>
              <img src={preview} alt={`Preview of ${file.name}`} />
              {isSample && (
                <small className="identify-sample-caption">
                  Sample from the knowledge base (a stored copy), so expect a near-identical match. Upload your own for a real test.
                </small>
              )}
              <strong>{file.name}</strong>
              <span id="identify-file-help">Click or drop to replace</span>
            </>
          ) : (
            <>
              <span className="compare-upload-mark" aria-hidden="true">＋</span>
              <strong>Choose or drop one image</strong>
              <span id="identify-file-help">One local image file</span>
            </>
          )}
        </label>
        <button
          className="identify-sample-button"
          type="button"
          disabled={busy}
          onClick={() => void handleSample()}
        >
          {sampleLoading ? "Loading sample…" : "Try a sample instead"}
        </button>
        {sampleError && <p className="compare-inline-error" role="alert">{sampleError}</p>}
        <button className="primary-button compare-submit" type="submit" disabled={!file || busy}>
          {loading ? (
            <>
              <span className="spinner" aria-hidden="true" />
              <span role="status">Placing in the family tree…</span>
            </>
          ) : (
            "Identify"
          )}
        </button>
        {error && <p className="error-banner compare-error" role="alert">{error}</p>}
      </form>

      {unavailable && (
        <section className="identify-empty" role="status">
          <h2>The meme knowledge base is not built on this server yet.</h2>
          <p>Build it with <code>python backend/scripts/build_meme_case.py</code></p>
        </section>
      )}

      {result?.matched && preview && file && (
        <MatchedFamily match={result} preview={preview} filename={file.name} />
      )}

      {result && !result.matched && (
        <section className="identify-empty" role="status">
          <h2>No family matched.</h2>
          <p>{result.reason}</p>
          {stats?.available && stats.wrong_family === 0 && (
            <p>Abstaining is deliberate: on the benchmark this feature never named a wrong family.</p>
          )}
          <p>Try the <Link to="/compare">Compare</Link> page for two files, or add this image to a case in <Link to="/audit">Audit</Link>.</p>
        </section>
      )}
    </main>
  );
}
