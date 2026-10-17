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
  created_at: string;
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

/** What a parent decision was made from: measurements, the alternatives, and calibrated confidence. */
export interface Evidence {
  chosen_cost: number;
  terms: Record<string, number>;
  runner_up: { id: string; cost: number } | null;
  margin: number | null;
  confidence: { bucket: string | null; precision: number | null; n: number };
  measurements: Record<string, number | string | number[]>;
  reasons: string[];
}

export interface TreeNode extends PoolItem {
  predicted_parent: string | null;
  correct: boolean;
  root: boolean;
  evidence: Evidence;
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
  calibration?: { runs: string[]; generated_at: string | null };
  summary?: {
    images: number;
    families: number;
    mean_precision: number | null;
    low_confidence: number;
  };
  mode?: "audit";
}

export interface AuditCase {
  id: string;
  name: string;
  items: number;
  created_at: number;
}

export interface CasesResponse {
  cases: AuditCase[];
}

export interface CaseItemsResponse {
  items: PoolItem[];
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

export function createCase(name: string, signal?: AbortSignal): Promise<AuditCase> {
  return requestJson<AuditCase>("/api/cases", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
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
