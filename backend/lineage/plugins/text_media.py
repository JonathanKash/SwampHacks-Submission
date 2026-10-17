"""Text media plug-in: stable fingerprints, asymmetric edit cost, and labels.

The direction signal is information loss.  Deleting words is a cheap edit, while
the reverse direction would have to invent them, so words newly present in the
child carry ten times the weight of words discarded from the parent.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import math
import re
from typing import Iterable

import numpy as np

from lineage.types import CostResult, Fingerprint


TEXT_WEIGHTS: dict[str, float] = {
    "added": 3.0,
    "removed": 0.3,
    "length": 1.0,
    "reorder": 0.2,
    "edit_op": 0.05,
    "semantic_offset": 2.0,
    # Rewritten-but-related texts keep ~half their words (Jaccard ~0.5) while unrelated
    # ones share only stop words (~0.05); scale 2.0 puts the first below the root
    # threshold (3.5) and the second above it.
    "semantic_scale": 2.0,
}

_WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|[\r\n]+")


@dataclass
class TextData:
    id: str
    text: str
    words: list[str]
    sentences: list[str]
    shingles: set[str]


def _words(text: str) -> list[str]:
    """Lowercase word tokens; punctuation and underscores are separators."""
    return _WORD_RE.findall(text.lower())


def _shingles(words: list[str]) -> set[str]:
    if not words:
        return set()
    width = min(3, len(words))
    return {" ".join(words[i : i + width]) for i in range(len(words) - width + 1)}


def simhash64(shingles: Iterable[str]) -> int:
    """Stable 64-bit SimHash (Python's process-salted ``hash`` is not used)."""
    values = sorted(set(shingles))
    if not values:
        return 0
    scores = [0] * 64
    for shingle in values:
        digest = hashlib.blake2b(shingle.encode("utf-8"), digest_size=8, person=b"lineage-text").digest()
        value = int.from_bytes(digest, "big")
        for bit in range(64):
            scores[bit] += 1 if value & (1 << bit) else -1
    result = 0
    for bit, score in enumerate(scores):
        if score >= 0:
            result |= 1 << bit
    return result


def minhash_code(shingles: Iterable[str]) -> np.ndarray:
    """Return 128 four-bit MinHashes packed into a 64-byte uint8 array."""
    values = sorted(set(shingles))
    nibbles: list[int] = []
    for seed in range(128):
        person = f"txt-mh-{seed:03d}".encode("ascii")
        minimum = min(
            (int.from_bytes(hashlib.blake2b(value.encode("utf-8"), digest_size=8, person=person).digest(), "big")
             for value in values),
            default=(1 << 64) - 1,
        )
        nibbles.append(minimum & 0xF)
    bits = [(nibble >> shift) & 1 for nibble in nibbles for shift in (3, 2, 1, 0)]
    return np.packbits(bits)


def _jaccard(a: set[str], b: set[str]) -> float:
    union = a | b
    return len(a & b) / len(union) if union else 1.0


def _missing_in_order(source: list[str], other: list[str]) -> list[str]:
    """Multiset subtraction while retaining source order for readable evidence."""
    missing = Counter(source) - Counter(other)
    result: list[str] = []
    for word in source:
        if missing[word]:
            result.append(word)
            missing[word] -= 1
    return result


def _sentence_words(sentence: str) -> list[str]:
    return _words(sentence)


def _sentence_key(sentence: str) -> str:
    return " ".join(_sentence_words(sentence))


def _absent_sentences(source: list[str], target: list[str]) -> list[str]:
    """Find whole sentences, but do not call an ordinary shortening a deletion."""
    target_sets = [set(_sentence_words(sentence)) for sentence in target]
    target_keys = {_sentence_key(sentence) for sentence in target}
    absent: list[str] = []
    for sentence in source:
        key = _sentence_key(sentence)
        if not key or key in target_keys:
            continue
        words = set(_sentence_words(sentence))
        best_overlap = max((_jaccard(words, candidate) for candidate in target_sets), default=0.0)
        if best_overlap < 0.5:
            absent.append(sentence)
    return absent


def _sentence_disorder(a: list[str], b: list[str]) -> float:
    """Kendall-style inversion fraction among sentences shared verbatim."""
    b_positions: dict[str, list[int]] = {}
    for index, sentence in enumerate(b):
        b_positions.setdefault(_sentence_key(sentence), []).append(index)
    used: Counter[str] = Counter()
    order: list[int] = []
    for sentence in a:
        key = _sentence_key(sentence)
        occurrence = used[key]
        positions = b_positions.get(key, [])
        if occurrence < len(positions):
            order.append(positions[occurrence])
            used[key] += 1
    if len(order) < 2:
        return 0.0
    inversions = sum(order[i] > order[j] for i in range(len(order)) for j in range(i + 1, len(order)))
    return inversions / (len(order) * (len(order) - 1) / 2)


def _quoted(words: list[str]) -> str:
    return ", ".join(repr(word) for word in words[:12])


def _reasons(
    len_a: int,
    len_b: int,
    added_words: list[str],
    removed_words: list[str],
    jaccard_words: float,
    jaccard_shingles: float,
    disorder: float,
    semantic: bool,
) -> list[str]:
    reasons: list[str] = []
    if removed_words:
        reasons.append(
            f"{len(removed_words)} of the parent's {len_a} words are missing here "
            f"(removed: {_quoted(removed_words)})"
        )
    if added_words:
        reasons.append(
            f"This text adds {len(added_words)} words the parent does not have ({_quoted(added_words)})"
        )
    if len_a != len_b:
        reasons.append(f"Length went from {len_a} to {len_b} words")
    else:
        reasons.append(f"Both texts contain {len_a} words")
    if removed_words:
        reasons.append(
            f"Deriving the parent from this text would require inventing {len(removed_words)} words"
        )
    if disorder > 0:
        reasons.append(f"Normalized sentence-order disorder is {disorder:.2f}")
    if semantic:
        reasons.append(
            f"Only {jaccard_shingles:.0%} of word shingles overlap; word-set Jaccard is {jaccard_words:.2f}"
        )
    elif len(reasons) < 2:
        reasons.append(f"Word-set Jaccard is {jaccard_words:.2f}")
    return reasons[:5]


class TextMedia:
    name = "text"

    def load(self, item_id: str, source: object) -> TextData:
        if isinstance(source, bytes):
            text = source.decode("utf-8")
        else:
            text = str(source)
        words = _words(text)
        sentences = [part.strip() for part in _SENTENCE_SPLIT_RE.split(text.strip()) if part.strip()]
        return TextData(id=item_id, text=text, words=words, sentences=sentences, shingles=_shingles(words))

    def fingerprint(self, data: TextData) -> Fingerprint:
        return Fingerprint(
            phash=simhash64(data.shingles),
            code=minhash_code(data.shingles),
            embedding=None,
        )

    def cost(self, a: TextData, b: TextData) -> CostResult:
        word_set_a, word_set_b = set(a.words), set(b.words)
        jaccard_words = _jaccard(word_set_a, word_set_b)
        jaccard_shingles = _jaccard(a.shingles, b.shingles)
        added_words = _missing_in_order(b.words, a.words)
        removed_words = _missing_in_order(a.words, b.words)
        len_a, len_b = len(a.words), len(b.words)

        added = len(added_words) / max(1, len_b)
        removed = len(removed_words) / max(1, len_a)
        length_growth = max(0.0, math.log(max(1, len_b) / max(1, len_a)))

        near_identical_words = jaccard_words >= 0.9
        disorder = _sentence_disorder(a.sentences, b.sentences) if near_identical_words else 0.0
        removed_sentences = _absent_sentences(a.sentences, b.sentences)
        added_sentences = _absent_sentences(b.sentences, a.sentences)

        ops: list[str] = []
        if removed_sentences:
            ops.append("removed_sentence")
        if len_b <= 0.85 * len_a and not removed_sentences:
            ops.append("shortened")
        similar_length = 0.85 <= len_b / max(1, len_a) <= 1.15
        if 0.5 <= jaccard_words < 0.95 and similar_length and not removed_sentences and not added_sentences:
            ops.append("reworded")
        if added_sentences:
            ops.append("added_sentence")
        if disorder > 0:
            ops.append("reordered")

        semantic = jaccard_shingles < 0.15
        reasons = _reasons(
            len_a,
            len_b,
            added_words,
            removed_words,
            jaccard_words,
            jaccard_shingles,
            disorder,
            semantic,
        )
        features: dict[str, object] = {
            "added_words": added_words[:12],
            "removed_words": removed_words[:12],
            "len_a": len_a,
            "len_b": len_b,
            "jaccard_words": jaccard_words,
            "jaccard_shingles": jaccard_shingles,
            "ops": ["restyle"] if semantic else ops,
            "media": "text",
            "reasons": reasons,
            "removed_sentence_words": sum(len(_sentence_words(sentence)) for sentence in removed_sentences),
            "removed_sentence_count": len(removed_sentences),
            "added_sentence_count": len(added_sentences),
            "sentence_disorder": disorder,
        }

        # Edits destroy information: a child normally has less.  Therefore a -> b
        # pays heavily for words b gains, but only lightly for words b discards.
        if semantic:
            semantic_cost = TEXT_WEIGHTS["semantic_offset"] + TEXT_WEIGHTS["semantic_scale"] * (
                1.0 - jaccard_words
            )
            terms = {
                "added": 0.0,
                "removed": 0.0,
                "length": 0.0,
                "reorder": 0.0,
                "edit_ops": 0.0,
                "semantic": semantic_cost,
            }
        else:
            terms = {
                "added": TEXT_WEIGHTS["added"] * added,
                "removed": TEXT_WEIGHTS["removed"] * removed,
                "length": TEXT_WEIGHTS["length"] * length_growth,
                "reorder": TEXT_WEIGHTS["reorder"] * disorder,
                "edit_ops": TEXT_WEIGHTS["edit_op"] * len(ops),
            }
        return CostResult(
            total=float(sum(terms.values())),
            semantic=semantic,
            terms=terms,
            features=features,  # CostResult's legacy annotation describes image-only values.
        )

    def explain(self, result: CostResult) -> tuple[str, str]:
        features = result.features
        ops = features.get("ops", [])
        if result.semantic or "restyle" in ops:
            return "rewritten", "rewritten (matched by meaning)"
        if "removed_sentence" in ops:
            count = int(features.get("removed_sentence_count", 1))
            words = int(features.get("removed_sentence_words", 0))
            noun = "a sentence" if count == 1 else f"{count} sentences"
            return "-sentence", f"removed {noun} ({words} words)"
        if "added_sentence" in ops:
            return "+sentence", "added a sentence"
        if "shortened" in ops:
            len_a = int(features.get("len_a", 0))
            len_b = int(features.get("len_b", 0))
            percent = round(100 * (len_a - len_b) / max(1, len_a))
            return f"shorter {percent}%", f"shortened by {percent}%"
        if "reworded" in ops:
            removed = list(features.get("removed_words", []))
            added = list(features.get("added_words", []))
            if removed and len(removed) == len(added):
                changes = ", ".join(f"{old!r} -> {new!r}" for old, new in zip(removed[:4], added[:4]))
                return "reworded", f"reworded: {changes}"
            pieces: list[str] = []
            if removed:
                pieces.append(f"removed {_quoted(removed)}")
            if added:
                pieces.append(f"added {_quoted(added)}")
            return "reworded", "reworded: " + "; ".join(pieces)
        if "reordered" in ops:
            return "reordered", "reordered sentences"
        return "copy", "near-identical copy"
