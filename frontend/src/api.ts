export type EditKind = "crop" | "rotate" | "filter" | "caption" | "jpeg" | "restyle";

export type FilterKind =
  | "warm"
  | "cool"
  | "brighter"
  | "darker"
  | "contrast"
  | "grayscale";

export type RestyleKind =
  | "watercolor"
  | "pencil sketch"
  | "oil painting"
  | "pop art"
  | "pixel art"
  | "stained glass"
  | "neon"
  | "claymation";

export type EditParams = Record<string, unknown>;

export interface PoolItem {
  id: string;
  url: string;
  thumb: string;
  edit: string | null;
  params: EditParams;
  source: string;
  created_at: number; // unix seconds (float) from the server
  footprint?: {
    sha256: string;
    width: number;
    height: number;
    bytes: number;
    phash: string;
  };
  metadata?: {
    software?: string;
    datetime?: string;
    camera?: string;
    has_exif: boolean;
  };
}

export interface PoolResponse {
  items: PoolItem[];
  edits: EditKind[];
  filters: FilterKind[];
}

export interface CalibrationCount {
  correct: number;
  n: number;
}

export interface CalibrationCorpus {
  buckets: Record<string, CalibrationCount>;
  generated_at: string;
  source: string;
  note?: string;
}

export interface CalibrationResponse {
  generated_at: string;
  runs: string[];
  root_cost: number;
  weights: Record<string, number>;
  buckets: Record<string, CalibrationCount>;
  per_edit?: Record<string, CalibrationCount>;
  caption_side?: CalibrationCount & { source: string; meaning: string };
  corpora?: Record<string, CalibrationCorpus>;
}

export type CompareVerdict = "parent-child" | "siblings" | "unrelated" | "inconclusive";

export type ConfidenceByCorpus = Record<string, { precision: number; n: number }>;

export type CompareConfidence =
  | {
      bucket: "caption-side cue";
      precision: number;
      n: number;
      observed: number;
      source: string;
      by_corpus?: ConfidenceByCorpus;
    }
  | {
      bucket: `margin ${string}`;
      precision: number | null;
      n: number;
      by_corpus?: ConfidenceByCorpus;
    }
  | {
      bucket: null;
      precision: null;
      n: 0;
      by_corpus?: ConfidenceByCorpus;
    };

export interface CompareReportResponse {
  verdict: CompareVerdict;
  relation: string;
  rerendered?: boolean;
  parent: "A" | "B" | null;
  child: "A" | "B" | null;
  summary: string;
  decisive_cues: string[];
  caption_side: "A" | "B" | null;
  noise: {
    measurable: boolean;
    region_fraction: number;
    noise_inside_changed?: number;
    noise_outside?: number;
    ratio?: number;
    break?: boolean;
    two_tone?: number | null;
    achromatic?: number;
    dark?: number;
    bright?: number;
    lum_std?: number;
    caption_like?: boolean;
    caption_on?: "copy" | "source" | null;
  } | null;
  confidence: CompareConfidence;
  benchmark_for_edit_type: { edit_type: string | null; accuracy: number | null; n: number };
  costs: { a_to_b: number; b_to_a: number; margin: number | null };
  explain: { a_to_b: string; b_to_a: string };
  signals: Array<{
    signal: string;
    found: string;
    direction: string;
    weight: number | string;
    kind: "pixel" | "semantic" | "metadata" | "gate" | "indicator";
  }>;
  conflicts: string[];
  unavailable: string[];
  ai_edit_indicators: string[];
  limitations: string[];
  reproducibility: {
    tool_version: string;
    weights_sha256_12: string;
    input_sha256: { A: string | null; B: string | null };
    calibration_runs: string[];
  };
  plates: {
    a_to_b: { png: string; registered: boolean; inliers: number };
    b_to_a: { png: string; registered: boolean; inliers: number };
  };
}

/** What a parent decision was made from: measurements, the alternatives, and calibrated confidence. */
export interface Confidence {
  bucket: string | null;
  precision: number | null;
  n: number;
  by_corpus?: ConfidenceByCorpus;
}

export interface Evidence {
  chosen_cost: number;
  terms: Record<string, number>;
  runner_up: { id: string; cost: number } | null;
  margin: number | null;
  confidence: Confidence;
  measurements: Record<string, number | string | number[]>;
  reasons: string[];
}

export interface TreeNode extends PoolItem {
  predicted_parent: string | null;
  correct: boolean;
  root: boolean;
  explains: string[];
  evidence: Evidence;
}

interface IdentifyResponseBase {
  case: string;
  footprint: Record<string, unknown>;
  metadata: Record<string, unknown>;
}

