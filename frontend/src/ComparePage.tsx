import {
  type ChangeEvent,
  type DragEvent,
  type FormEvent,
  useEffect,
  useState,
} from "react";
import { ApiError, type CompareReportResponse, comparePair } from "./api";
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

/** Ad-hoc pairwise comparison for two local image files. */
export default function ComparePage() {
  usePageTitle("Compare · Lineage");

  const [fileA, setFileA] = useState<File | null>(null);
  const [fileB, setFileB] = useState<File | null>(null);
  const [dragging, setDragging] = useState<FileSlot | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<CompareReportResponse | null>(null);
  const previewA = usePreview(fileA);
  const previewB = usePreview(fileB);

  const chooseFile = (slot: FileSlot, file: File | undefined) => {
    if (!file || loading) return;
    if (!isImage(file)) {
      setError(`${file.name} is not a supported image file.`);
      return;
    }
    if (slot === "A") setFileA(file);
    else setFileB(file);
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
    if (!fileA || !fileB || loading) return;
    const body = new FormData();
    body.append("a", fileA);
    body.append("b", fileB);
    setLoading(true);
    setError(null);
    setReport(null);
    try {
      setReport(await comparePair(body));
    } catch (compareError) {
      setError(messageFrom(compareError));
    } finally {
      setLoading(false);
    }
  };

  const slots = [
    { label: "A" as const, file: fileA, preview: previewA },
    { label: "B" as const, file: fileB, preview: previewB },
  ];

  return (
    <main className="compare-page">
      <NavBar />
      <section className="compare-hero">
        <p className="eyebrow">Pairwise provenance</p>
        <h1>Which image came first?</h1>
        <p>
          Add two files. Lineage aligns and measures them in both directions, then shows the evidence for
          parent and child, siblings, unrelated files, or an inconclusive result.
        </p>
      </section>

      <form className="compare-form" onSubmit={(event) => void handleCompare(event)}>
        <div className="compare-dropzones">
          {slots.map(({ label, file, preview }) => {
            const inputId = `compare-file-${label.toLowerCase()}`;
            const helpId = `${inputId}-help`;
            return (
              <label
                className={`compare-dropzone ${dragging === label ? "is-dragging" : ""} ${file ? "has-file" : ""}`}
                htmlFor={inputId}
                onDragEnter={(event) => { event.preventDefault(); setDragging(label); }}
                onDragOver={(event) => event.preventDefault()}
                onDragLeave={(event) => {
                  if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragging(null);
                }}
                onDrop={(event) => handleDrop(label, event)}
                key={label}
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
                {file && preview ? (
                  <>
                    <img src={preview} alt={`Preview of ${file.name}`} />
                    <strong>{file.name}</strong>
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
            );
          })}
        </div>
        <button className="primary-button compare-submit" type="submit" disabled={!fileA || !fileB || loading}>
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
