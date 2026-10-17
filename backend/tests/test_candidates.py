"""Specification for the hand-written core/candidates.py."""

from __future__ import annotations

import numpy as np
import pytest
from lineage.core import candidates
from lineage.types import Fingerprint


def fp(phash: int, code_bits: str | None = None) -> Fingerprint:
    """Build a fingerprint from an int pHash and an optional bit string (padded to 512)."""
    code = None
    if code_bits is not None:
        bits = np.array([int(b) for b in code_bits.ljust(512, "0")], dtype=np.uint8)
        code = np.packbits(bits)
    return Fingerprint(phash=phash, code=code, embedding=None)


# ---- hamming_phash ----------------------------------------------------------

def test_hamming_phash_identical_is_zero():
    assert candidates.hamming_phash(0xDEADBEEF, 0xDEADBEEF) == 0


def test_hamming_phash_counts_differing_bits():
    assert candidates.hamming_phash(0b1011, 0b0001) == 2
    assert candidates.hamming_phash(0, (1 << 64) - 1) == 64


def test_hamming_phash_is_symmetric():
    assert candidates.hamming_phash(12345, 67890) == candidates.hamming_phash(67890, 12345)


# ---- hamming_code -----------------------------------------------------------

def test_hamming_code_identical_is_zero():
    a = np.packbits(np.ones(512, dtype=np.uint8))
    assert candidates.hamming_code(a, a.copy()) == 0


def test_hamming_code_counts_bits_across_bytes():
    a = np.packbits(np.zeros(512, dtype=np.uint8))
    bits = np.zeros(512, dtype=np.uint8)
    bits[[0, 7, 8, 300, 511]] = 1  # five bits spread over different bytes
    b = np.packbits(bits)
    assert candidates.hamming_code(a, b) == 5


def test_hamming_code_all_different_is_512():
    a = np.packbits(np.zeros(512, dtype=np.uint8))
    b = np.packbits(np.ones(512, dtype=np.uint8))
    assert candidates.hamming_code(a, b) == 512


# ---- distance ---------------------------------------------------------------

def test_distance_zero_for_identical():
    a = fp(42, "1010")
    assert candidates.distance(a, fp(42, "1010")) == pytest.approx(0.0)


def test_distance_is_normalized_sum():
    a = fp(0, "0" * 512)
    b = fp(0b111, "1" * 256)  # 3/64 phash bits + 256/512 code bits
    assert candidates.distance(a, b, phash_weight=1.0) == pytest.approx(3 / 64 + 0.5)
    assert candidates.distance(a, b, phash_weight=2.0) == pytest.approx(2 * 3 / 64 + 0.5)


def test_distance_falls_back_to_phash_when_code_missing():
    a = fp(0, None)
    b = fp(0b1111, "1" * 512)
    assert candidates.distance(a, b) == pytest.approx(4 / 64)


# ---- top_k_candidates -------------------------------------------------------

def test_top_k_excludes_self_and_respects_k():
    fps = {f"i{n}": fp(n) for n in range(20)}
    result = candidates.top_k_candidates(fps, k=5)
    assert set(result) == set(fps)
    for item_id, neighbours in result.items():
        assert item_id not in neighbours
        assert len(neighbours) == 5
        assert len(set(neighbours)) == 5


def test_top_k_returns_all_when_pool_is_small():
    fps = {"a": fp(1), "b": fp(2), "c": fp(3)}
    result = candidates.top_k_candidates(fps, k=8)
    assert sorted(result["a"]) == ["b", "c"]


def test_top_k_orders_nearest_first():
    # Distances from 'q' (phash 0): near = 1 bit, mid = 3 bits, far = 10 bits.
    fps = {
        "q": fp(0),
        "far": fp(0b1111111111),
        "near": fp(0b1),
        "mid": fp(0b111),
    }
    assert candidates.top_k_candidates(fps, k=3)["q"] == ["near", "mid", "far"]


def test_top_k_uses_code_distance_too():
    # Same pHash everywhere; only the CLIP codes differ.
    fps = {
        "q": fp(0, "0" * 512),
        "twin": fp(0, "0" * 511 + "1"),
        "cousin": fp(0, "1" * 100),
        "stranger": fp(0, "1" * 400),
    }
    assert candidates.top_k_candidates(fps, k=2)["q"] == ["twin", "cousin"]


def test_top_k_ties_broken_by_id_order():
    fps = {"q": fp(0), "b": fp(1), "a": fp(1), "c": fp(1)}
    assert candidates.top_k_candidates(fps, k=3)["q"] == ["a", "b", "c"]


def test_top_k_single_item():
    assert candidates.top_k_candidates({"only": fp(7)}, k=8) == {"only": []}
