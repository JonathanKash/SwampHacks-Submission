import { useState } from "react";

const DIFF_CAPTION =
  "source aligned onto this copy · this copy · residual after color fit (brighter = more different; hatched = area the source cannot supply)";

interface VisualDiffProps {
  src: string;
  caption?: string;
  defaultShown?: boolean;
  hideLabel?: string;
  showLabel?: string;
  unavailableMessage?: string;
}

export default function VisualDiff({
  src,
  caption = DIFF_CAPTION,
  defaultShown = false,
  hideLabel = "Hide visual diff",
  showLabel = "Show visual diff",
  unavailableMessage = "Visual diff unavailable for this image.",
}: VisualDiffProps) {
  const [shown, setShown] = useState(defaultShown);
  const [loading, setLoading] = useState(defaultShown);
  const [error, setError] = useState(false);

  const toggle = () => {
    const next = !shown;
    setShown(next);
    if (next) {
      setLoading(true);
      setError(false);
    }
  };

  return (
    <div className="visual-diff-block">
      <button
        className="secondary-button visual-diff-toggle"
        type="button"
        onClick={toggle}
        aria-expanded={shown}
      >
        {shown ? hideLabel : showLabel}
      </button>
      {shown && (
        <figure className="visual-diff">
          {loading && <span className="spinner" aria-label="Loading visual diff" />}
          {!error && (
            <img
              src={src}
              alt="Visual diff plate showing the aligned source, this copy, and a residual heatmap"
              onLoad={() => setLoading(false)}
              onError={() => {
                setLoading(false);
                setError(true);
              }}
            />
          )}
          {error && <p className="visual-diff-error" role="alert">{unavailableMessage}</p>}
          {!error && <figcaption>{caption}</figcaption>}
        </figure>
      )}
    </div>
  );
}
