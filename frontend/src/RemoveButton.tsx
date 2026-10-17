import { useState } from "react";
import { ApiError } from "./api";

const TOKEN_KEY = "lineage.adminToken";

function readToken(): string | undefined {
  try {
    return sessionStorage.getItem(TOKEN_KEY) ?? undefined;
  } catch {
    return undefined;
  }
}

function storeToken(token: string): void {
  try {
    sessionStorage.setItem(TOKEN_KEY, token);
  } catch {
    // private mode: keep it for this call only
  }
}

/**
 * Moderation: remove an image. Confirms first, and if the server wants an admin token
 * (403) asks for it once and remembers it for the session.
 */
export default function RemoveButton({
  remove,
  onRemoved,
  label = "Remove this image",
}: {
  remove: (token?: string) => Promise<unknown>;
  onRemoved: () => void;
  label?: string;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    if (!window.confirm("Remove this image? Its children will be re-linked to its source.")) return;
    setBusy(true);
    setError(null);
    try {
      try {
        await remove(readToken());
      } catch (first) {
        if (!(first instanceof ApiError && first.status === 403)) throw first;
        const token = window.prompt("This server requires an admin token:") ?? "";
        if (!token) throw first;
        storeToken(token);
        await remove(token);
      }
      onRemoved();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Could not remove the image.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="remove-block">
      <button className="danger-button" type="button" onClick={() => void run()} disabled={busy}>
        {busy ? "Removing…" : label}
      </button>
      {error && <p className="error-banner" role="alert">{error}</p>}
    </div>
  );
}
