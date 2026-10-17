import { describe, expect, it } from "vitest";
import type { Evidence, TreeEdge, TreeNode, TreeResponse } from "./api";
import { provenancePath, provenanceSentence } from "./provenance";

const evidence: Evidence = {
  chosen_cost: 0,
  terms: {},
  runner_up: null,
  margin: null,
  confidence: { bucket: null, precision: null, n: 0 },
  measurements: {},
  reasons: [],
};

function node(id: string, parent: string | null): TreeNode {
  return {
    id,
    url: `/images/${id}.png`,
    thumb: `/thumbs/${id}.jpg`,
    edit: null,
    params: {},
    source: "seed",
    created_at: 1,
    predicted_parent: parent,
    correct: true,
    root: parent === null,
    evidence,
  };
}

function edge(src: string, dst: string, explain: string): TreeEdge {
  return { src, dst, label: explain, explain, cost: 0.05, semantic: false, correct: true, evidence };
}

const tree: TreeResponse = {
  version: 1,
  nodes: [node("root", null), node("a", "root"), node("b", "a"), node("x", null)],
  edges: [edge("root", "a", "cropped to 60%"), edge("a", "b", "warm filter")],
  accuracy: { correct: 2, total: 2, pct: 100 },
  newest_id: "b",
};

describe("provenancePath", () => {
  it("walks from the original down to the node, oldest first", () => {
    const steps = provenancePath(tree, "b");
    expect(steps.map((s) => s.node.id)).toEqual(["root", "a", "b"]);
    expect(steps[0].edge).toBeNull();
    expect(steps[2].edge?.explain).toBe("warm filter");
  });

  it("returns just the node for a root", () => {
    expect(provenancePath(tree, "x").map((s) => s.node.id)).toEqual(["x"]);
  });

  it("renders the one-line story", () => {
    expect(provenanceSentence(provenancePath(tree, "b"))).toBe("original → cropped to 60% → warm filter");
  });

  it("never loops on a malformed cyclic payload", () => {
    const cyclic: TreeResponse = {
      ...tree,
      nodes: [node("p", "q"), node("q", "p")],
      edges: [edge("q", "p", "e1"), edge("p", "q", "e2")],
    };
    expect(provenancePath(cyclic, "p").length).toBeLessThanOrEqual(2);
  });
});
