import {
  type ChangeEvent,
  type DragEvent,
  type FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useSearchParams } from "react-router-dom";
import {
  type AddCaseItemsByUrlResponse,
  ApiError,
  type AuditCase,
  type CompareReportResponse,
  type TreeNode,
  type TreeResponse,
  type WebSearchCaseItemResponse,
  addCaseItemsByUrl,
  compareIds,
  createCase,
  createSampleCase,
  deleteCase,
  deleteCaseItem,
  fetchCases,
  fetchCaseTree,
  htmlReportUrl,
  reportUrl,
  uploadCaseFiles,
  webSearchCaseItem,
} from "./api";
import CompareReport from "./CompareReport";
import ConfidenceChip from "./ConfidenceChip";
import EvidenceList, { reliabilityTier } from "./EvidenceList";
import NavBar from "./NavBar";
import { provenancePath, provenanceSentence } from "./provenance";
import ModeBadge from "./ModeBadge";
import RemoveButton from "./RemoveButton";
import TreeView from "./TreeView";
import { useHealth } from "./useHealth";
import { usePageTitle } from "./usePageTitle";
import VisualDiff from "./VisualDiff";

const CANDIDATE_ORIGINAL_TITLE = "earliest within this case; an earlier version outside it may exist";

const AUDIT_USES = [
  ["Newsroom verification desks", "Separate likely source images from crops, captions, and circulated copies."],
  ["Trust & safety teams", "Trace related visuals and send uncertain parent decisions to human review."],
  ["Legal discovery teams", "Organize image families with a clear, exportable evidence trail."],
  ["Digital asset management teams", "Find likely masters and understand how each derived asset changed."],
] as const;

function messageFrom(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "Something went wrong. Please try again.";
}

function formatPrecision(value: number | null): string {
  if (value === null) return "—";
  const percent = value * 100;
  return `${Number.isInteger(percent) ? percent.toFixed(0) : percent.toFixed(1)}%`;
}

function formatBytes(value: number): string {
  return `${new Intl.NumberFormat().format(value)} bytes`;
}

function truncateUrl(value: string, maxLength = 58): string {
  return value.length > maxLength ? `${value.slice(0, maxLength - 1)}…` : value;
}

function storedAnalyst(): string {
  try {
    return window.localStorage.getItem("lineage.analyst") ?? "";
  } catch {
    // Storage can be blocked in privacy-focused browser modes.
    return "";
  }
}

function isImage(file: File): boolean {
  return file.type.startsWith("image/") || /\.(avif|bmp|gif|heic|heif|jpe?g|png|tiff?|webp)$/i.test(file.name);
}

