import {
  Fragment,
  type ChangeEvent,
  type DragEvent,
  type FormEvent,
  useEffect,
  useRef,
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

type ResizeNotice = {
  originalWidth: number;
  originalHeight: number;
  resizedWidth: number;
  resizedHeight: number;
};

const MAX_UPLOAD_BYTES = 4 * 1024 * 1024;
const MAX_SOURCE_SIDE = 2000;
const MAX_UPLOAD_SIDE = 1600;

function messageFrom(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "Something went wrong. Please try again.";
}

function isImage(file: File): boolean {
  return file.type.startsWith("image/") || /\.(avif|bmp|gif|heic|heif|jpe?g|png|tiff?|webp)$/i.test(file.name);
}

function loadImage(file: File): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    const url = URL.createObjectURL(file);
    image.onload = () => {
      URL.revokeObjectURL(url);
      resolve(image);
    };
    image.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("The image could not be decoded in this browser."));
    };
    image.src = url;
  });
}

function canvasBlob(canvas: HTMLCanvasElement, type: string): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => blob ? resolve(blob) : reject(new Error("The resized image could not be encoded.")),
      type,
      type === "image/jpeg" ? 0.9 : undefined,
    );
  });
}

async function prepareUpload(file: File): Promise<{ file: File; resize: ResizeNotice | null }> {
  const image = await loadImage(file);
  const originalWidth = image.naturalWidth;
  const originalHeight = image.naturalHeight;
  const longestSide = Math.max(originalWidth, originalHeight);

  if (file.size <= MAX_UPLOAD_BYTES && longestSide <= MAX_SOURCE_SIDE) {
    return { file, resize: null };
  }

  const scale = Math.min(1, MAX_UPLOAD_SIDE / longestSide);
  const resizedWidth = Math.max(1, Math.round(originalWidth * scale));
  const resizedHeight = Math.max(1, Math.round(originalHeight * scale));
  const canvas = document.createElement("canvas");
  canvas.width = resizedWidth;
  canvas.height = resizedHeight;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("Canvas resizing is not available in this browser.");
  context.drawImage(image, 0, 0, resizedWidth, resizedHeight);

  const isSmallPng = file.size <= MAX_UPLOAD_BYTES
    && (file.type.toLowerCase() === "image/png" || /\.png$/i.test(file.name));
  const type = isSmallPng ? "image/png" : "image/jpeg";
  const blob = await canvasBlob(canvas, type);
  return {
    file: new File([blob], file.name, { type, lastModified: file.lastModified }),
    resize: { originalWidth, originalHeight, resizedWidth, resizedHeight },
  };
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
  const [resizeA, setResizeA] = useState<ResizeNotice | null>(null);
  const [resizeB, setResizeB] = useState<ResizeNotice | null>(null);
  const [poolA, setPoolA] = useState<PoolItem | null>(null);
  const [poolB, setPoolB] = useState<PoolItem | null>(null);
  const [poolItems, setPoolItems] = useState<PoolItem[]>([]);
  const [poolLoading, setPoolLoading] = useState(true);
  const [poolError, setPoolError] = useState<string | null>(null);
  const [dragging, setDragging] = useState<FileSlot | null>(null);
  const [loading, setLoading] = useState(false);
  const [preparing, setPreparing] = useState<Record<FileSlot, boolean>>({ A: false, B: false });
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<CompareReportResponse | null>(null);
  const fileChoiceVersion = useRef<Record<FileSlot, number>>({ A: 0, B: 0 });
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

  const chooseFile = async (slot: FileSlot, file: File | undefined) => {
    if (!file || loading) return;
    if (!isImage(file)) {
      setError(`${file.name} is not a supported image file.`);
      return;
    }
    const version = ++fileChoiceVersion.current[slot];
    setPreparing((current) => ({ ...current, [slot]: true }));
    setReport(null);
    setError(null);
    try {
      const prepared = await prepareUpload(file);
      if (fileChoiceVersion.current[slot] !== version) return;
      if (slot === "A") {
        setFileA(prepared.file);
        setResizeA(prepared.resize);
        setPoolA(null);
      } else {
        setFileB(prepared.file);
        setResizeB(prepared.resize);
        setPoolB(null);
      }
    } catch (prepareError) {
      if (fileChoiceVersion.current[slot] === version) setError(messageFrom(prepareError));
    } finally {
      if (fileChoiceVersion.current[slot] === version) {
        setPreparing((current) => ({ ...current, [slot]: false }));
      }
    }
  };

  const choosePoolItem = (slot: FileSlot, event: ChangeEvent<HTMLSelectElement>) => {
    if (loading) return;
    const item = poolItems.find(({ id }) => id === event.currentTarget.value) ?? null;
    fileChoiceVersion.current[slot] += 1;
    setPreparing((current) => ({ ...current, [slot]: false }));
    if (slot === "A") {
      setPoolA(item);
      if (item) {
        setFileA(null);
        setResizeA(null);
      }
    } else {
      setPoolB(item);
      if (item) {
        setFileB(null);
        setResizeB(null);
      }
    }
    setReport(null);
    setError(null);
  };

  const swapSelections = () => {
    if (loading || preparing.A || preparing.B) return;
    setFileA(fileB);
    setFileB(fileA);
    setResizeA(resizeB);
    setResizeB(resizeA);
    setPoolA(poolB);
    setPoolB(poolA);
    setReport(null);
    setError(null);
  };

  const handleInput = (slot: FileSlot, event: ChangeEvent<HTMLInputElement>) => {
    void chooseFile(slot, event.currentTarget.files?.[0]);
    event.currentTarget.value = "";
  };

  const handleDrop = (slot: FileSlot, event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setDragging(null);
    void chooseFile(slot, event.dataTransfer.files[0]);
  };

  const handleCompare = async (event: FormEvent) => {
    event.preventDefault();
    if (loading || preparing.A || preparing.B || (!fileA || !fileB) && (!poolA || !poolB)) return;
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
    { label: "A" as const, file: fileA, poolItem: poolA, preview: previewA, resize: resizeA },
    { label: "B" as const, file: fileB, poolItem: poolB, preview: previewB, resize: resizeB },
  ];
  const hasMixedSources = Boolean((fileA && poolB) || (poolA && fileB));
  const canCompare = !preparing.A && !preparing.B && Boolean((fileA && fileB) || (poolA && poolB));
  const bothSidesEmpty = !fileA && !fileB && !poolA && !poolB;

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
        <div className="compare-dropzones">
          {slots.map(({ label, file, poolItem, preview, resize }) => {
            const inputId = `compare-file-${label.toLowerCase()}`;
            const helpId = `${inputId}-help`;
            const selectId = `compare-pool-${label.toLowerCase()}`;
            const displayName = file?.name ?? (poolItem ? poolItemName(poolItem) : null);
            const displayPreview = preview ?? poolItem?.thumb ?? poolItem?.url ?? null;
            return (
              <Fragment key={label}>
                {label === "B" && (
                  <div className="compare-swap-column">
                    <button
                      className="compare-swap-button"
                      type="button"
                      disabled={loading || preparing.A || preparing.B || bothSidesEmpty}
                      onClick={swapSelections}
                    >
                      <span aria-hidden="true">⇄</span>
                      <span className="sr-only">Swap A and B</span>
                    </button>
                    <span>Swap</span>
                  </div>
                )}
                <div className="compare-slot">
                  <label
                    className={`compare-dropzone ${dragging === label ? "is-dragging" : ""} ${displayName ? "has-file" : ""} ${loading ? "is-disabled" : ""}`}
                    htmlFor={inputId}
                    aria-disabled={loading}
                    onDragEnter={(event) => {
                      event.preventDefault();
                      if (!loading) setDragging(label);
                    }}
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
                  {resize && (
                    <p
                      style={{ color: "var(--muted)", fontSize: "0.82rem", margin: "10px 0 0" }}
                      title="The SHA-256 in the report is calculated from the resized file."
                    >
                      Resized for upload: {resize.originalWidth}×{resize.originalHeight} →{" "}
                      {resize.resizedWidth}×{resize.resizedHeight}
                    </p>
                  )}
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
              </Fragment>
            );
          })}
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
        {bothSidesEmpty && (
          <p className="compare-submit-note">No files handy? Pick two items from the demo pool above.</p>
        )}
        {loading && (
          <p className="compare-submit-note" role="status">
            Usually 3 to 10 seconds; large phone photos are resized first.
          </p>
        )}
        {error && <p className="error-banner compare-error" role="alert">{error}</p>}
      </form>

      {report && <CompareReport report={report} />}
    </main>
  );
}
