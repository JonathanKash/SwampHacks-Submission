import {
  hierarchy,
  select,
  tree as d3Tree,
  zoom,
  zoomIdentity,
  zoomTransform,
  type D3ZoomEvent,
  type ZoomBehavior,
  type ZoomTransform,
} from "d3";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import type { TreeEdge, TreeNode, TreeResponse } from "./api";
import { reliabilityTier } from "./EvidenceList";

const NODE_SIZE = 96;
const NODE_HALF = NODE_SIZE / 2;
const HORIZONTAL_GAP = 150;
// Leave a clear lane for the caption and edge pill between thumbnail rows.
// 1.9 x thumbnail: room for a caption and an edge pill, but a 9-level demo forest still fits a 1600x900 screen
const VERTICAL_GAP = Math.max(166, Math.ceil(NODE_SIZE * 1.9));
const EDGE_LABEL_POSITION = 0.62;
const EDGE_LABEL_HALO_WIDTH = 6;
const TRANSITION_MS = 600;
const ZOOM_TRANSITION_MS = 250;
const MIN_ZOOM = 0.3;
const MAX_ZOOM = 6;
const MIN_FITTED_NODE_SIZE = 36; // below this the whole-forest view is unreadable, so focus the newest node instead
const FOCUSED_NODE_SIZE = 64;

interface HierarchyDatum {
  id: string;
  item?: TreeNode;
  children: HierarchyDatum[];
}

interface LayoutNode {
  item: TreeNode;
  x: number;
  y: number;
}

interface LayoutEdge extends TreeEdge {
  source: LayoutNode;
  target: LayoutNode;
}

interface LayoutResult {
  nodes: LayoutNode[];
  edges: LayoutEdge[];
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
}

interface TooltipState {
  x: number;
  y: number;
  text: string;
}

interface TreeViewProps {
  data: TreeResponse;
  selectedId: string | null;
  onSelect: (node: TreeNode, target: SVGGElement) => void;
  colorBy?: "truth" | "confidence";
  rootLabel?: string;
  rootTitle?: string;
}

function buildLayout(data: TreeResponse): LayoutResult {
  const records = new Map<string, HierarchyDatum>();
  for (const item of data.nodes) {
    records.set(item.id, { id: item.id, item, children: [] });
  }

  const roots: HierarchyDatum[] = [];
  for (const item of data.nodes) {
    const record = records.get(item.id);
    const parent = item.predicted_parent ? records.get(item.predicted_parent) : undefined;
    if (!record) continue;
    if (parent && parent !== record) parent.children.push(record);
    else roots.push(record);
  }

  // Oldest first so the layout is stable as uploads arrive; created_at is a unix timestamp.
  const byAge = (left: HierarchyDatum, right: HierarchyDatum) =>
    (left.item?.created_at ?? 0) - (right.item?.created_at ?? 0) || left.id.localeCompare(right.id);
  const sortBranch = (branch: HierarchyDatum) => {
    branch.children.sort(byAge);
    branch.children.forEach(sortBranch);
  };
  roots.sort(byAge);
  roots.forEach(sortBranch);

  const virtualRoot: HierarchyDatum = { id: "__forest__", children: roots };
  const root = hierarchy(virtualRoot, (datum) => datum.children);
  const pointRoot = d3Tree<HierarchyDatum>().nodeSize([HORIZONTAL_GAP, VERTICAL_GAP])(root);
  const nodes: LayoutNode[] = [];

  for (const point of pointRoot.descendants()) {
    if (!point.data.item) continue;
    nodes.push({ item: point.data.item, x: point.x, y: point.y - VERTICAL_GAP });
  }

  const positions = new Map(nodes.map((node) => [node.item.id, node]));
  const edges: LayoutEdge[] = [];
  for (const edge of data.edges) {
    const source = positions.get(edge.src);
    const target = positions.get(edge.dst);
    if (source && target) edges.push({ ...edge, source, target });
  }

  const xs = nodes.map((node) => node.x);
  const ys = nodes.map((node) => node.y);
  return {
    nodes,
    edges,
    minX: Math.min(...xs) - 72,
    maxX: Math.max(...xs) + 72,
    minY: Math.min(...ys) - 66,
    maxY: Math.max(...ys) + 74,
  };
}

