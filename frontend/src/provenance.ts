import type { TreeEdge, TreeNode, TreeResponse } from "./api";

export interface ProvenanceStep {
  node: TreeNode;
  /** The edge that produced this node from the previous step (null for the original). */
  edge: TreeEdge | null;
}

/**
 * The chain from a family's original down to `nodeId`, oldest first.
 * This is the one-sentence provenance story an auditor wants: "source → cropped to 60% → warm filter".
 */
export function provenancePath(tree: TreeResponse, nodeId: string): ProvenanceStep[] {
  const nodes = new Map(tree.nodes.map((node) => [node.id, node]));
  const incoming = new Map(tree.edges.map((edge) => [edge.dst, edge]));
  const steps: ProvenanceStep[] = [];
  const seen = new Set<string>();
  let current: string | null = nodeId;
  while (current && !seen.has(current)) {
    seen.add(current);
    const node = nodes.get(current);
    if (!node) break;
    const edge: TreeEdge | null = incoming.get(current) ?? null;
    steps.push({ node, edge });
    current = edge ? edge.src : null;
  }
  return steps.reverse();
}

/** "original → cropped to 60% → warm filter" */
export function provenanceSentence(steps: ProvenanceStep[]): string {
  return steps.map((step) => (step.edge ? step.edge.explain : "original")).join(" → ");
}
