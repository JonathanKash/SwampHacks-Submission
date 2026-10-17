import { type ComponentType, type FormEvent, type SVGProps, useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  ApiError,
  type EditKind,
  type EditParams,
  type FilterKind,
  type PoolItem,
  type RestyleKind,
  type Evidence,
  type TreeEdge,
  fetchRandom,
  fetchTree,
  submitEdit,
} from "./api";
import EvidenceList from "./EvidenceList";
import { CaptionIcon, CropIcon, FilterIcon, JpegIcon, RestyleIcon, RotateIcon } from "./icons";
import NavBar from "./NavBar";
import { usePageTitle } from "./usePageTitle";
import VisualDiff from "./VisualDiff";

const CAPTIONS = [
  "me irl",
  "no context",
  "art history final boss",
  "when the deadline is 8am",
  "Gators",
  "this is fine",
  "SwampHacks XII",
  "mood",
  "vibes",
  "certified classic",
] as const;

const FILTERS: Array<{ id: FilterKind; label: string; hint: string }> = [
  { id: "warm", label: "Warm", hint: "more red, less blue" },
  { id: "cool", label: "Cool", hint: "more blue, less red" },
  { id: "brighter", label: "Brighter", hint: "lift everything" },
  { id: "darker", label: "Darker", hint: "dim everything" },
  { id: "contrast", label: "Contrast", hint: "punchier tones" },
  { id: "grayscale", label: "Grayscale", hint: "drop all color" },
];

const STYLES: RestyleKind[] = [
  "watercolor",
  "pencil sketch",
  "oil painting",
  "pop art",
  "pixel art",
  "stained glass",
  "neon",
  "claymation",
];

const EDITS: Array<{
  id: EditKind;
  title: string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
  description: string;
  detects: string;
}> = [
  { id: "crop", title: "Crop", icon: CropIcon, description: "Keep a random 45–85% slice.", detects: "uncovered area" },
  { id: "rotate", title: "Rotate", icon: RotateIcon, description: "Tilt by a few degrees.", detects: "the homography angle" },
  { id: "filter", title: "Color filter", icon: FilterIcon, description: "Shift color or tone.", detects: "the color fit" },
  { id: "caption", title: "Caption", icon: CaptionIcon, description: "Bold text across the bottom.", detects: "an added blob" },
  { id: "jpeg", title: "Crunchy JPEG", icon: JpegIcon, description: "Re-save at very low quality.", detects: "8×8 block energy" },
  { id: "restyle", title: "AI restyle", icon: RestyleIcon, description: "Re-render in a new art style.", detects: "meaning, via CLIP" },
];

interface Verdict {
  correct: boolean | null;
  edge: TreeEdge | null;
  predicted: PoolItem | null;
  evidence: Evidence | null;
}

function randomCaption(): string {
  return CAPTIONS[Math.floor(Math.random() * CAPTIONS.length)];
}

