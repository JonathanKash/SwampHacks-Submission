export type TokenDiffPart = {
  kind: "same" | "removed" | "added";
  text: string;
};

/** Keep shared words in order so deletions and additions remain easy to scan. */
export function tokenDiff(a: string[], b: string[]): TokenDiffPart[] {
  const lengths = Array.from({ length: a.length + 1 }, () => Array<number>(b.length + 1).fill(0));

  for (let i = a.length - 1; i >= 0; i -= 1) {
    for (let j = b.length - 1; j >= 0; j -= 1) {
      lengths[i][j] = a[i] === b[j] ? lengths[i + 1][j + 1] + 1 : Math.max(lengths[i + 1][j], lengths[i][j + 1]);
    }
  }

  const result: TokenDiffPart[] = [];
  let i = 0;
  let j = 0;

  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) {
      result.push({ kind: "same", text: a[i] });
      i += 1;
      j += 1;
    } else if (lengths[i + 1][j] >= lengths[i][j + 1]) {
      result.push({ kind: "removed", text: a[i] });
      i += 1;
    } else {
      result.push({ kind: "added", text: b[j] });
      j += 1;
    }
  }

  while (i < a.length) {
    result.push({ kind: "removed", text: a[i] });
    i += 1;
  }
  while (j < b.length) {
    result.push({ kind: "added", text: b[j] });
    j += 1;
  }

  return result;
}
