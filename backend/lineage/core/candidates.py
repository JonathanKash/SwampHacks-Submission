"""Core 1/3: candidate search from fingerprints.

Why: with n items there are n*(n-1) directed pairs. Costs are expensive (ORB +
RANSAC + warps), so we only compute them for the top-k most similar items per
item, judged by cheap Hamming distances on the fingerprints. Edits change a
few pHash bits and a few CLIP sign bits, so true relatives are almost always
within the top-k even for a pool of hundreds.
"""

from __future__ import annotations

import numpy as np

from lineage.types import Fingerprint


def hamming_phash(a: int, b: int) -> int:
    """Number of differing bits between two 64-bit pHash integers (0..64)."""
    return (a ^ b).bit_count()


def hamming_code(a: np.ndarray, b: np.ndarray) -> int:
    """Number of differing bits between two packed-bit uint8 arrays of equal length
    (np.packbits output; 64 bytes = 512 bits for CLIP codes). Range 0..8*len."""
    return int(np.unpackbits(np.bitwise_xor(a, b)).sum())


def distance(a: Fingerprint, b: Fingerprint, phash_weight: float = 1.0) -> float:
    """Combined normalized distance in [0, 1 + phash_weight]:
        phash_weight * hamming_phash / 64 + hamming_code / (8 * len(code))
    If either code is None (CLIP unavailable), use the pHash part only."""
    d = phash_weight * hamming_phash(a.phash, b.phash) / 64.0
    if a.code is not None and b.code is not None:
        d += hamming_code(a.code, b.code) / (8.0 * len(a.code))
    return d


def top_k_candidates(
    fingerprints: dict[str, Fingerprint], k: int = 8, phash_weight: float = 1.0
) -> dict[str, list[str]]:
    """For every item id, the ids of its k nearest other items by distance(),
    nearest first. Never includes the item itself. When there are fewer than k
    other items, returns all of them. Deterministic: ties broken by id order.

    The engine turns this into directed candidate pairs in BOTH directions
    (i -> j and j -> i for every j in result[i]), so direction is decided by
    cost, never by this function."""
    ids = sorted(fingerprints)
    result: dict[str, list[str]] = {}
    for i in ids:
        # Sorting (distance, id) tuples gives nearest-first with id tie-breaks.
        scored = sorted((distance(fingerprints[i], fingerprints[j], phash_weight), j) for j in ids if j != i)
        result[i] = [j for _, j in scored[:k]]
    return result