export interface IdentifyMatchResponse extends IdentifyResponseBase {
  matched: true;
  parent: TreeNode;
  root: TreeNode;
  match_strength: number;
  tree_root?: TreeNode;
  tree_disagrees?: boolean;
  edit: string;
  explain: string;
  cost: number;
  reverse_cost: number;
  semantic_only: boolean;
  would_be_better_parent: boolean;
  depth_below_root: number;
  report: CompareReportResponse;
}

export interface IdentifyNoMatchResponse extends IdentifyResponseBase {
  matched: false;
  reason: string;
  nearest?: string;
  cost?: number;
}

export type IdentifyResponse = IdentifyMatchResponse | IdentifyNoMatchResponse;

export interface IdentifyStatsResponse {
  available: boolean;
  knowledge_base?: string;
  items?: number;
  queries?: number;
  correct?: number;
  abstained?: number;
  wrong_family?: number;
  family_accuracy?: number;
  wrong_family_rate?: number;
  median_latency_s?: number;
  p90_latency_s?: number;
  generated_at?: string;
}

export interface TreeEdge {
  src: string;
  dst: string;
  label: string;
  explain: string;
  cost: number;
  semantic: boolean;
  correct: boolean;
  evidence: Evidence;
}

export interface TreeResponse {
  version: number;
  nodes: TreeNode[];
  edges: TreeEdge[];
  accuracy: {
    correct: number;
    total: number;
    pct: number | null;
  };
  newest_id: string | null;
  newest_took_over: boolean;
  calibration?: { runs: string[]; generated_at: string | null };
  summary?: {
    images: number;
    families: number;
    mean_precision: number | null;
    low_confidence: number;
  };
  mode?: "demo" | "audit";
}

export interface AuditCase {
  id: string;
  name: string;
  items: number;
  created_at: number;
  analyst: string;
  protected?: boolean; // the case that backs /identify; the server refuses to delete it without the admin token
}

export interface CasesResponse {
  cases: AuditCase[];
}

export interface CaseItemsResponse {
  items: PoolItem[];
}

export interface UrlFailure {
  url: string;
  error: string;
}

export interface AddCaseItemsByUrlResponse {
  items: TreeNode[];
  failed: UrlFailure[];
}

export interface WebSearchCaseItemResponse extends AddCaseItemsByUrlResponse {
  candidates: number;
}

export interface EditRequest {
  parent_id: string;
  edit: EditKind;
  params: EditParams;
}

interface ErrorBody {
  detail?: unknown;
}

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as ErrorBody;
    if (typeof body.detail === "string") {
      return body.detail;
    }
  } catch {
    // Some proxy failures are HTML or empty; the HTTP status remains useful.
  }
  return `Request failed (${response.status})`;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    throw new ApiError(await errorMessage(response), response.status);
  }
  return (await response.json()) as T;
}

export function fetchRandom(signal?: AbortSignal): Promise<PoolItem> {
  return requestJson<PoolItem>("/api/random", { signal });
}

export function fetchPool(signal?: AbortSignal): Promise<PoolResponse> {
  return requestJson<PoolResponse>("/api/pool", { signal });
}

export function fetchCalibration(signal?: AbortSignal): Promise<CalibrationResponse> {
  return requestJson<CalibrationResponse>("/api/calibration", { signal });
}

export function comparePair(formData: FormData, signal?: AbortSignal): Promise<CompareReportResponse> {
  return requestJson<CompareReportResponse>("/api/compare", {
    method: "POST",
    body: formData,
    signal,
  });
}

export function identifyImage(formData: FormData, signal?: AbortSignal): Promise<IdentifyResponse> {
  return requestJson<IdentifyResponse>("/api/identify", {
    method: "POST",
    body: formData,
    signal,
  });
}

export function fetchIdentifyStats(signal?: AbortSignal): Promise<IdentifyStatsResponse> {
  return requestJson<IdentifyStatsResponse>("/api/identify/stats", { signal });
}

export function compareIds(
  aId: string,
  bId: string,
  caseId?: string,
  signal?: AbortSignal,
): Promise<CompareReportResponse> {
  const body = new FormData();
  body.append("a_id", aId);
  body.append("b_id", bId);
  if (caseId) body.append("case", caseId);
  return comparePair(body, signal);
}