function linkPath(edge: LayoutEdge): string {
  const startY = edge.source.y + NODE_HALF;
  const endY = edge.target.y - NODE_HALF;
  const middleY = (startY + endY) / 2;
  return `M${edge.source.x},${startY} C${edge.source.x},${middleY} ${edge.target.x},${middleY} ${edge.target.x},${endY}`;
}

function collapsedPath(node: LayoutNode): string {
  return `M${node.x},${node.y} C${node.x},${node.y} ${node.x},${node.y} ${node.x},${node.y}`;
}

function cubicPoint(start: number, control1: number, control2: number, end: number, t: number): number {
  const remaining = 1 - t;
  return remaining ** 3 * start
    + 3 * remaining ** 2 * t * control1
    + 3 * remaining * t ** 2 * control2
    + t ** 3 * end;
}

function labelPosition(edge: LayoutEdge): { x: number; y: number } {
  const startY = edge.source.y + NODE_HALF;
  const endY = edge.target.y - NODE_HALF;
  const middleY = (startY + endY) / 2;
  return {
    x: cubicPoint(edge.source.x, edge.source.x, edge.target.x, edge.target.x, EDGE_LABEL_POSITION),
    y: cubicPoint(startY, middleY, middleY, endY, EDGE_LABEL_POSITION),
  };
}

function canvasBackground(element: Element): string {
  let current: Element | null = element;
  while (current) {
    const color = window.getComputedStyle(current).backgroundColor;
    if (color !== "transparent" && color !== "rgba(0, 0, 0, 0)") return color;
    current = current.parentElement;
  }
  return "#070b0a";
}

function labelText(label: string): string {
  return label.length > 25 ? `${label.slice(0, 24)}…` : label;
}

function labelWidth(label: string): number {
  return Math.min(196, Math.max(56, labelText(label).length * 7.2 + 22));
}

function edgePillText(edge: LayoutEdge, colorBy: "truth" | "confidence"): string {
  const prefixes = [];
  if (colorBy === "truth" && !edge.correct) prefixes.push("×");
  if (edge.semantic) prefixes.push("≈");
  return [...prefixes, edge.label].join(" ");
}

function edgeAriaLabel(edge: LayoutEdge, colorBy: "truth" | "confidence"): string {
  const precision = edge.evidence.confidence.precision;
  const precisionText = precision === null
    ? "empirical precision unavailable"
    : `${Math.round(precision * 100)}% empirical precision`;
  if (colorBy === "confidence") {
    const tier = precision === null ? "unrated" : reliabilityTier(precision);
    return `derived via ${edge.label}, ${precisionText}, ${tier} tier`;
  }
  return `derived via ${edge.label}, ${edge.correct ? "correct" : "wrong"} parent, ${precisionText}`;
}

function fitTreeTransform(layout: LayoutResult, width: number, height: number): ZoomTransform {
  const contentWidth = Math.max(1, layout.maxX - layout.minX);
  const contentHeight = Math.max(1, layout.maxY - layout.minY);
  // Keep the existing breathing room for the legend and newest-image callout.
  const bottomReserve = 150; // the newest-image callout is about 130 px tall at the bottom-left
  const usableHeight = Math.max(1, height - 54 - bottomReserve);
  const scale = Math.min(1.25, Math.max(1, width - 64) / contentWidth, usableHeight / contentHeight);
  const scaledHeight = contentHeight * scale;
  const top = Math.max(26, (usableHeight - scaledHeight) / 2 + 20);
  const translateX = width / 2 - ((layout.minX + layout.maxX) / 2) * scale;
  const translateY = top - layout.minY * scale;
  return zoomIdentity.translate(translateX, translateY).scale(scale);
}

