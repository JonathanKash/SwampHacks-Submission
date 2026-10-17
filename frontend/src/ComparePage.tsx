import {
  type ChangeEvent,
  type DragEvent,
  type FormEvent,
  useEffect,
  useState,
} from "react";
import {
  ApiError,
  type CompareReportResponse,
  type PoolItem,
  compareIds,
  comparePair,
  fetchPool,
} from "./api";
import CompareReport from "./CompareReport";
import NavBar from "./NavBar";
import { usePageTitle } from "./usePageTitle";

type FileSlot = "A" | "B";

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

function poolItemName(item: PoolItem): string {
  const filename = item.params.filename;
  return typeof filename === "string" && filename.trim() ? filename : item.id.slice(0, 8);
}

/** Ad-hoc pairwise comparison for two local image files. */
export default function ComparePage() {
  usePageTitle("Compare · Lineage");

  const [fileA, setFileA] = useState<File | null>(null);
  const [fileB, setFileB] = useState<File | null>(null);
  const [poolA, setPoolA] = useState<PoolItem | null>(null);
  const [poolB, setPoolB] = useState<PoolItem | null>(null);
  const [poolItems, setPoolItems] = useState<PoolItem[]>([]);
  const [poolLoading, setPoolLoading] = useState(true);
  const [poolError, setPoolError] = useState<string | null>(null);
  const [dragging, setDragging] = useState<FileSlot | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<CompareReportResponse | null>(null);
  const previewA = usePreview(fileA);
  const previewB = usePreview(fileB);

  useEffect(() => {
    const controller = new AbortController();
    void fetchPool(controller.signal)
      .then(({ items }) => setPoolItems(items))
      .catch((poolFetchError: unknown) => {
        if (!controller.signal.aborted) setPoolError(messageFrom(poolFetchError));
      })
      .finally(() => {
        if (!controller.signal.aborted) setPoolLoading(false);
      });
    return () => controller.abort();
  }, []);

  const chooseFile = (slot: FileSlot, file: File | undefined) => {
    if (!file || loading) return;
    if (!isImage(file)) {
      setError(`${file.name} is not a supported image file.`);
      return;
    }
    if (slot === "A") {
      setFileA(file);
      setPoolA(null);
    } else {
      setFileB(file);
      setPoolB(null);
    }
    setReport(null);
    setError(null);
  };

  const choosePoolItem = (slot: FileSlot, event: ChangeEvent<HTMLSelectElement>) => {
    if (loading) return;
    const item = poolItems.find(({ id }) => id === event.currentTarget.value) ?? null;
    if (slot === "A") {
      setPoolA(item);
      if (item) setFileA(null);
    } else {
      setPoolB(item);
      if (item) setFileB(null);
    }
    setReport(null);
    setError(null);
  };

  const swapSelections = () => {
    if (loading) return;
    setFileA(fileB);
    setFileB(fileA);
    setPoolA(poolB);
    setPoolB(poolA);
    setReport(null);
    setError(null);
  };

  const handleInput = (slot: FileSlot, event: ChangeEvent<HTMLInputElement>) => {
    chooseFile(slot, event.currentTarget.files?.[0]);
    event.currentTarget.value = "";
  };

  const handleDrop = (slot: FileSlot, event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setDragging(null);
    chooseFile(slot, event.dataTransfer.files[0]);
  };

  const handleCompare = async (event: FormEvent) => {
    event.preventDefault();
    if (loading || (!fileA || !fileB) && (!poolA || !poolB)) return;
    setLoading(true);
    setError(null);
    setReport(null);
    try {
      if (poolA && poolB) {
        setReport(await compareIds(poolA.id, poolB.id));
      } else if (fileA && fileB) {
        const body = new FormData();
        body.append("a", fileA);
        body.append("b", fileB);
        setReport(await comparePair(body));
      }
    } catch (compareError) {
      setError(messageFrom(compareError));
    } finally {
      setLoading(false);
    }
  };

  const slots = [
    { label: "A" as const, file: fileA, poolItem: poolA, preview: previewA },
    { label: "B" as const, file: fileB, poolItem: poolB, preview: previewB },
  ];
  const hasMixedSources = Boolean((fileA && poolB) || (poolA && fileB));
  const canCompare = Boolean((fileA && fileB) || (poolA && poolB));

  return (
    <main className="compare-page">
      <NavBar />
      <section className="compare-hero">
        <p className="eyebrow">Pairwise provenance</p>
        <h1>Which image came first?</h1>
        <p>
          Add two files. Lineage aligns and measures them in both directions, then shows the evidence for
          parent and child, siblings, unrelated files, a re-rendered copy, or an inconclusive result.
        </p>
      </section>

      <form className="compare-form" onSubmit={(event) => void handleCompare(event)}>
        <div
          className="compare-dropzones"
          style={{ position: "relative", columnGap: "clamp(72px, 10vw, 132px)", rowGap: 72 }}
        >
          {slots.map(({ label, file, poolItem, preview }) => {
            const inputId = `compare-file-${label.toLowerCase()}`;
            const helpId = `${inputId}-help`;
            const selectId = `compare-pool-${label.toLowerCase()}`;
            const displayName = file?.name ?? (poolItem ? poolItemName(poolItem) : null);
            const displayPreview = preview ?? poolItem?.thumb ?? poolItem?.url ?? null;
            return (
              <div key={label}>
                <label
                  className={`compare-dropzone ${dragging === label ? "is-dragging" : ""} ${displayName ? "has-file" : ""}`}
                  htmlFor={inputId}
                  onDragEnter={(event) => { event.preventDefault(); setDragging(label); }}
                  onDragOver={(event) => event.preventDefault()}
                  onDragLeave={(event) => {
                    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragging(null);
                  }}
                  onDrop={(event) => handleDrop(label, event)}
                >
                  <input
                    className="sr-only"
                    id={inputId}
                    type="file"
                    accept="image/*"
                    aria-describedby={helpId}
                    disabled={loading}
                    onChange={(event) => handleInput(label, event)}
                  />
                  <span className="compare-slot-label">{label}</span>
                  {displayName && displayPreview ? (
                    <>
                      <img src={displayPreview} alt={`Preview of ${displayName}`} />
                      <strong>{displayName}</strong>
                      <span id={helpId}>Click or drop to replace</span>
                    </>
                  ) : (
                    <>
                      <span className="compare-upload-mark" aria-hidden="true">＋</span>
                      <strong>Choose or drop one image</strong>
                      <span id={helpId}>One local image file</span>
                    </>
                  )}
                </label>
                <div className="compare-with">
                  <label htmlFor={selectId}>or pick from the demo pool</label>
                  <select
                    id={selectId}
                    value={poolItem?.id ?? ""}
                    disabled={loading || poolLoading || poolItems.length === 0}
                    onChange={(event) => choosePoolItem(label, event)}
                  >
                    <option value="">{poolLoading ? "Loading demo pool…" : "Choose a pool item"}</option>
                    {poolItems.map((item) => (
                      <option value={item.id} key={item.id}>{poolItemName(item)}</option>
                    ))}
                  </select>
                </div>
              </div>
            );
          })}
          <button
            className="secondary-button"
            type="button"
            disabled={loading || (!fileA && !fileB && !poolA && !poolB)}
            style={{ position: "absolute", top: "50%", left: "50%", zIndex: 1, transform: "translate(-50%, -50%)" }}
            onClick={swapSelections}
          >
            Swap A and B
          </button>
        </div>
        {hasMixedSources && (
          <p className="compare-inline-error compare-error" role="note">
            Mixing a file and a pool item is not supported yet; pick two pool items or two files
          </p>
        )}
        {poolError && <p className="compare-inline-error compare-error" role="alert">{poolError}</p>}
        <button className="primary-button compare-submit" type="submit" disabled={!canCompare || loading}>
          {loading ? (
            <>
              <span className="spinner" aria-hidden="true" />
              <span role="status">Aligning and measuring…</span>
            </>
          ) : (
            "Compare"
          )}
        </button>
        {error && <p className="error-banner compare-error" role="alert">{error}</p>}
      </form>

      {report && <CompareReport report={report} />}
    </main>
  );
}
