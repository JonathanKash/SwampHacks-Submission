import { useEffect, useState } from "react";
import QRCode from "qrcode";

/**
 * Scan-to-join code for the tablet page, so visitors can add edits from their own phones.
 * Rendered as a data URL so it works offline and needs no server round-trip.
 */
export default function QrCode({ path = "/edit", size = 132, label = "scan to add your own edit", baseUrl }: {
  path?: string;
  size?: number;
  label?: string;
  baseUrl?: string | null;
}) {
  const [src, setSrc] = useState<string | null>(null);
  const [pageOrigin, setPageOrigin] = useState<string>(typeof window !== "undefined" ? window.location.origin : "");
  const normalizedBaseUrl = baseUrl?.replace(/\/+$/, "") ?? null;
  const publicOrigin = normalizedBaseUrl?.startsWith("https://") ? normalizedBaseUrl : null;
  const publicHost = publicOrigin ? new URL(publicOrigin).host : null;
  const origin = publicOrigin
    ?? (/^https?:\/\/(localhost|127\.0\.0\.1)(:|$)/.test(pageOrigin) && normalizedBaseUrl
      ? normalizedBaseUrl
      : pageOrigin);
  const targetPath = publicOrigin ? "/identify" : path;
  const url = `${origin}${targetPath}`;

  // A phone cannot reach "localhost": when the page runs on a loopback origin, ask the
  // server for its LAN address (or PUBLIC_URL) and encode that instead.
  useEffect(() => {
    if (baseUrl !== undefined || !/^https?:\/\/(localhost|127\.0\.0\.1)(:|$)/.test(pageOrigin)) return;
    fetch("/api/health")
      .then((r) => r.json() as Promise<{ lan_url?: string | null }>)
      .then((h) => {
        if (h.lan_url) setPageOrigin(h.lan_url.replace(/\/$/, ""));
      })
      .catch(() => undefined);
  }, [baseUrl, pageOrigin]);

  useEffect(() => {
    let active = true;
    QRCode.toDataURL(url, {
      margin: 1,
      width: size * 2, // crisp on the TV
      errorCorrectionLevel: "M",
      color: { dark: "#f5f7f3", light: "#00000000" },
    })
      .then((data) => {
        if (active) setSrc(data);
      })
      .catch(() => setSrc(null));
    return () => {
      active = false;
    };
  }, [url, size]);

  if (!src) return null;
  return (
    <figure className="qr-join">
      <img src={src} width={size} height={size} alt={`QR code linking to ${url}`} />
      <figcaption className={publicOrigin ? "qr-public" : undefined}>
        <span className="qr-lead">{publicOrigin ? "scan to identify or add an edit" : label}</span>
        {publicOrigin ? (
          // Typed by people who cannot scan: host on one line, path in the accent colour.
          <span className="qr-host">
            {publicHost}
            <b>/identify</b>
          </span>
        ) : (
          <span>{url.replace(/^https?:\/\//, "")}</span>
        )}
      </figcaption>
      {/* Already on a phone? A QR code is useless there; CSS shows this link only under 640 px. */}
      <a className="qr-open" href={targetPath}>
        Open it on this phone
      </a>
    </figure>
  );
}