function focusedTreeTransform(
  layout: LayoutResult,
  data: TreeResponse,
  width: number,
  height: number,
): ZoomTransform {
  const focus = layout.nodes.find((node) => node.item.id === data.newest_id)
    ?? layout.nodes.find((node) => node.item.root)
    ?? layout.nodes.find((node) => !node.item.predicted_parent)
    ?? layout.nodes[0];
  const scale = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, FOCUSED_NODE_SIZE / NODE_SIZE));
  if (!focus) return zoomIdentity;
  return zoomIdentity
    .translate(width / 2 - focus.x * scale, height / 2 - focus.y * scale)
    .scale(scale);
}

export default function TreeView({
  data,
  selectedId,
  onSelect,
  colorBy = "truth",
  rootLabel = "original",
  rootTitle,
}: TreeViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const previousPositions = useRef(new Map<string, LayoutNode>());
  const previousItemCount = useRef<number | null>(null);
  const zoomBehaviorRef = useRef<ZoomBehavior<SVGSVGElement, unknown> | null>(null);
  const fitTransformRef = useRef<ZoomTransform>(zoomIdentity);
  const reduceMotionRef = useRef(false);
  const draggedRef = useRef(false);
  const dragResetTimerRef = useRef<number | null>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);
  const [showZoomHint, setShowZoomHint] = useState(true);

  useEffect(() => {
    const timer = window.setTimeout(() => setShowZoomHint(false), 4000);
    return () => window.clearTimeout(timer);
  }, []);

  const changeZoom = useCallback((factor: number) => {
    const svgElement = svgRef.current;
    const zoomBehavior = zoomBehaviorRef.current;
    if (!svgElement || !zoomBehavior) return;
    const svg = select(svgElement);
    svg.interrupt("tree-zoom");
    if (reduceMotionRef.current) svg.call(zoomBehavior.scaleBy, factor);
    else svg.transition("tree-zoom").duration(ZOOM_TRANSITION_MS).call(zoomBehavior.scaleBy, factor);
  }, []);

  const fitTree = useCallback(() => {
    const svgElement = svgRef.current;
    const zoomBehavior = zoomBehaviorRef.current;
    if (!svgElement || !zoomBehavior) return;
    const svg = select(svgElement);
    svg.interrupt("tree-zoom");
    if (reduceMotionRef.current) svg.call(zoomBehavior.transform, fitTransformRef.current);
    else svg.transition("tree-zoom").duration(ZOOM_TRANSITION_MS).call(zoomBehavior.transform, fitTransformRef.current);
  }, []);

  useLayoutEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    const updateSize = () => {
      const bounds = element.getBoundingClientRect();
      setSize({ width: Math.round(bounds.width), height: Math.round(bounds.height) });
    };
    updateSize();
    const observer = new ResizeObserver(updateSize);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useLayoutEffect(() => {
    const svgElement = svgRef.current;
    if (!svgElement || size.width === 0 || size.height === 0 || data.nodes.length === 0) return;

    const layout = buildLayout(data);
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    reduceMotionRef.current = reduceMotion;
    const transitionMs = reduceMotion ? 0 : TRANSITION_MS;
    const exitTransitionMs = reduceMotion ? 0 : 240;
    // Caption each node with what was done to it; ids mean nothing to a viewer.
    const captions = new Map(data.edges.map((edge) => [edge.dst, edge.label]));
    const svg = select(svgElement).attr("viewBox", `0 0 ${size.width} ${size.height}`);
    const viewport = svg.select<SVGGElement>("g.viewport");
    const stage = viewport.select<SVGGElement>("g.tree-stage");
    const clipsLayer = svg.select<SVGDefsElement>("defs.tree-defs");
    const linksLayer = stage.select<SVGGElement>("g.links-layer");
    const labelsLayer = stage.select<SVGGElement>("g.labels-layer");
    const nodesLayer = stage.select<SVGGElement>("g.nodes-layer");
    const labelHaloColor = canvasBackground(svgElement);

    const fitTransform = fitTreeTransform(layout, size.width, size.height);
    fitTransformRef.current = fitTransform;
    const zoomBehavior = zoom<SVGSVGElement, unknown>()
      .scaleExtent([MIN_ZOOM, MAX_ZOOM])
      .clickDistance(4)
      .on("start", (event: D3ZoomEvent<SVGSVGElement, unknown>) => {
        const type = event.sourceEvent?.type;
        if (type === "mousedown" || type === "touchstart" || type === "pointerdown") {
          if (dragResetTimerRef.current !== null) window.clearTimeout(dragResetTimerRef.current);
          draggedRef.current = false;
        }
      })
      .on("zoom", (event: D3ZoomEvent<SVGSVGElement, unknown>) => {
        const type = event.sourceEvent?.type;
        if (type === "mousemove" || type === "touchmove" || type === "pointermove") {
          draggedRef.current = true;
        }
        viewport.attr("transform", event.transform.toString());
      })
      .on("end", () => {
        if (!draggedRef.current) return;
        // Let the click following mouseup observe the drag before clearing it.
        dragResetTimerRef.current = window.setTimeout(() => {
          draggedRef.current = false;
          dragResetTimerRef.current = null;
        }, 0);
      });
    zoomBehaviorRef.current = zoomBehavior;
    svg.call(zoomBehavior);
    viewport.attr("transform", zoomTransform(svgElement).toString());

    const itemCountChanged = previousItemCount.current !== data.nodes.length;
    if (itemCountChanged) {
      const initialTransform = fitTransform.k * NODE_SIZE < MIN_FITTED_NODE_SIZE
        ? focusedTreeTransform(layout, data, size.width, size.height)
        : fitTransform;
      const animate = previousItemCount.current !== null && !reduceMotion;
      svg.interrupt("tree-zoom");
      if (animate) {
        svg.transition("tree-zoom").duration(ZOOM_TRANSITION_MS).call(zoomBehavior.transform, initialTransform);
      } else {
        svg.call(zoomBehavior.transform, initialTransform);
      }
      previousItemCount.current = data.nodes.length;
    }

    const clips = clipsLayer
      .selectAll<SVGClipPathElement, LayoutNode>("clipPath.node-clip")
      .data(layout.nodes, (node) => node.item.id);
    clips.exit().remove();
    const clipEnter = clips.enter().append("clipPath").attr("class", "node-clip");
    clipEnter.append("rect");
    clipEnter
      .merge(clips)
      .attr("id", (node) => `node-clip-${node.item.id}`)
      .select("rect")
      .attr("x", -NODE_HALF)
      .attr("y", -NODE_HALF)
      .attr("width", NODE_SIZE)
      .attr("height", NODE_SIZE)
      .attr("rx", 14);

    const edgeJoin = linksLayer
      .selectAll<SVGGElement, LayoutEdge>("g.tree-edge")
      .data(layout.edges, (edge) => `${edge.src}-${edge.dst}`);
    edgeJoin.exit().transition().duration(exitTransitionMs).style("opacity", "0").remove();
    const edgeEnter = edgeJoin.enter().append("g").attr("class", "tree-edge").style("opacity", "0");
    edgeEnter.append("path").attr("class", "edge-line");
    edgeEnter.append("path").attr("class", "edge-hit");
    edgeEnter
      .selectAll<SVGPathElement, LayoutEdge>("path")
      .attr("d", (edge) => collapsedPath(previousPositions.current.get(edge.src) ?? edge.source));
    const edgeMerged = edgeEnter.merge(edgeJoin);
    edgeMerged
      .attr("class", (edge) => {
        const precision = edge.evidence.confidence.precision;
        const tone = colorBy === "truth"
          ? edge.correct ? "is-correct" : "is-wrong"
          : precision !== null && precision >= 0.85 ? "is-sure" : "is-unsure";
        return `tree-edge ${tone}${edge.semantic ? " is-semantic" : ""}`;
      })
      .attr("role", "img")
      .attr("aria-label", (edge) => edgeAriaLabel(edge, colorBy))
      .on("pointerenter", (event: PointerEvent, edge) => {
        const bounds = containerRef.current?.getBoundingClientRect();
        if (!bounds) return;
        setTooltip({ x: event.clientX - bounds.left + 14, y: event.clientY - bounds.top + 14, text: edge.explain });
      })
      .on("pointermove", (event: PointerEvent, edge) => {
        const bounds = containerRef.current?.getBoundingClientRect();
        if (!bounds) return;
        setTooltip({ x: event.clientX - bounds.left + 14, y: event.clientY - bounds.top + 14, text: edge.explain });
      })
      .on("pointerleave", () => setTooltip(null))
      .transition()
      .duration(transitionMs)
      .style("opacity", "1");
    edgeMerged
      .selectAll<SVGPathElement, LayoutEdge>("path")
      .transition()
      .duration(transitionMs)
      .attr("d", linkPath);

    const labelJoin = labelsLayer
      .selectAll<SVGGElement, LayoutEdge>("g.edge-label")
      .data(layout.edges, (edge) => `${edge.src}-${edge.dst}`);
    labelJoin.exit().transition().duration(exitTransitionMs).style("opacity", "0").remove();
    const labelEnter = labelJoin
      .enter()
      .append("g")
      .attr("class", "edge-label")
      .attr("aria-hidden", "true")
      .style("opacity", "0");
    labelEnter
      .append("rect")
      .attr("class", "edge-label-halo")
      .attr("y", -13)
      .attr("height", 26)
      .attr("rx", 13)
      .style("fill", "none")
      .style("stroke-width", `${EDGE_LABEL_HALO_WIDTH}px`)
      .style("paint-order", "stroke");
    labelEnter.append("rect").attr("class", "edge-label-pill").attr("y", -13).attr("height", 26).attr("rx", 13);
    labelEnter.append("text").attr("dy", "0.35em").attr("text-anchor", "middle");
    const labelMerged = labelEnter.merge(labelJoin);
    labelMerged
      .attr("class", (edge) => {
        const precision = edge.evidence.confidence.precision;
        const tone = colorBy === "truth"
          ? edge.correct ? "is-correct" : "is-wrong"
          : precision !== null && precision >= 0.85 ? "is-sure" : "is-unsure";
        return `edge-label ${tone}`;
      });
    labelMerged
      .select<SVGRectElement>("rect.edge-label-halo")
      .style("stroke", labelHaloColor);
    labelMerged
      .selectAll<SVGRectElement, LayoutEdge>("rect")
      .attr("x", (edge) => -labelWidth(edgePillText(edge, colorBy)) / 2)
      .attr("width", (edge) => labelWidth(edgePillText(edge, colorBy)));
    labelMerged.select("text").text((edge) => labelText(edgePillText(edge, colorBy)));
    labelMerged
      .transition()
      .duration(transitionMs)
      .style("opacity", "1")
      .attr("transform", (edge) => {
        const position = labelPosition(edge);
        return `translate(${position.x},${position.y})`;
      });

    const nodeJoin = nodesLayer
      .selectAll<SVGGElement, LayoutNode>("g.tree-node")
      .data(layout.nodes, (node) => node.item.id);
    nodeJoin.exit().transition().duration(exitTransitionMs).style("opacity", "0").remove();

    const nodeEnter = nodeJoin
      .enter()
      .append("g")
      .attr("class", "tree-node")
      .attr("role", "button")
      .attr("tabindex", 0)
      .style("opacity", "0")
      .attr("transform", (node) => {
        const parentPosition = node.item.predicted_parent
          ? previousPositions.current.get(node.item.predicted_parent)
          : undefined;
        const start = parentPosition ?? node;
        return `translate(${start.x},${start.y})`;
      });
    const card = nodeEnter.append("g").attr("class", "node-card");
    card.append("rect").attr("class", "node-glow").attr("x", -57).attr("y", -57).attr("width", 114).attr("height", 114).attr("rx", 21);
    card.append("rect").attr("class", "node-backdrop").attr("x", -51).attr("y", -51).attr("width", 102).attr("height", 102).attr("rx", 17);
    card.append("image").attr("x", -NODE_HALF).attr("y", -NODE_HALF).attr("width", NODE_SIZE).attr("height", NODE_SIZE).attr("preserveAspectRatio", "xMidYMid slice");
    card.append("rect").attr("class", "node-border").attr("x", -NODE_HALF).attr("y", -NODE_HALF).attr("width", NODE_SIZE).attr("height", NODE_SIZE).attr("rx", 14);
    card.append("text").attr("class", "node-id").attr("y", 67).attr("text-anchor", "middle");
    card.append("title");

    const nodeMerged = nodeEnter.merge(nodeJoin);
    nodeMerged
      .attr("class", (node) =>
        `tree-node${node.item.id === data.newest_id ? " is-newest" : ""}${node.item.id === selectedId ? " is-selected" : ""}`,
      )
      .attr("aria-label", (node) => `Open image ${node.item.id}`)
      .on("click", (event: MouseEvent, node) => {
        event.stopPropagation();
        if (draggedRef.current) {
          event.preventDefault();
          return;
        }
        onSelect(node.item, event.currentTarget as SVGGElement);
      })
      .on("keydown", (event: KeyboardEvent, node) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect(node.item, event.currentTarget as SVGGElement);
        }
      });
    nodeEnter
      .filter((node) => node.item.id === data.newest_id)
      .select("g.node-card")
      .classed("pop-in", true);
    nodeMerged
      .select("image")
      .attr("href", (node) => node.item.thumb)
      .attr("clip-path", (node) => `url(#node-clip-${node.item.id})`);
    nodeMerged.select("text.node-id").text((node) => captions.get(node.item.id) ?? rootLabel);
    nodeMerged
      .select("title")
      .text((node) => node.item.root && rootTitle
        ? `${rootTitle} · ${node.item.id}`
        : `${node.item.edit ? `${node.item.edit} · ` : ""}${node.item.id}`);
    nodeMerged
      .transition()
      .duration(transitionMs)
      .style("opacity", "1")
      .attr("transform", (node) => `translate(${node.x},${node.y})`);

    previousPositions.current = new Map(layout.nodes.map((node) => [node.item.id, node]));

    return () => {
      svg.on(".zoom", null);
      svg.interrupt("tree-zoom");
      if (dragResetTimerRef.current !== null) window.clearTimeout(dragResetTimerRef.current);
      dragResetTimerRef.current = null;
      draggedRef.current = false;
    };
  }, [colorBy, data, onSelect, rootLabel, rootTitle, selectedId, size]);

  return (
    <div className="tree-view" ref={containerRef}>
      <svg ref={svgRef} role="img" aria-label="Live image lineage forest">
        <defs className="tree-defs" />
        <g className="viewport">
          <g className="tree-stage">
            <g className="links-layer" />
            <g className="labels-layer" />
            <g className="nodes-layer" />
          </g>
        </g>
      </svg>
      <div className="tree-zoom-overlay">
        <div className="tree-zoom-controls" role="group" aria-label="Tree zoom controls">
          <button type="button" aria-label="Zoom in" onClick={() => changeZoom(1.35)}>+</button>
          <button type="button" aria-label="Zoom out" onClick={() => changeZoom(1 / 1.35)}>−</button>
          <button type="button" aria-label="Fit tree to view" onClick={fitTree}>Fit</button>
        </div>
        <span className={`tree-zoom-hint${showZoomHint ? "" : " is-hidden"}`}>
          scroll to zoom · drag to pan
        </span>
      </div>
      {tooltip && (
        <div className="edge-tooltip" style={{ left: tooltip.x, top: tooltip.y }} role="tooltip">
          {tooltip.text}
        </div>
      )}
    </div>
  );
}