export function submitEdit(payload: EditRequest, signal?: AbortSignal): Promise<PoolItem> {
  return requestJson<PoolItem>("/api/edit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
}

export async function fetchTree(since?: number, signal?: AbortSignal): Promise<TreeResponse | null> {
  const query = since === undefined ? "" : `?since=${encodeURIComponent(since)}`;
  const response = await fetch(`/api/tree${query}`, { signal });
  if (response.status === 204) {
    return null;
  }
  if (!response.ok) {
    throw new ApiError(await errorMessage(response), response.status);
  }
  return (await response.json()) as TreeResponse;
}

export function fetchCases(signal?: AbortSignal): Promise<CasesResponse> {
  return requestJson<CasesResponse>("/api/cases", { signal });
}

export function createCase(name: string, analyst?: string, signal?: AbortSignal): Promise<AuditCase> {
  return requestJson<AuditCase>("/api/cases", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, analyst: analyst || undefined }),
    signal,
  });
}

export function createSampleCase(signal?: AbortSignal): Promise<AuditCase> {
  return requestJson<AuditCase>("/api/cases/sample", {
    method: "POST",
    signal,
  });
}

export function deleteCase(id: string, signal?: AbortSignal): Promise<{ ok: true }> {
  return requestJson<{ ok: true }>(`/api/cases/${encodeURIComponent(id)}`, {
    method: "DELETE",
    signal,
  });
}

export async function uploadCaseFiles(
  id: string,
  files: File[],
  signal?: AbortSignal,
): Promise<CaseItemsResponse> {
  const body = new FormData();
  files.forEach((file) => body.append("files", file));
  return requestJson<CaseItemsResponse>(`/api/cases/${encodeURIComponent(id)}/items`, {
    method: "POST",
    body,
    signal,
  });
}

export function addCaseItemsByUrl(
  caseId: string,
  urls: string[],
  signal?: AbortSignal,
): Promise<AddCaseItemsByUrlResponse> {
  return requestJson<AddCaseItemsByUrlResponse>(
    `/api/cases/${encodeURIComponent(caseId)}/items/urls`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ urls }),
      signal,
    },
  );
}

export function webSearchCaseItem(
  caseId: string,
  itemId: string,
  signal?: AbortSignal,
): Promise<WebSearchCaseItemResponse> {
  return requestJson<WebSearchCaseItemResponse>(
    `/api/cases/${encodeURIComponent(caseId)}/web-search/${encodeURIComponent(itemId)}?limit=10`,
    { method: "POST", signal },
  );
}

export async function fetchCaseTree(
  id: string,
  since?: number,
  signal?: AbortSignal,
): Promise<TreeResponse | null> {
  const query = since === undefined ? "" : `?since=${encodeURIComponent(since)}`;
  const response = await fetch(`/api/cases/${encodeURIComponent(id)}/tree${query}`, { signal });
  if (response.status === 204) {
    return null;
  }
  if (!response.ok) {
    throw new ApiError(await errorMessage(response), response.status);
  }
  return (await response.json()) as TreeResponse;
}

export function reportUrl(id: string): string {
  return `/api/cases/${encodeURIComponent(id)}/report`;
}

export function htmlReportUrl(id: string): string {
  return `/api/cases/${encodeURIComponent(id)}/report.html`;
}


// ---- text media (second plug-in) ---------------------------------------------
export interface TextNode {
  id: string;
  text: string;
  words: number;
  predicted_parent: string | null;
  root: boolean;
  evidence: Evidence;
}

export interface TextEdge {
  src: string;
  dst: string;
  label: string;
  explain: string;
  cost: number;
  semantic: boolean;
  evidence: Evidence;
}

export interface TextTreeResponse {
  mode: "text";
  nodes: TextNode[];
  edges: TextEdge[];
  note?: string;
  summary: { versions: number; families: number };
}

export function buildTextTree(versions: Array<{ id?: string; text: string }>, signal?: AbortSignal): Promise<TextTreeResponse> {
  return requestJson<TextTreeResponse>("/api/text/tree", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ versions }),
    signal,
  });
}


// ---- health + moderation ------------------------------------------------------
export interface HealthResponse {
  ok: boolean;
  items: number;
  version: number;
  clip: boolean;
  lan_url: string | null;
  web_search: boolean;
  identify_ready: boolean;
}

export function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return requestJson<HealthResponse>("/api/health", { signal });
}

function adminHeaders(token?: string): HeadersInit {
  return token ? { "X-Admin-Token": token } : {};
}

export function deleteItem(id: string, token?: string): Promise<{ ok: true }> {
  return requestJson<{ ok: true }>(`/api/items/${encodeURIComponent(id)}`, { method: "DELETE", headers: adminHeaders(token) });
}

export function deleteCaseItem(caseId: string, id: string, token?: string): Promise<{ ok: true }> {
  return requestJson<{ ok: true }>(
    `/api/cases/${encodeURIComponent(caseId)}/items/${encodeURIComponent(id)}`,
    { method: "DELETE", headers: adminHeaders(token) },
  );
}
