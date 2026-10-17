import { useEffect, useMemo, useRef, useState } from "react";
import type { TreeEdge, TreeNode, TreeResponse } from "./api";

const STEP_MS = 1600;

interface ReplayFrame {
  node: TreeNode;
  parent: TreeNode | null;
  edge: TreeEdge | null;
}

function byCreatedAt(left: TreeNode, right: TreeNode): number {
  if (typeof left.created_at === "number" && typeof right.created_at === "number") {
    const difference = left.created_at - right.created_at;
    if (difference !== 0) return difference;
  }
  return left.id.localeCompare(right.id);
}

function familyFrom(root: TreeNode, tree: TreeResponse): ReplayFrame[] {
  const nodesById = new Map(tree.nodes.map((node) => [node.id, node]));
  const childrenById = new Map<string, ReplayFrame[]>();

  for (const edge of tree.edges) {
    const node = nodesById.get(edge.dst);
    const parent = nodesById.get(edge.src);
    if (!node || !parent) continue;
    const children = childrenById.get(parent.id) ?? [];
    children.push({ node, parent, edge });
    childrenById.set(parent.id, children);
  }
  childrenById.forEach((children) => children.sort((left, right) => byCreatedAt(left.node, right.node)));

  const frames: ReplayFrame[] = [{ node: root, parent: null, edge: null }];
  const seen = new Set([root.id]);
  let level = frames;
  while (level.length > 0) {
    const nextLevel: ReplayFrame[] = [];
    for (const parentFrame of level) {
      for (const child of childrenById.get(parentFrame.node.id) ?? []) {
        if (seen.has(child.node.id)) continue;
        seen.add(child.node.id);
        nextLevel.push(child);
      }
    }
    nextLevel.sort((left, right) => byCreatedAt(left.node, right.node));
    frames.push(...nextLevel);
    level = nextLevel;
  }
  return frames;
}

function largestFamily(tree: TreeResponse): ReplayFrame[] {
  const roots = tree.nodes.filter((node) => node.root).sort(byCreatedAt);
  const families = roots.map((root) => familyFrom(root, tree));
  families.sort((left, right) => right.length - left.length || byCreatedAt(left[0].node, right[0].node));
  return families[0] ?? [];
}

function shortLabel(node: TreeNode, tree: TreeResponse): string {
  if (node.root) return "original";
  const label = tree.edges.find((edge) => edge.dst === node.id)?.label ?? node.edit ?? node.id;
  return label.length > 24 ? `${label.slice(0, 23)}…` : label;
}

interface ReplayOverlayProps {
  tree: TreeResponse;
  onClose: () => void;
}

export default function ReplayOverlay({ tree, onClose }: ReplayOverlayProps) {
  const frames = useMemo(() => largestFamily(tree), [tree]);
  const [step, setStep] = useState(0);
  const [paused, setPaused] = useState(false);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const finalFrame = step >= frames.length;

  useEffect(() => {
    closeButtonRef.current?.focus();
  }, []);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  useEffect(() => {
    if (paused) return;
    const timer = window.setTimeout(() => {
      if (finalFrame) onClose();
      else setStep((current) => current + 1);
    }, STEP_MS);
    return () => window.clearTimeout(timer);
  }, [finalFrame, onClose, paused, step]);

  const togglePaused = () => setPaused((current) => !current);
  const frame = frames[Math.min(step, Math.max(0, frames.length - 1))];
  const previousFrame = step > 0 ? frames[step - 1] : null;
  const caption = frame?.edge && frame.parent
    ? `${frame.edge.label} · from ${shortLabel(frame.parent, tree)}`
    : "original";

  return (
    <div className="replay-backdrop" onClick={togglePaused}>
      <section
        className={`arrival replay-overlay ${paused ? "is-paused" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="replay-title"
        aria-describedby="replay-help"
      >
        <button
          className="panel-close replay-close"
          type="button"
          ref={closeButtonRef}
          onClick={(event) => {
            event.stopPropagation();
            onClose();
          }}
          aria-label="Close replay"
        >
          ×
        </button>
        <p className="eyebrow">Edit-history replay</p>
        <h2 id="replay-title">Largest reconstructed family</h2>

        {finalFrame ? (
          <p className="replay-final" role="status">
            Family of {frames.length} versions reconstructed from pixels alone
          </p>
        ) : frame ? (
          <figure className="replay-frame" aria-live="polite">
            <div className="replay-image-stack">
              {previousFrame && (
                <img className="replay-previous" src={previousFrame.node.url} alt="" aria-hidden="true" />
              )}
              <img
                className="replay-current"
                key={frame.node.id}
                src={frame.node.url}
                alt={`Version ${step + 1} of ${frames.length}`}
              />
            </div>
            <figcaption>
              <strong>{caption}</strong>
              {frame.edge && <span>{frame.edge.explain}</span>}
            </figcaption>
          </figure>
        ) : (
          <p className="replay-final">No family to replay</p>
        )}

        <footer className="replay-footer">
          <span>{finalFrame ? "complete" : `step ${step + 1} of ${frames.length}`}</span>
          <span id="replay-help">Click the overlay to {paused ? "resume" : "pause"}</span>
          <button
            className="secondary-button replay-pause"
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              togglePaused();
            }}
          >
            {paused ? "Resume" : "Pause"}
          </button>
        </footer>
      </section>
    </div>
  );
}