function titleCase(value: string): string {
  return value.replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function messageFrom(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "Something went wrong. Please try again.";
}

function showDiffByDefault(): boolean {
  return typeof window !== "undefined" && window.innerWidth >= 900;
}

/** Tablet page: pick an image, apply exactly one edit, then see whether Lineage traced it back. */
export default function EditPage() {
  usePageTitle("Make an edit · Lineage");

  const [parent, setParent] = useState<PoolItem | null>(null);
  const [result, setResult] = useState<PoolItem | null>(null);
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [selected, setSelected] = useState<EditKind | null>(null);
  const [filter, setFilter] = useState<FilterKind | null>(null);
  const [style, setStyle] = useState<RestyleKind | null>(null);
  const [caption, setCaption] = useState(randomCaption);
  const [loadingImage, setLoadingImage] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadRandom = useCallback(async (signal?: AbortSignal) => {
    setLoadingImage(true);
    setError(null);
    try {
      setParent(await fetchRandom(signal));
    } catch (loadError) {
      if (!(loadError instanceof DOMException && loadError.name === "AbortError")) {
        setParent(null);
        setError(messageFrom(loadError));
      }
    } finally {
      if (!signal?.aborted) setLoadingImage(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void loadRandom(controller.signal);
    return () => controller.abort();
  }, [loadRandom]);

  const chooseEdit = (edit: EditKind) => {
    setError(null);
    setSelected(edit);
    if (edit !== "filter") setFilter(null);
    if (edit !== "restyle") setStyle(null);
  };

  const params = useMemo<EditParams>(() => {
    if (selected === "filter" && filter) return { kind: filter };
    if (selected === "caption") return { text: caption.trim() };
    if (selected === "restyle" && style) return { style };
    return {};
  }, [caption, filter, selected, style]);

  const needsChoice = (selected === "filter" && !filter) || (selected === "restyle" && !style);
  const canSubmit =
    Boolean(parent && selected) && !needsChoice && (selected !== "caption" || Boolean(caption.trim()));

  const summary = useMemo(() => {
    if (!selected) return "Pick one edit below.";
    if (selected === "filter") return filter ? `Apply the ${filter} filter.` : "Which filter?";
    if (selected === "restyle") return style ? `Re-render as ${style}.` : "Which style?";
    if (selected === "caption") return `Add “${caption.trim() || "your caption"}”.`;
    return EDITS.find((edit) => edit.id === selected)?.description ?? "";
  }, [caption, filter, selected, style]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!parent || !selected || !canSubmit || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const created = await submitEdit({ parent_id: parent.id, edit: selected, params });
      setResult(created);
      // The tree is rebuilt synchronously on upload, so one fetch tells us the verdict.
      const tree = await fetchTree();
      const node = tree?.nodes.find((candidate) => candidate.id === created.id) ?? null;
      const edge = tree?.edges.find((candidate) => candidate.dst === created.id) ?? null;
      const predicted = tree?.nodes.find((candidate) => candidate.id === node?.predicted_parent) ?? null;
      setVerdict({ correct: node ? node.correct : null, edge, predicted, evidence: node?.evidence ?? null });
    } catch (submitError) {
      setError(messageFrom(submitError));
    } finally {
      setSubmitting(false);
    }
  };

  const doAnother = () => {
    setResult(null);
    setVerdict(null);
    setSelected(null);
    setFilter(null);
    setStyle(null);
    setCaption(randomCaption());
    void loadRandom();
  };

  if (result && parent) {
    const guessedRight = verdict?.correct === true;
    const fooled = verdict?.correct === false;
    return (
      <main className="edit-page">
        <NavBar />
        <section className="verdict" aria-live="polite">
          <p className="eyebrow">Step 3 · the verdict</p>
          <h1 className={guessedRight ? "verdict-ok" : fooled ? "verdict-bad" : ""}>
            {guessedRight && "Lineage traced your edit back to the right parent."}
            {fooled && "The measurements pointed to a different parent."}
            {verdict?.correct === null && "Added to the pool."}
            {!verdict && "Added to the pool. Checking the tree…"}
          </h1>
          <div className="before-after">
            <figure>
              <img src={parent.url} alt="The image you started from" />
              <figcaption>you started from</figcaption>
            </figure>
            <span className="before-after-arrow" aria-hidden="true">→</span>
            <figure>
              <img src={result.url} alt="Your edited image" />
              <figcaption>your edit</figcaption>
            </figure>
            {fooled && verdict?.predicted && (
              <>
                <span className="before-after-arrow" aria-hidden="true">?</span>
                <figure className="is-wrong">
                  <img src={verdict.predicted.url} alt="The parent Lineage guessed instead" />
                  <figcaption>parent the measurements selected</figcaption>
                </figure>
              </>
            )}
          </div>
          {verdict?.edge && (
            <p className="verdict-explain">
              It read the edit as <strong>“{verdict.edge.explain}”</strong>
              {verdict.edge.semantic ? " and had to match by meaning, because the pixels no longer align." : "."}
            </p>
          )}
          <VisualDiff
            src={`/api/diff/${result.id}`}
            caption={
              verdict?.predicted && verdict.predicted.id !== parent.id
                ? "source Lineage selected, aligned onto your edit"
                : "source aligned · your edit · pixel difference"
            }
            defaultShown={showDiffByDefault()}
            showLabel="Show the evidence picture"
            hideLabel="Hide the evidence picture"
            unavailableMessage="No pixel alignment to show for this edit."
          />
          {verdict?.evidence && <EvidenceList evidence={verdict.evidence} />}
          <div className="verdict-actions">
            <button className="primary-button" type="button" onClick={doAnother}>
              Do another
            </button>
            <Link to="/tree" className="secondary-button">
              See it on the tree
            </Link>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="edit-page">
      <NavBar />
      <ol className="steps" aria-label="Progress">
        <li className="is-done">1 · Your image</li>
        <li className={selected ? "is-done" : "is-current"}>2 · One edit</li>
        <li className={canSubmit ? "is-current" : ""}>3 · Verdict + evidence</li>
      </ol>

      <form className="edit-workspace" onSubmit={handleSubmit}>
        <section className="source-panel" aria-label="Your image">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Step 1</p>
              <h2>Your image</h2>
            </div>
            <button
              className="secondary-button another-button"
              type="button"
              onClick={() => void loadRandom()}
              disabled={loadingImage || submitting}
            >
              ↻ Different image
            </button>
          </div>
          <div className={`source-image ${loadingImage ? "is-loading" : ""}`}>
            {parent && <img src={parent.url} alt="Random image from the Lineage pool" />}
            {loadingImage && <span className="spinner large" aria-label="Loading image" />}
            {!loadingImage && !parent && <p>The pool is empty right now.</p>}
          </div>
          <p className="hint">
            Picked at random from the pool. It may already be someone else's edit; that is fine, trees have
            branches.
          </p>
        </section>

        <section className="controls-panel" aria-label="Choose one edit">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Step 2</p>
              <h2>Apply one edit</h2>
            </div>
            <span className="step-badge">just one</span>
          </div>

          <div className="edit-grid">
            {EDITS.map((edit) => {
              const Icon = edit.icon;
              return (
                <button
                  className={`edit-choice ${selected === edit.id ? "is-selected" : ""}`}
                  type="button"
                  key={edit.id}
                  onClick={() => chooseEdit(edit.id)}
                  aria-pressed={selected === edit.id}
                >
                  <span className="edit-icon" aria-hidden="true"><Icon /></span>
                  <span>{edit.title}</span>
                  <small>{edit.description}</small>
                </button>
              );
            })}
          </div>

          {selected === "filter" && (
            <div className="option-panel">
              <p>Which filter?</p>
              <div className="chip-grid">
                {FILTERS.map((kind) => (
                  <button
                    className={`choice-chip ${filter === kind.id ? "is-selected" : ""}`}
                    type="button"
                    key={kind.id}
                    onClick={() => setFilter(kind.id)}
                  >
                    {kind.label}
                    <small>{kind.hint}</small>
                  </button>
                ))}
              </div>
            </div>
          )}

          {selected === "caption" && (
            <div className="option-panel caption-options">
              <label htmlFor="caption-text">Your caption</label>
              <input
                id="caption-text"
                value={caption}
                onChange={(event) => setCaption(event.target.value)}
                maxLength={80}
                autoFocus
              />
              <div className="quick-picks" aria-label="Quick caption picks">
                {CAPTIONS.slice(0, 5).map((text) => (
                  <button className="choice-chip" type="button" key={text} onClick={() => setCaption(text)}>
                    {text}
                  </button>
                ))}
              </div>
            </div>
          )}

          {selected === "restyle" && (
            <div className="option-panel">
              <p>Which style?</p>
              <div className="chip-grid styles-grid">
                {STYLES.map((kind) => (
                  <button
                    className={`choice-chip ${style === kind ? "is-selected" : ""}`}
                    type="button"
                    key={kind}
                    onClick={() => setStyle(kind)}
                  >
                    {titleCase(kind)}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="submit-row">
            <p className="selection-description">
              {summary}
              {selected && (
                <small> Lineage will look for {EDITS.find((edit) => edit.id === selected)?.detects}.</small>
              )}
            </p>
            {error && <p className="error-banner" role="alert">{error}</p>}
            <button className="primary-button submit-button" type="submit" disabled={!canSubmit || submitting}>
              {submitting ? (
                <>
                  <span className="spinner" aria-hidden="true" />
                  {selected === "restyle" ? "Restyling… 10–20 seconds" : "Adding to the pool…"}
                </>
              ) : (
                "Submit my edit →"
              )}
            </button>
          </div>
        </section>
      </form>
    </main>
  );
}
