import { describe, expect, it } from "vitest";
import { tokenDiff } from "./textDiff";

const words = (s: string) => s.split(/\s+/).filter(Boolean);

describe("tokenDiff", () => {
  it("marks everything as same for identical input", () => {
    const parts = tokenDiff(words("a b c"), words("a b c"));
    expect(parts.every((p) => p.kind === "same")).toBe(true);
    expect(parts.map((p) => p.text)).toEqual(["a", "b", "c"]);
  });

  it("marks a dropped trailing sentence as removed", () => {
    const parts = tokenDiff(words("one two three four"), words("one two"));
    expect(parts.filter((p) => p.kind === "removed").map((p) => p.text)).toEqual(["three", "four"]);
    expect(parts.filter((p) => p.kind === "added")).toHaveLength(0);
  });

  it("pairs a synonym swap as removed + added in place", () => {
    const parts = tokenDiff(words("the big dog ran"), words("the large dog ran"));
    expect(parts.map((p) => `${p.kind}:${p.text}`)).toEqual([
      "same:the",
      "removed:big",
      "added:large",
      "same:dog",
      "same:ran",
    ]);
  });

  it("handles empty sides", () => {
    expect(tokenDiff([], words("x y"))).toEqual([
      { kind: "added", text: "x" },
      { kind: "added", text: "y" },
    ]);
    expect(tokenDiff(words("x"), [])).toEqual([{ kind: "removed", text: "x" }]);
  });

  it("keeps the longest common subsequence (no spurious churn)", () => {
    const parts = tokenDiff(words("a b c d e"), words("a c e"));
    expect(parts.filter((p) => p.kind === "same").map((p) => p.text)).toEqual(["a", "c", "e"]);
    expect(parts.filter((p) => p.kind === "removed").map((p) => p.text)).toEqual(["b", "d"]);
  });
});
