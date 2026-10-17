import { useEffect, useState } from "react";
import { type HealthResponse, fetchHealth } from "./api";

/** One health fetch on mount: used for the low-memory badge and the LAN URL. */
export function useHealth(): HealthResponse | null {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    fetchHealth(controller.signal).then(setHealth).catch(() => undefined);
    return () => controller.abort();
  }, []);
  return health;
}
