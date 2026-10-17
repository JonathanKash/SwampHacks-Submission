import { useEffect, useState } from "react";
import QRCode from "qrcode";

/**
 * Scan-to-join code for the tablet page, so visitors can add edits from their own phones.
 * Rendered as a data URL so it works offline and needs no server round-trip.
 */
export default function QrCode({ path = "/edit", size = 132, label = "scan to add your own edit" }: {
  path?: string;
  size?: number;
  label?: string;
}) {
  const [src, setSrc] = useState<string | null>(null);
  const [origin, setOrigin] = useState<string>(typeof window !== "undefined" ? window.location.origin : "");
  const url = `${origin}${path}`;

  // A phone cannot reach "localhost": when the page runs on a loopback origin, ask the
  // server for its LAN address (or PUBLIC_URL) and encode that instead.
  useEffect(() => {
    if (!/^https?:\/\/(localhost|127\.0\.0\.1)(:|$)/.test(origin)) return;
    fetch("/api/health")
      .then((r) => r.json() as Promise<{ lan_url?: string | null }>)
      .then((h) => {
        if (h.lan_url) setOrigin(h.lan_url.replace(/\/$/, ""));
      })
      .catch(() => undefined);
  }, [origin]);

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
      <figcaption>
        {label}
        <span>{url.replace(/^https?:\/\//, "")}</span>
      </figcaption>
    </figure>
  );
}
