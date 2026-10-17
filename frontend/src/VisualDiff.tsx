import { useState } from "react";

const DIFF_CAPTION =
  "source aligned onto this copy · this copy · residual after color fit (brighter = more different; hatched = area the source cannot supply)";

export default function VisualDiff({ src }: { src: string }) {
  const [shown, setShown] = useState(false);
  const [loading, setLoading] = useState(false);
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
        {shown ? "Hide visual diff" : "Show visual diff"}
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
          {error && <p className="visual-diff-error" role="alert">Visual diff unavailable for this image.</p>}
          {!error && <figcaption>{DIFF_CAPTION}</figcaption>}
        </figure>
      )}
    </div>
  );
}
