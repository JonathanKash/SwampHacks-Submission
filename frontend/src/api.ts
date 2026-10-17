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
}

export interface PoolResponse {
  items: PoolItem[];
  edits: EditKind[];
  filters: FilterKind[];
}

export interface TreeNode extends PoolItem {
  predicted_parent: string | null;
  correct: boolean;
  root: boolean;
}

export interface TreeEdge {
  src: string;
  dst: string;
  label: string;
  explain: string;
  cost: number;
  semantic: boolean;
  correct: boolean;
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
