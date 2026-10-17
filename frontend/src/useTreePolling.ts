import { useEffect, useRef, useState } from "react";
import { type TreeResponse, fetchTree } from "./api";

interface TreePollingState {
  tree: TreeResponse | null;
  loading: boolean;
  fetching: boolean;
  error: string | null;
}

export function useTreePolling(intervalMs = 2_000): TreePollingState {
  const [tree, setTree] = useState<TreeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [fetching, setFetching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const version = useRef<number | undefined>(undefined);

  useEffect(() => {
    let active = true;
    let timer: number | undefined;
    let controller: AbortController | null = null;

    const poll = async () => {
      controller = new AbortController();
      setFetching(true);
      try {
        const next = await fetchTree(version.current, controller.signal);
        if (!active) return;
        if (next) {
          version.current = next.version;
          setTree(next);
        }
        setError(null);
      } catch (pollError) {
        if (!active || (pollError instanceof DOMException && pollError.name === "AbortError")) return;
        setError(pollError instanceof Error ? pollError.message : "Live updates are temporarily unavailable.");
      } finally {
        if (active) {
          setLoading(false);
          setFetching(false);
          timer = window.setTimeout(() => void poll(), intervalMs);
        }
      }
    };

    void poll();
    return () => {
      active = false;
      controller?.abort();
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [intervalMs]);

  return { tree, loading, fetching, error };
}
