import { hierarchy, select, tree as d3Tree } from "d3";
import { useLayoutEffect, useRef, useState } from "react";
import type { TreeEdge, TreeNode, TreeResponse } from "./api";

const NODE_SIZE = 96;
const NODE_HALF = NODE_SIZE / 2;
const HORIZONTAL_GAP = 150;
const VERTICAL_GAP = 166;
const TRANSITION_MS = 600;

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
  onSelect: (node: TreeNode) => void;
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

  const sortBranch = (branch: HierarchyDatum) => {
    branch.children.sort((left, right) =>
      (left.item?.created_at ?? left.id).localeCompare(right.item?.created_at ?? right.id),
    );
    branch.children.forEach(sortBranch);
  };
  roots.sort((left, right) =>
    (left.item?.created_at ?? left.id).localeCompare(right.item?.created_at ?? right.id),
  );
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

function labelPosition(edge: LayoutEdge): { x: number; y: number } {
  return {
    x: (edge.source.x + edge.target.x) / 2,
    y: (edge.source.y + edge.target.y) / 2,
  };
}

function labelText(label: string): string {
  return label.length > 25 ? `${label.slice(0, 24)}…` : label;
}

function labelWidth(label: string): number {
  return Math.min(196, Math.max(56, labelText(label).length * 7.2 + 22));
}

export default function TreeView({ data, selectedId, onSelect }: TreeViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const previousPositions = useRef(new Map<string, LayoutNode>());
  const [size, setSize] = useState({ width: 0, height: 0 });
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);

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
    // Caption each node with what was done to it; ids mean nothing to a viewer.
    const captions = new Map(data.edges.map((edge) => [edge.dst, edge.label]));
    const svg = select(svgElement).attr("viewBox", `0 0 ${size.width} ${size.height}`);
    const stage = svg.select<SVGGElement>("g.tree-stage");
    const clipsLayer = svg.select<SVGDefsElement>("defs.tree-defs");
    const linksLayer = stage.select<SVGGElement>("g.links-layer");
    const labelsLayer = stage.select<SVGGElement>("g.labels-layer");
    const nodesLayer = stage.select<SVGGElement>("g.nodes-layer");

    const contentWidth = Math.max(1, layout.maxX - layout.minX);
    const contentHeight = Math.max(1, layout.maxY - layout.minY);
    const scale = Math.min(1.25, (size.width - 64) / contentWidth, (size.height - 54) / contentHeight);
    const scaledHeight = contentHeight * scale;
    const top = Math.max(26, (size.height - scaledHeight) / 2);
    const translateX = size.width / 2 - ((layout.minX + layout.maxX) / 2) * scale;
    const translateY = top - layout.minY * scale;
    stage
      .transition()
      .duration(TRANSITION_MS)
      .attr("transform", `translate(${translateX},${translateY}) scale(${scale})`);

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
    edgeJoin.exit().transition().duration(240).style("opacity", "0").remove();
    const edgeEnter = edgeJoin.enter().append("g").attr("class", "tree-edge").style("opacity", "0");
    edgeEnter.append("path").attr("class", "edge-line");
    edgeEnter.append("path").attr("class", "edge-hit");
    edgeEnter
      .selectAll<SVGPathElement, LayoutEdge>("path")
      .attr("d", (edge) => collapsedPath(previousPositions.current.get(edge.src) ?? edge.source));
    const edgeMerged = edgeEnter.merge(edgeJoin);
    edgeMerged
      .attr("class", (edge) =>
        `tree-edge ${edge.correct ? "is-correct" : "is-wrong"}${edge.semantic ? " is-semantic" : ""}`,
      )
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
      .duration(TRANSITION_MS)
      .style("opacity", "1");
    edgeMerged
      .selectAll<SVGPathElement, LayoutEdge>("path")
      .transition()
      .duration(TRANSITION_MS)
      .attr("d", linkPath);

    const labelJoin = labelsLayer
      .selectAll<SVGGElement, LayoutEdge>("g.edge-label")
      .data(layout.edges, (edge) => `${edge.src}-${edge.dst}`);
    labelJoin.exit().transition().duration(240).style("opacity", "0").remove();
    const labelEnter = labelJoin.enter().append("g").attr("class", "edge-label").style("opacity", "0");
    labelEnter.append("rect").attr("y", -13).attr("height", 26).attr("rx", 13);
    labelEnter.append("text").attr("dy", "0.35em").attr("text-anchor", "middle");
    const labelMerged = labelEnter.merge(labelJoin);
    labelMerged
      .attr("class", (edge) => `edge-label ${edge.correct ? "is-correct" : "is-wrong"}`)
      .select("rect")
      .attr("x", (edge) => -labelWidth(edge.label) / 2)
      .attr("width", (edge) => labelWidth(edge.label));
    labelMerged.select("text").text((edge) => labelText(edge.label));
    labelMerged
      .transition()
      .duration(TRANSITION_MS)
      .style("opacity", "1")
      .attr("transform", (edge) => {
        const position = labelPosition(edge);
        return `translate(${position.x},${position.y})`;
      });

    const nodeJoin = nodesLayer
      .selectAll<SVGGElement, LayoutNode>("g.tree-node")
      .data(layout.nodes, (node) => node.item.id);
    nodeJoin.exit().transition().duration(240).style("opacity", "0").remove();

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
        onSelect(node.item);
      })
      .on("keydown", (event: KeyboardEvent, node) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect(node.item);
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
    nodeMerged.select("text.node-id").text((node) => captions.get(node.item.id) ?? "original");
    nodeMerged
      .select("title")
      .text((node) => `${node.item.edit ? `${node.item.edit} · ` : ""}${node.item.id}`);
    nodeMerged
      .transition()
      .duration(TRANSITION_MS)
      .style("opacity", "1")
      .attr("transform", (node) => `translate(${node.x},${node.y})`);

    previousPositions.current = new Map(layout.nodes.map((node) => [node.item.id, node]));
  }, [data, onSelect, selectedId, size]);

  return (
    <div className="tree-view" ref={containerRef}>
      <svg ref={svgRef} role="img" aria-label="Live image lineage forest">
        <defs className="tree-defs" />
        <g className="tree-stage">
          <g className="links-layer" />
          <g className="labels-layer" />
          <g className="nodes-layer" />
        </g>
      </svg>
      {tooltip && (
        <div className="edge-tooltip" style={{ left: tooltip.x, top: tooltip.y }} role="tooltip">
          {tooltip.text}
        </div>
      )}
    </div>
  );
}