/** Industry workspace: unknown ground truth, so decisions are presented by empirical precision. */
export default function AuditPage() {
  usePageTitle("Audit · Lineage");
  const health = useHealth();

  const [searchParams, setSearchParams] = useSearchParams();
  const [cases, setCases] = useState<AuditCase[]>([]);
  const [caseName, setCaseName] = useState("");
  const [analyst, setAnalyst] = useState(storedAnalyst);
  const [tree, setTree] = useState<TreeResponse | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [casesLoading, setCasesLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [sampleLoading, setSampleLoading] = useState(false);
  const [sampleError, setSampleError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadCount, setUploadCount] = useState(0);
  const [urlInput, setUrlInput] = useState("");
  const [addingUrls, setAddingUrls] = useState(false);
  const [urlResult, setUrlResult] = useState<AddCaseItemsByUrlResponse | null>(null);
  const [urlError, setUrlError] = useState<string | null>(null);
  const [treeLoading, setTreeLoading] = useState(false);
  const [treeFetching, setTreeFetching] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [treeError, setTreeError] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);
  const [copied, setCopied] = useState(false);
  const [copiedHash, setCopiedHash] = useState(false);
  const [compareWith, setCompareWith] = useState("");
  const [parentReport, setParentReport] = useState<CompareReportResponse | null>(null);
  const [parentReportOpen, setParentReportOpen] = useState(false);
  const [parentReportLoading, setParentReportLoading] = useState(false);
  const [parentReportError, setParentReportError] = useState<string | null>(null);
  const [webSearching, setWebSearching] = useState(false);
  const [webSearchResult, setWebSearchResult] = useState<WebSearchCaseItemResponse | null>(null);
  const [webSearchError, setWebSearchError] = useState<string | null>(null);
  const [verifyVerdict, setVerifyVerdict] = useState<string | null>(null);
  const [originalToast, setOriginalToast] = useState<{ caseId: string; count: number } | null>(null);

  // Re-check a previously downloaded JSON report against the server's hash/signature.
  const handleVerifyReport = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    try {
      const report: unknown = JSON.parse(await file.text());
      const response = await fetch("/api/verify-report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(report),
      });
      const result = (await response.json()) as { verdict?: string };
      setVerifyVerdict(result.verdict ?? "Could not verify this file.");
    } catch {
      setVerifyVerdict("Not a readable Lineage report (expected the downloaded JSON).");
    }
  };

  const copyResetTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const hashCopyResetTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const compareRequestRef = useRef<AbortController | null>(null);
  const urlRequestRef = useRef<AbortController | null>(null);
  const webSearchRequestRef = useRef<AbortController | null>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const returnFocusRef = useRef<SVGGElement | null>(null);
  const takeoverCheckCaseRef = useRef<string | null>(null);
  const selectedCaseId = searchParams.get("case");
  const selectedCaseIdRef = useRef(selectedCaseId);
  selectedCaseIdRef.current = selectedCaseId;

  // A new selection starts without comparison state from the prior image.
  useEffect(() => {
    compareRequestRef.current?.abort();
    webSearchRequestRef.current?.abort();
    setCompareWith("");
    setParentReport(null);
    setParentReportOpen(false);
    setParentReportLoading(false);
    setParentReportError(null);
    setWebSearching(false);
    setWebSearchResult(null);
    setWebSearchError(null);
  }, [selectedNodeId]);

  useEffect(() => {
    urlRequestRef.current?.abort();
    setUrlInput("");
    setAddingUrls(false);
    setUrlResult(null);
    setUrlError(null);
  }, [selectedCaseId]);

  const selectCase = useCallback((id: string | null) => {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      if (id) next.set("case", id);
      else next.delete("case");
      return next;
    }, { replace: true });
  }, [setSearchParams]);

  const loadCases = useCallback(async (signal?: AbortSignal) => {
    const response = await fetchCases(signal);
    setCases(response.cases);
  }, []);

  const refreshCaseData = useCallback(async (caseId: string, signal?: AbortSignal) => {
    const [nextTree] = await Promise.all([
      fetchCaseTree(caseId, undefined, signal),
      loadCases(signal),
    ]);
    if (nextTree && selectedCaseIdRef.current === caseId) setTree(nextTree);
  }, [loadCases]);

  useEffect(() => {
    const controller = new AbortController();
    void loadCases(controller.signal)
      .catch((loadError: unknown) => {
        if (!(loadError instanceof DOMException && loadError.name === "AbortError")) {
          setError(messageFrom(loadError));
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setCasesLoading(false);
      });
    return () => controller.abort();
  }, [loadCases]);

  useEffect(() => () => {
    if (copyResetTimer.current !== null) clearTimeout(copyResetTimer.current);
    if (hashCopyResetTimer.current !== null) clearTimeout(hashCopyResetTimer.current);
    compareRequestRef.current?.abort();
    urlRequestRef.current?.abort();
    webSearchRequestRef.current?.abort();
  }, []);

  useEffect(() => {
    if (!selectedCaseId) {
      setTree(null);
      setTreeLoading(false);
      return;
    }

    const controller = new AbortController();
    let version: number | undefined;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const checkForTakeover = takeoverCheckCaseRef.current === selectedCaseId;
    setTree(null);
    setSelectedNodeId(null);
    setTreeLoading(true);
    setTreeError(null);

    const poll = async () => {
      setTreeFetching(true);
      try {
        const next = await fetchCaseTree(selectedCaseId, version, controller.signal);
        if (next) {
          version = next.version;
          setTree(next);
          if (checkForTakeover && takeoverCheckCaseRef.current === selectedCaseId) {
            takeoverCheckCaseRef.current = null;
            if (next.newest_took_over) {
              const newestNode = next.nodes.find((node) => node.id === next.newest_id);
              setOriginalToast({
                caseId: selectedCaseId,
                count: newestNode?.explains.length ?? 0,
              });
            }
          }
        }
        setTreeError(null);
      } catch (pollError) {
        if (!(pollError instanceof DOMException && pollError.name === "AbortError")) {
          setTreeError(messageFrom(pollError));
        }
      } finally {
        if (!controller.signal.aborted) {
          setTreeFetching(false);
          setTreeLoading(false);
          timer = setTimeout(() => void poll(), 3_000);
        }
      }
    };

    void poll();
    return () => {
      controller.abort();
      if (timer !== undefined) clearTimeout(timer);
    };
  }, [refreshToken, selectedCaseId]);

  useEffect(() => {
    if (selectedNodeId && tree && !tree.nodes.some((node) => node.id === selectedNodeId)) {
      setSelectedNodeId(null);
    }
  }, [selectedNodeId, tree]);

  useEffect(() => {
    if (selectedNodeId) closeButtonRef.current?.focus();
  }, [selectedNodeId]);

  useEffect(() => {
    if (!originalToast) return;
    const timer = window.setTimeout(() => setOriginalToast(null), 8_000);
    return () => window.clearTimeout(timer);
  }, [originalToast]);

  const selectedCase = useMemo(
    () => cases.find((auditCase) => auditCase.id === selectedCaseId) ?? null,
    [cases, selectedCaseId],
  );
  const selectedNode = useMemo(
    () => tree?.nodes.find((node) => node.id === selectedNodeId) ?? null,
    [selectedNodeId, tree],
  );
  const sourceUrl = typeof selectedNode?.params.source_url === "string"
    ? selectedNode.params.source_url
    : null;
  const urlEntries = useMemo(
    () => urlInput.split(/\r?\n/).map((url) => url.trim()).filter(Boolean),
    [urlInput],
  );
  const incomingEdge = useMemo(
    () => tree?.edges.find((edge) => edge.dst === selectedNodeId) ?? null,
    [selectedNodeId, tree],
  );
  const selectedConfidence = incomingEdge?.evidence.confidence ?? null;
  const selectedPrecision = selectedConfidence?.precision ?? null;
  const summary = tree?.summary ?? {
    images: tree?.nodes.length ?? selectedCase?.items ?? 0,
    families: tree?.nodes.filter((node) => node.root).length ?? 0,
    mean_precision: null,
    low_confidence: 0,
  };

  const handleCreate = async (event: FormEvent) => {
    event.preventDefault();
    const name = caseName.trim();
    if (!name || creating || sampleLoading) return;
    setCreating(true);
    setError(null);
    try {
      const created = await createCase(name, analyst.trim());
      setCases((current) => [...current, created]);
      selectCase(created.id);
      setCaseName("");
    } catch (createError) {
      setError(messageFrom(createError));
    } finally {
      setCreating(false);
    }
  };

  const handleCreateSample = async () => {
    if (sampleLoading || creating) return;
    setSampleLoading(true);
    setSampleError(null);
    try {
      const created = await createSampleCase();
      await loadCases();
      selectCase(created.id);
    } catch (sampleCreateError) {
      setSampleError(messageFrom(sampleCreateError));
    } finally {
      setSampleLoading(false);
    }
  };

  const handleDelete = async (auditCase: AuditCase) => {
    if (!window.confirm(`Delete “${auditCase.name}” and all of its uploaded images?`)) return;
    setError(null);
    try {
      await deleteCase(auditCase.id);
      setCases((current) => current.filter((candidate) => candidate.id !== auditCase.id));
      if (selectedCaseId === auditCase.id) selectCase(null);
    } catch (deleteError) {
      setError(messageFrom(deleteError));
    }
  };

  const uploadFiles = async (fileList: FileList | File[]) => {
    if (!selectedCaseId || uploading) return;
    const files = Array.from(fileList).filter(isImage);
    if (files.length === 0) {
      setError("Choose one or more image files.");
      return;
    }

    const caseId = selectedCaseId;
    setUploading(true);
    setUploadCount(files.length);
    setError(null);
    try {
      await uploadCaseFiles(caseId, files);
      takeoverCheckCaseRef.current = caseId;
      // Restarting the poll guarantees a full tree after a long analysis request.
      if (selectedCaseId === caseId) setRefreshToken((value) => value + 1);
      await loadCases();
    } catch (uploadError) {
      setError(messageFrom(uploadError));
    } finally {
      setUploading(false);
      setUploadCount(0);
    }
  };

  const handleFileInput = (event: ChangeEvent<HTMLInputElement>) => {
    const files = event.currentTarget.files;
    if (files) void uploadFiles(files);
    event.currentTarget.value = "";
  };

  const handleDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setDragging(false);
    void uploadFiles(event.dataTransfer.files);
  };

  const handleAddUrls = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedCaseId || addingUrls) return;
    if (urlEntries.length === 0 || urlEntries.length > 40) {
      setUrlError("Enter 1 to 40 URLs, one per line.");
      return;
    }

    const caseId = selectedCaseId;
    const controller = new AbortController();
    urlRequestRef.current?.abort();
    urlRequestRef.current = controller;
    setAddingUrls(true);
    setUrlResult(null);
    setUrlError(null);
    try {
      const result = await addCaseItemsByUrl(caseId, urlEntries, controller.signal);
      if (controller.signal.aborted) return;
      setUrlResult(result);
      setUrlInput(result.failed.map((failure) => failure.url).join("\n"));
      await refreshCaseData(caseId, controller.signal);
    } catch (addError) {
      if (!(addError instanceof DOMException && addError.name === "AbortError")) {
        setUrlError(messageFrom(addError));
      }
    } finally {
      if (!controller.signal.aborted) setAddingUrls(false);
    }
  };

  const selectNode = useCallback((node: TreeNode, target: SVGGElement) => {
    returnFocusRef.current = target;
    setSelectedNodeId(node.id);
  }, []);

  const closeDetails = useCallback(() => {
    setSelectedNodeId(null);
    window.requestAnimationFrame(() => returnFocusRef.current?.focus());
  }, []);

  const handleAnalystChange = (value: string) => {
    setAnalyst(value);
    try {
      window.localStorage.setItem("lineage.analyst", value);
    } catch {
      // The form still works when storage is unavailable.
    }
  };

  const handleCopyLink = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      if (copyResetTimer.current !== null) clearTimeout(copyResetTimer.current);
      copyResetTimer.current = setTimeout(() => setCopied(false), 1_500);
    } catch (copyError) {
      setError(messageFrom(copyError));
    }
  };

  const handleCopyHash = async (hash: string) => {
    try {
      await navigator.clipboard.writeText(hash);
      setCopiedHash(true);
      if (hashCopyResetTimer.current !== null) clearTimeout(hashCopyResetTimer.current);
      hashCopyResetTimer.current = setTimeout(() => setCopiedHash(false), 1_500);
    } catch (copyError) {
      setError(messageFrom(copyError));
    }
  };

  const handleCompareParent = async () => {
    if (!selectedNode?.predicted_parent || !selectedCaseId || parentReportLoading) return;
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
      const next = await compareIds(
        selectedNode.predicted_parent,
        selectedNode.id,
        selectedCaseId,
        controller.signal,
      );
      if (!controller.signal.aborted) {
        setParentReport(next);
        setParentReportOpen(true);
      }
    } catch (compareError) {
      if (!(compareError instanceof DOMException && compareError.name === "AbortError")) {
        setParentReportError(messageFrom(compareError));
      }
    } finally {
      if (!controller.signal.aborted) setParentReportLoading(false);
    }
  };

  const handleWebSearch = async () => {
    if (!selectedCaseId || !selectedNode || webSearching || !health?.web_search) return;

    const caseId = selectedCaseId;
    const itemId = selectedNode.id;
    const controller = new AbortController();
    webSearchRequestRef.current?.abort();
    webSearchRequestRef.current = controller;
    setWebSearching(true);
    setWebSearchResult(null);
    setWebSearchError(null);
    try {
      const result = await webSearchCaseItem(caseId, itemId, controller.signal);
      if (controller.signal.aborted) return;
      setWebSearchResult(result);
      await refreshCaseData(caseId, controller.signal);
    } catch (searchError) {
      if (!(searchError instanceof DOMException && searchError.name === "AbortError")) {
        // ApiError preserves the server's 503 detail for actionable setup guidance.
        setWebSearchError(messageFrom(searchError));
      }
    } finally {
      if (!controller.signal.aborted) setWebSearching(false);
    }
  };

  return (
    <main className="audit-page">
      <div className="audit-screen">
        <NavBar />
        <div className="audit-workspace">
          <aside className="audit-sidebar" aria-label="Audit cases">
            <div className="audit-sidebar-heading">
              <p className="eyebrow">Provenance audit</p>
              <h1>Cases</h1>
            </div>
            <form className="audit-new-case" onSubmit={handleCreate}>
              <label htmlFor="audit-case-name">New case</label>
              <div className="audit-new-case-fields">
                <input
                  id="audit-case-name"
                  value={caseName}
                  onChange={(event) => setCaseName(event.target.value)}
                  placeholder="Case name"
                  maxLength={100}
                />
                <input
                  id="audit-case-analyst"
                  value={analyst}
                  onChange={(event) => handleAnalystChange(event.target.value)}
                  placeholder="Analyst (optional)"
                  aria-label="Analyst (optional)"
                  maxLength={80}
                />
                <button
                  className="primary-button"
                  type="submit"
                  disabled={!caseName.trim() || creating || sampleLoading}
                >
                  {creating ? <span className="spinner" aria-label="Creating case" /> : "Add"}
                </button>
              </div>
            </form>
            {!selectedCase && (
              <div>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => void handleCreateSample()}
                  disabled={sampleLoading || creating}
                >
                  {sampleLoading ? (
                    <>
                      <span className="spinner" aria-hidden="true" />
                      Loading sample…
                    </>
                  ) : (
                    "Load a sample case"
                  )}
                </button>
                {sampleError && <p className="error-banner" role="alert">{sampleError}</p>}
              </div>
            )}

            <div className="audit-case-list">
              {casesLoading && <p className="audit-list-status">Loading cases…</p>}
              {!casesLoading && cases.length === 0 && (
                <p className="audit-list-status">No cases yet. Create one to begin.</p>
              )}
              {cases.map((auditCase) => (
                <div
                  className={`audit-case-row ${selectedCaseId === auditCase.id ? "is-selected" : ""}`}
                  key={auditCase.id}
                >
                  <button type="button" className="audit-case-select" onClick={() => selectCase(auditCase.id)}>
                    <strong>{auditCase.name}</strong>
                    {auditCase.analyst && <span>Analyst · {auditCase.analyst}</span>}
                    <span>{auditCase.items} {auditCase.items === 1 ? "image" : "images"}</span>
                  </button>
                  <button
                    type="button"
                    className="audit-case-delete"
                    onClick={() => void handleDelete(auditCase)}
                    title="Delete case"
                  >
                    <span aria-hidden="true">×</span>
                    <span className="sr-only">Delete {auditCase.name}</span>
                  </button>
                </div>
              ))}
            </div>
            {error && <p className="error-banner audit-error" role="alert">{error}</p>}
          </aside>

          {!selectedCase ? (
            <section className="audit-welcome">
              <p className="eyebrow">Unknown ground truth</p>
              <h2>Turn a folder of image variants into an explainable family tree.</h2>
              <p>
                An audit identifies the candidate original, describes what changed in every copy, and shows how
                sure the system is from calibrated empirical precision. There is no accuracy counter because
                the real lineage is not known in advance.
              </p>
              <div className="audit-how-to-read">
                <h3>How to read a lineage tree</h3>
                <p>
                  Each image sits under the image it was most cheaply derived from, using pixel measurements only.{' '}
                  <span title={CANDIDATE_ORIGINAL_TITLE}>'Candidate original'</span> means nothing in the case explains
                  it more cheaply than calling it an original; an earlier version outside this case may exist. Precision
                  figures come from an evaluation on synthetic edit chains with known truth. Treat low-margin decisions
                  as leads to verify, not conclusions.
                </p>
              </div>
              <div className="audit-use-grid">
                {AUDIT_USES.map(([title, description]) => (
                  <article key={title}>
                    <h3>{title}</h3>
                    <p>{description}</p>
                  </article>
                ))}
              </div>
            </section>
          ) : (
            <section className="audit-case-main">
              <header className="audit-case-header">
                <div>
                  <p className="eyebrow">Active case <ModeBadge /></p>
                  <h2>{selectedCase.name}</h2>
                  {selectedCase.analyst && <p className="audit-case-analyst">Analyst · {selectedCase.analyst}</p>}
                  {verifyVerdict && (
                    <p className="verify-verdict" role="status">
                      Report check: <strong>{verifyVerdict}</strong>
                    </p>
                  )}
                </div>
                <div className="audit-actions">
                  <a className="secondary-button" href={reportUrl(selectedCase.id)} download>
                    Download report (JSON)
                  </a>
                  <a
                    className="secondary-button"
                    href={htmlReportUrl(selectedCase.id)}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Open HTML report
                  </a>
                  <a className="secondary-button" href={`/api/cases/${encodeURIComponent(selectedCase.id)}/report.csv`} download>
                    CSV ledger
                  </a>
                  <button className="secondary-button" type="button" onClick={() => void handleCopyLink()}>
                    {copied ? "Copied" : "Copy link"}
                  </button>
                  <label className="secondary-button verify-report">
                    Verify a report
                    <input type="file" accept="application/json,.json" className="sr-only" onChange={(event) => void handleVerifyReport(event)} />
                  </label>
                  <button className="secondary-button" type="button" onClick={() => window.print()}>
                    Print summary
                  </button>
                </div>
              </header>

              <dl
                className="audit-summary"
                aria-label="Case summary"
                aria-live="polite"
                aria-atomic="true"
              >
                <div><dt>images</dt><dd>{summary.images}</dd></div>
                <div><dt>families</dt><dd>{summary.families}</dd></div>
                <div><dt>mean empirical precision</dt><dd>{formatPrecision(summary.mean_precision)}</dd></div>
                <div><dt>low-reliability decisions (&lt; 80%)</dt><dd>{summary.low_confidence}</dd></div>
                <span
                  className={`poll-dot ${treeFetching ? "is-fetching" : ""} ${treeError ? "has-error" : ""}`}
                  title={treeError ?? "Checking for changes every 3 seconds"}
                  aria-label={treeError ? "Audit updates retrying" : "Audit updates active"}
                />
              </dl>

              <div className="audit-ingest">
                <label
                  className={`audit-dropzone ${dragging ? "is-dragging" : ""} ${uploading ? "is-uploading" : ""}`}
                  htmlFor="audit-files"
                  onDragEnter={(event) => { event.preventDefault(); setDragging(true); }}
                  onDragOver={(event) => event.preventDefault()}
                  onDragLeave={(event) => {
                    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragging(false);
                  }}
                  onDrop={handleDrop}
                >
                  <input
                    id="audit-files"
                    className="sr-only"
                    type="file"
                    accept="image/*"
                    multiple
                    disabled={uploading}
                    onChange={handleFileInput}
                  />
                  {uploading ? (
                    <>
                      <span className="spinner large" aria-hidden="true" />
                      <strong>Analysing {uploadCount} {uploadCount === 1 ? "image" : "images"}…</strong>
                      <span>Reconstructing likely parents and calibrating each decision.</span>
                    </>
                  ) : (
                    <>
                      <span className="audit-upload-mark" aria-hidden="true">＋</span>
                      <strong>Drop image versions here, or click to choose</strong>
                      <span>Upload multiple images together. Originals and copies can be mixed.</span>
                    </>
                  )}
                </label>
                <details className="audit-url-import">
                  <summary>Add from URLs</summary>
                  <form onSubmit={(event) => void handleAddUrls(event)}>
                    <label htmlFor="audit-urls">One image URL per line</label>
                    <textarea
                      id="audit-urls"
                      value={urlInput}
                      rows={4}
                      placeholder={"https://example.com/image-one.jpg\nhttps://example.com/image-two.png"}
                      aria-describedby="audit-url-limit"
                      disabled={addingUrls}
                      onChange={(event) => {
                        setUrlInput(event.target.value);
                        setUrlResult(null);
                        setUrlError(null);
                      }}
                    />
                    <div className="audit-url-actions">
                      <small id="audit-url-limit" className={urlEntries.length > 40 ? "has-error" : ""}>
                        {urlEntries.length} / 40 URLs
                      </small>
                      <button
                        className="secondary-button"
                        type="submit"
                        disabled={addingUrls || urlEntries.length === 0 || urlEntries.length > 40}
                      >
                        {addingUrls ? (
                          <>
                            <span className="spinner" aria-hidden="true" />
                            Fetching…
                          </>
                        ) : (
                          "Fetch and add"
                        )}
                      </button>
                    </div>
                  </form>
                  {urlResult && (
                    <div className="url-import-result" role="status" aria-live="polite">
                      <p>Added {urlResult.items.length} · failed {urlResult.failed.length}</p>
                      {urlResult.failed.length > 0 && (
                        <details className="url-failures">
                          <summary>Failed URLs</summary>
                          <ul>
                            {urlResult.failed.map((failure, index) => (
                              <li key={`${failure.url}-${index}`}>
                                <code title={failure.url}>{truncateUrl(failure.url)}</code>
                                <span>{failure.error}</span>
                              </li>
                            ))}
                          </ul>
                        </details>
                      )}
                    </div>
                  )}
                  {urlError && <p className="compare-inline-error" role="alert">{urlError}</p>}
                </details>
              </div>

              <div className={`audit-tree-area ${selectedNode ? "has-panel" : ""}`}>
                {treeLoading && !tree && (
                  <div className="tree-empty">
                    <span className="spinner large" aria-hidden="true" />
                    <p>Loading this audit…</p>
                  </div>
                )}
                {!treeLoading && tree && tree.nodes.length === 0 && (
                  <div className="tree-empty">
                    <span className="waiting-orbit" aria-hidden="true" />
                    <p>No images in this case yet.</p>
                    <small>Use the drop zone above to add the versions you need to audit.</small>
                  </div>
                )}
                {!treeLoading && !tree && (
                  <div className="tree-empty">
                    <p>Could not load this audit.</p>
                    {treeError && <small>{treeError}</small>}
                  </div>
                )}
                {tree && tree.nodes.length > 0 && (
                  <>
                    <TreeView
                      data={tree}
                      selectedId={selectedNodeId}
                      onSelect={selectNode}
                      colorBy="confidence"
                      rootLabel="Candidate original"
                      rootTitle={CANDIDATE_ORIGINAL_TITLE}
                    />
                    <div className="legend audit-legend" aria-label="Audit confidence legend">
                      <span className="legend-item"><i className="swatch sure" /> 85%+ precision</span>
                      <span className="legend-item"><i className="swatch unsure" /> review</span>
                      <span className="legend-item"><i className="swatch dashed" /> matched by meaning</span>
                      <span className="legend-item"><i className="swatch new" /> newest</span>
                    </div>
                  </>
                )}

                {selectedNode && (
                  <aside className="node-panel audit-node-panel" aria-label="Image audit details">
                    <button
                      className="panel-close"
                      type="button"
                      ref={closeButtonRef}
                      onClick={closeDetails}
                      aria-label="Close details"
                    >
                      ×
                    </button>
                    <p className="eyebrow" title={selectedNode.root ? CANDIDATE_ORIGINAL_TITLE : undefined}>
                      {selectedNode.root ? "Candidate original" : "Derived copy"}
                    </p>
                    <h2>{incomingEdge?.label ?? "root of its family"}</h2>
                    <img src={selectedNode.url} alt={`Full-size audit image ${selectedNode.id}`} />
                    {sourceUrl && (
                      <p className="node-source">
                        Source:{" "}
                        <a href={sourceUrl} title={sourceUrl} target="_blank" rel="noopener noreferrer">
                          {truncateUrl(sourceUrl)}
                        </a>
                      </p>
                    )}
                    <div className="web-search-control">
                      {health?.web_search ? (
                        <button
                          className="secondary-button"
                          type="button"
                          disabled={webSearching}
                          onClick={() => void handleWebSearch()}
                        >
                          {webSearching ? (
                            <>
                              <span className="spinner" aria-hidden="true" />
                              Finding copies…
                            </>
                          ) : (
                            "Find copies on the web"
                          )}
                        </button>
                      ) : (
                        <p className="web-search-unavailable">
                          Web search needs a provider key on the server (SERPAPI_KEY + PUBLIC_URL)
                        </p>
                      )}
                      {webSearchResult && (
                        <div className="url-import-result" role="status" aria-live="polite">
                          <p>
                            Found {webSearchResult.candidates} · added {webSearchResult.items.length} · failed{" "}
                            {webSearchResult.failed.length}
                          </p>
                          {webSearchResult.failed.length > 0 && (
                            <details className="url-failures">
                              <summary>Failed web copies</summary>
                              <ul>
                                {webSearchResult.failed.map((failure, index) => (
                                  <li key={`${failure.url}-${index}`}>
                                    <code title={failure.url}>{truncateUrl(failure.url)}</code>
                                    <span>{failure.error}</span>
                                  </li>
                                ))}
                              </ul>
                            </details>
                          )}
                        </div>
                      )}
                      {webSearchError && (
                        <p className="compare-inline-error" role="alert">{webSearchError}</p>
                      )}
                    </div>
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
                    <div className={incomingEdge ? "edge-details" : "root-details"}>
                      <div className="detail-heading">
                        <span>Lineage's reading</span>
                        {selectedConfidence && selectedPrecision !== null && (
                          <ConfidenceChip
                            confidence={selectedConfidence}
                            className="audit-precision"
                            legacy={(
                              <>
                                <strong>{formatPrecision(selectedPrecision)} precision</strong>
                                <small>{reliabilityTier(selectedPrecision)}</small>
                              </>
                            )}
                          />
                        )}
                      </div>
                      <p>
                        {incomingEdge
                          ? `Derived from ${incomingEdge.src}: ${incomingEdge.explain}`
                          : "No uploaded image explains this one more cheaply, so it is treated as a candidate original."}
                      </p>
                      <EvidenceList evidence={incomingEdge?.evidence ?? selectedNode.evidence} compact />
                    </div>
                    {!selectedNode.root && tree && (
                      <VisualDiff
                        key={`${selectedNode.id}-${tree.version}`}
                        src={`/api/cases/${encodeURIComponent(selectedCase.id)}/diff/${encodeURIComponent(selectedNode.id)}?t=${tree.version}`}
                      />
                    )}
                    {selectedNode.predicted_parent && (
                      <div className="compare-parent-control">
                        <button
                          className="primary-button"
                          type="button"
                          aria-expanded={parentReport ? parentReportOpen : undefined}
                          aria-controls="audit-parent-compare-report"
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
                          <div id="audit-parent-compare-report">
                            <CompareReport report={parentReport} />
                          </div>
                        )}
                      </div>
                    )}
                    {tree && tree.nodes.length > 1 && (
                      <div className="compare-with">
                        <label htmlFor="compare-with-select">Compare with any image</label>
                        <select
                          id="compare-with-select"
                          value={compareWith}
                          onChange={(event) => setCompareWith(event.target.value)}
                        >
                          <option value="">Choose an image…</option>
                          {tree.nodes
                            .filter((node) => node.id !== selectedNode.id)
                            .map((node) => (
                              <option key={node.id} value={node.id}>
                                {String(node.params.filename ?? node.id)}
                              </option>
                            ))}
                        </select>
                        {compareWith && (
                          <VisualDiff
                            key={`${selectedNode.id}-vs-${compareWith}-${tree.version}`}
                            src={`/api/cases/${encodeURIComponent(selectedCase.id)}/diff/${encodeURIComponent(selectedNode.id)}?other=${encodeURIComponent(compareWith)}&t=${tree.version}`}
                            defaultShown
                            showLabel="Show comparison"
                            hideLabel="Hide comparison"
                            caption="chosen image aligned onto this one · this image · residual after color fit"
                            unavailableMessage="These two images do not align; they are not direct pixel relatives."
                          />
                        )}
                      </div>
                    )}
                    {tree && !selectedNode.root && (
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
                        <p className="provenance-sentence">{provenanceSentence(provenancePath(tree, selectedNode.id))}</p>
                      </div>
                    )}
                    <div className="metadata-hints">
                      <h3>Metadata hints <small>(unverified, easily stripped)</small></h3>
                      {selectedNode.metadata?.has_exif ? (
                        <dl>
                          {selectedNode.metadata.software && <><dt>Software</dt><dd>{selectedNode.metadata.software}</dd></>}
                          {selectedNode.metadata.datetime && <><dt>Date/time</dt><dd>{selectedNode.metadata.datetime}</dd></>}
                          {selectedNode.metadata.camera && <><dt>Camera</dt><dd>{selectedNode.metadata.camera}</dd></>}
                          {!selectedNode.metadata.software &&
                            !selectedNode.metadata.datetime &&
                            !selectedNode.metadata.camera && <><dt>EXIF</dt><dd>Present, with no supported hints.</dd></>}
                        </dl>
                      ) : (
                        <p>no EXIF</p>
                      )}
                    </div>
                    {selectedNode.footprint && (
                      <div className="footprint">
                        <h3>Footprint</h3>
                        <dl>
                          <dt>Dimensions</dt>
                          <dd>{selectedNode.footprint.width} × {selectedNode.footprint.height}px</dd>
                          <dt>Bytes</dt>
                          <dd>{formatBytes(selectedNode.footprint.bytes)}</dd>
                          <dt>pHash</dt>
                          <dd>{selectedNode.footprint.phash}</dd>
                          <dt>SHA-256</dt>
                          <dd className="footprint-hash">
                            <span title={selectedNode.footprint.sha256}>
                              {selectedNode.footprint.sha256.slice(0, 16)}…
                            </span>
                            <button
                              type="button"
                              onClick={() => void handleCopyHash(selectedNode.footprint?.sha256 ?? "")}
                              aria-label="Copy full SHA-256 hash"
                            >
                              {copiedHash ? "copied" : "copy"}
                            </button>
                          </dd>
                        </dl>
                      </div>
                    )}
                    <small className="node-id-small">id {selectedNode.id}</small>
                    <RemoveButton
                      remove={(token) => deleteCaseItem(selectedCase.id, selectedNode.id, token)}
                      onRemoved={() => {
                        setSelectedNodeId(null);
                        setRefreshToken((value) => value + 1);
                      }}
                    />
                  </aside>
                )}
                {treeError && tree && <div className="tree-error-toast">Audit update retrying · {treeError}</div>}
                {originalToast?.caseId === selectedCaseId && (
                  <div
                    className="original-recognised-toast"
                    role="status"
                    aria-live="polite"
                    aria-atomic="true"
                    onClick={() => setOriginalToast(null)}
                  >
                    <span>
                      New candidate original recognised: it explains {originalToast.count} existing{" "}
                      {originalToast.count === 1 ? "version" : "versions"}.
                    </span>
                    <button type="button" onClick={() => setOriginalToast(null)} aria-label="Dismiss notification">
                      ×
                    </button>
                  </div>
                )}
              </div>
            </section>
          )}
        </div>
      </div>

      {selectedCase && tree && (
        <section className="audit-print-report">
          <header>
            <p>Lineage provenance audit</p>
            <h1>{selectedCase.name}</h1>
            {selectedCase.analyst && <p className="audit-print-analyst">Analyst · {selectedCase.analyst}</p>}
            <dl>
              <div><dt>Images</dt><dd>{summary.images}</dd></div>
              <div><dt>Families</dt><dd>{summary.families}</dd></div>
              <div><dt>Mean empirical precision</dt><dd>{formatPrecision(summary.mean_precision)}</dd></div>
              <div><dt>Low-reliability decisions (&lt; 80%)</dt><dd>{summary.low_confidence}</dd></div>
            </dl>
          </header>
          <div className="audit-print-list">
            {tree.nodes.map((node) => {
              const edge = tree.edges.find((candidate) => candidate.dst === node.id) ?? null;
              const evidence = edge?.evidence ?? node.evidence;
              return (
                <article key={node.id}>
                  <img src={node.thumb} alt="" />
                  <div>
                    <h2>{node.id}</h2>
                    <p>
                      <strong>Parent:</strong>{' '}
                      {node.predicted_parent ?? <span title={CANDIDATE_ORIGINAL_TITLE}>candidate original</span>}
                    </p>
                    <p>
                      {edge
                        ? `Derived from ${edge.src}: ${edge.explain}`
                        : "Treated as a candidate original because no uploaded image explains it more cheaply."}
                    </p>
                    <ul>
                      {evidence.reasons.map((reason) => <li key={reason}>{reason}</li>)}
                    </ul>
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      )}
    </main>
  );
}
