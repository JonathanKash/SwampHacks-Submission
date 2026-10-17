import {
  type ChangeEvent,
  type DragEvent,
  type FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  ApiError,
  type AuditCase,
  type TreeNode,
  type TreeResponse,
  createCase,
  deleteCase,
  fetchCases,
  fetchCaseTree,
  reportUrl,
  uploadCaseFiles,
} from "./api";
import EvidenceList from "./EvidenceList";
import NavBar from "./NavBar";
import TreeView from "./TreeView";

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

function isImage(file: File): boolean {
  return file.type.startsWith("image/") || /\.(avif|bmp|gif|heic|heif|jpe?g|png|tiff?|webp)$/i.test(file.name);
}

/** Industry workspace: unknown ground truth, so decisions are presented by empirical precision. */
export default function AuditPage() {
  const [cases, setCases] = useState<AuditCase[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [caseName, setCaseName] = useState("");
  const [tree, setTree] = useState<TreeResponse | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [casesLoading, setCasesLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadCount, setUploadCount] = useState(0);
  const [treeLoading, setTreeLoading] = useState(false);
  const [treeFetching, setTreeFetching] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [treeError, setTreeError] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);

  const loadCases = useCallback(async (signal?: AbortSignal) => {
    const response = await fetchCases(signal);
    setCases(response.cases);
  }, []);

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

  useEffect(() => {
    if (!selectedCaseId) {
      setTree(null);
      setTreeLoading(false);
      return;
    }

    const controller = new AbortController();
    let version: number | undefined;
    let timer: ReturnType<typeof setTimeout> | undefined;
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

  const selectedCase = useMemo(
    () => cases.find((auditCase) => auditCase.id === selectedCaseId) ?? null,
    [cases, selectedCaseId],
  );
  const selectedNode = useMemo(
    () => tree?.nodes.find((node) => node.id === selectedNodeId) ?? null,
    [selectedNodeId, tree],
  );
  const incomingEdge = useMemo(
    () => tree?.edges.find((edge) => edge.dst === selectedNodeId) ?? null,
    [selectedNodeId, tree],
  );
  const summary = tree?.summary ?? {
    images: tree?.nodes.length ?? selectedCase?.items ?? 0,
    families: tree?.nodes.filter((node) => node.root).length ?? 0,
    mean_precision: null,
    low_confidence: 0,
  };

  const handleCreate = async (event: FormEvent) => {
    event.preventDefault();
    const name = caseName.trim();
    if (!name || creating) return;
    setCreating(true);
    setError(null);
    try {
      const created = await createCase(name);
      setCases((current) => [...current, created]);
      setSelectedCaseId(created.id);
      setCaseName("");
    } catch (createError) {
      setError(messageFrom(createError));
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (auditCase: AuditCase) => {
    if (!window.confirm(`Delete “${auditCase.name}” and all of its uploaded images?`)) return;
    setError(null);
    try {
      await deleteCase(auditCase.id);
      setCases((current) => current.filter((candidate) => candidate.id !== auditCase.id));
      if (selectedCaseId === auditCase.id) setSelectedCaseId(null);
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
      await loadCases();
      // Restarting the poll guarantees a full tree after a long analysis request.
      if (selectedCaseId === caseId) setRefreshToken((value) => value + 1);
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

  const selectNode = useCallback((node: TreeNode) => setSelectedNodeId(node.id), []);

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
              <div>
                <input
                  id="audit-case-name"
                  value={caseName}
                  onChange={(event) => setCaseName(event.target.value)}
                  placeholder="Case name"
                  maxLength={100}
                />
                <button className="primary-button" type="submit" disabled={!caseName.trim() || creating}>
                  {creating ? <span className="spinner" aria-label="Creating case" /> : "Add"}
                </button>
              </div>
            </form>

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
                  <button type="button" className="audit-case-select" onClick={() => setSelectedCaseId(auditCase.id)}>
                    <strong>{auditCase.name}</strong>
                    <span>{auditCase.items} {auditCase.items === 1 ? "image" : "images"}</span>
                  </button>
                  <button
                    type="button"
                    className="audit-case-delete"
                    onClick={() => void handleDelete(auditCase)}
                    aria-label={`Delete ${auditCase.name}`}
                    title="Delete case"
                  >
                    ×
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
                An audit identifies the likely original, describes what changed in every copy, and shows how
                sure the system is from calibrated empirical precision. There is no accuracy counter because
                the real lineage is not known in advance.
              </p>
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
                  <p className="eyebrow">Active case</p>
                  <h2>{selectedCase.name}</h2>
                </div>
                <div className="audit-actions">
                  <a className="secondary-button" href={reportUrl(selectedCase.id)} download>
                    Download report (JSON)
                  </a>
                  <button className="secondary-button" type="button" onClick={() => window.print()}>
                    Print summary
                  </button>
                </div>
              </header>

              <dl className="audit-summary" aria-label="Case summary">
                <div><dt>images</dt><dd>{summary.images}</dd></div>
                <div><dt>families</dt><dd>{summary.families}</dd></div>
                <div><dt>mean empirical precision</dt><dd>{formatPrecision(summary.mean_precision)}</dd></div>
                <div><dt>low-confidence decisions</dt><dd>{summary.low_confidence}</dd></div>
                <span
                  className={`poll-dot ${treeFetching ? "is-fetching" : ""} ${treeError ? "has-error" : ""}`}
                  title={treeError ?? "Checking for changes every 3 seconds"}
                  aria-label={treeError ? "Audit updates retrying" : "Audit updates active"}
                />
              </dl>

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
                  className="visually-hidden"
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
                      onClick={() => setSelectedNodeId(null)}
                      aria-label="Close details"
                    >
                      ×
                    </button>
                    <p className="eyebrow">{selectedNode.root ? "Likely original" : "Derived image"}</p>
                    <h2>{incomingEdge?.label ?? "root of its family"}</h2>
                    <img src={selectedNode.url} alt={`Full-size audit image ${selectedNode.id}`} />
                    <div className={incomingEdge ? "edge-details" : "root-details"}>
                      <div className="detail-heading">
                        <span>Lineage's reading</span>
                        {incomingEdge?.evidence.confidence.precision !== null && incomingEdge && (
                          <strong>{formatPrecision(incomingEdge.evidence.confidence.precision)} precision</strong>
                        )}
                      </div>
                      <p>
                        {incomingEdge?.explain ??
                          "No uploaded image explains this one more cheaply, so it is treated as a likely original."}
                      </p>
                      <EvidenceList evidence={incomingEdge?.evidence ?? selectedNode.evidence} compact />
                    </div>
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
                    <small className="node-id-small">id {selectedNode.id}</small>
                  </aside>
                )}
                {treeError && tree && <div className="tree-error-toast">Audit update retrying · {treeError}</div>}
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
            <dl>
              <div><dt>Images</dt><dd>{summary.images}</dd></div>
              <div><dt>Families</dt><dd>{summary.families}</dd></div>
              <div><dt>Mean empirical precision</dt><dd>{formatPrecision(summary.mean_precision)}</dd></div>
              <div><dt>Low-confidence decisions</dt><dd>{summary.low_confidence}</dd></div>
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
                    <p><strong>Parent:</strong> {node.predicted_parent ?? "likely original"}</p>
                    <p>{edge?.explain ?? "Treated as a likely original because no uploaded image explains it more cheaply."}</p>
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
