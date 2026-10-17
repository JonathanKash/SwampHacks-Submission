"""Phase 5 text plug-in tests: fingerprints, direction, labels, and core reuse."""

from __future__ import annotations

import random

import numpy as np

from lineage.core.candidates import hamming_code, hamming_phash
from lineage.core.engine import Engine
from lineage.plugins.text_media import TextMedia, minhash_code, simhash64


S1 = "During autumn workshop, our patient team learned how careful sketches guide every difficult engineering decision."
S2 = "In spite of rain, students carried a large number of bright sensors across the crowded campus."
S3 = "They worked in order to test each circuit, recording results, and sharing clear notes before midnight."
S4 = "By morning, the final prototype answered every question, and the excited group presented its discovery confidently."


def text_chain() -> list[str]:
    original = " ".join((S1, S2, S3, S4))
    removed_sentence = " ".join((S1, S2, S3))
    reworded = " ".join(
        (
            S1,
            "Despite rain, students carried many bright sensors across the crowded campus.",
            "They worked to test each circuit, recording results, and sharing clear notes before midnight.",
        )
    )
    shortened = " ".join(
        (
            "During workshop, our team learned how sketches guide every engineering decision.",
            "Despite students carried many sensors across the campus.",
            "They worked to test circuit, results, and sharing notes before midnight.",
        )
    )
    # The last edit adds a new sentence while consolidating repeated wording.  It
    # remains lossy, preserving the model's central parent -> child direction.
    added_sentence = " ".join(
        (
            "During workshop, our team learned sketches guide engineering decision.",
            "Despite students carried sensors across campus.",
            "They worked to test circuit, results, sharing notes before midnight.",
            "Observers applauded loudly.",
        )
    )
    return [original, removed_sentence, reworded, shortened, added_sentence]


UNRELATED = (
    "Volcanic basalt cools beneath an ocean ridge while mineral crystals record pressure inside the mantle. "
    "Astronomers meanwhile calculate distant orbital periods from radio pulses emitted by a rotating neutron star."
)


def loaded_chain() -> tuple[TextMedia, list]:
    media = TextMedia()
    return media, [media.load(f"v{i}", text) for i, text in enumerate(text_chain())]


def test_text_chain_costs_labels_and_reasons():
    media, chain = loaded_chain()
    expected_labels = ["-sentence", "reworded", "shorter 25%", "+sentence"]
    related_costs: list[float] = []

    for index, (parent, child) in enumerate(zip(chain, chain[1:])):
        forward = media.cost(parent, child)
        reverse = media.cost(child, parent)
        assert forward.total < reverse.total
        assert media.explain(forward)[0] == expected_labels[index]
        assert len(media.explain(forward)[0]) <= 28
        assert forward.features["reasons"]
        assert all(isinstance(reason, str) for reason in forward.features["reasons"])
        related_costs.append(forward.total)

        if index:
            grandparent = chain[index - 1]
            assert forward.total < media.cost(grandparent, child).total

    unrelated = media.cost(chain[0], media.load("other", UNRELATED))
    assert unrelated.semantic is True
    assert unrelated.features["ops"] == ["restyle"]
    assert unrelated.total > max(related_costs)
    assert media.explain(unrelated) == ("rewritten", "rewritten (matched by meaning)")


def test_stable_fingerprint_shapes_and_related_distances():
    media, chain = loaded_chain()
    unrelated = media.load("other", UNRELATED)
    original_fp = media.fingerprint(chain[0])
    related_fp = media.fingerprint(chain[1])
    unrelated_fp = media.fingerprint(unrelated)

    assert isinstance(simhash64(chain[0].shingles), int)
    assert 0 <= simhash64(chain[0].shingles) < 2**64
    code = minhash_code(chain[0].shingles)
    assert isinstance(code, np.ndarray)
    assert code.dtype == np.uint8
    assert len(code) == code.nbytes == 64
    assert original_fp.embedding is None
    assert hamming_phash(original_fp.phash, related_fp.phash) < hamming_phash(
        original_fp.phash, unrelated_fp.phash
    )
    assert hamming_code(original_fp.code, related_fp.code) < hamming_code(
        original_fp.code, unrelated_fp.code
    )


def test_shared_engine_recovers_shuffled_text_chain():
    texts = text_chain()
    order = list(range(len(texts)))
    random.Random(7).shuffle(order)
    engine = Engine(media=TextMedia(), use_clip=False)
    for index in order:
        engine.add_item(f"v{index}", texts[index])

    tree = engine.build_tree()
    assert tree.parent == {
        "v0": None,
        "v1": "v0",
        "v2": "v1",
        "v3": "v2",
        "v4": "v3",
    }
