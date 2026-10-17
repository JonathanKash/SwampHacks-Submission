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
  identifyImage,
  type IdentifyMatchResponse,
  type IdentifyResponse,
  type TreeNode,
} from "./api";
import CompareReport from "./CompareReport";
import NavBar from "./NavBar";
import { usePageTitle } from "./usePageTitle";

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

  return (
    <article className="identify-family-card">
      <div className="identify-family-overview">
        <figure className="identify-root-image">
          <img src={match.root.url} alt={`${rootFilename}, the documented source for ${family}`} />
          <figcaption>{rootBadge}</figcaption>
        </figure>
        <div className="identify-family-copy">
          <p className="eyebrow">Matched family</p>
          <h2>{family}</h2>
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
            {match.depth_below_root > 0 && <small>{depthLabel}</small>}
          </div>
          <figure>
            <img src={preview} alt={`Your uploaded file, ${filename}`} />
            <figcaption>Your copy</figcaption>
          </figure>
        </div>

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
  const [error, setError] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const [result, setResult] = useState<IdentifyResponse | null>(null);
  const preview = usePreview(file);

  const chooseFile = (nextFile: File | undefined) => {
    if (!nextFile || loading) return;
    if (!isImage(nextFile)) {
      setError(`${nextFile.name} is not a supported image file.`);
      return;
    }
    setFile(nextFile);
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

  const handleIdentify = async (event: FormEvent) => {
    event.preventDefault();
    if (!file || loading) return;
    const body = new FormData();
    body.append("file", file);
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

  return (
    <main className="identify-page">
      <NavBar />
      <section className="compare-hero identify-hero">
        <p className="eyebrow">MEME PROVENANCE</p>
        <h1>Which meme is this, and where did it come from?</h1>
        <p>Upload any copy from your camera roll. Lineage places it in a family of 38 documented meme originals and shows the evidence.</p>
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
            disabled={loading}
            onChange={handleInput}
          />
          {file && preview ? (
            <>
              <img src={preview} alt={`Preview of ${file.name}`} />
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
        <button className="primary-button compare-submit" type="submit" disabled={!file || loading}>
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
          <p>Try the <Link to="/compare">Compare</Link> page for two files, or add this image to a case in <Link to="/audit">Audit</Link>.</p>
        </section>
      )}
    </main>
  );
}
