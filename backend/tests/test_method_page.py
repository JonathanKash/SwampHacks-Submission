"""The method page prints the cost weights as static text; keep it honest against config.py."""

from __future__ import annotations

import re
from pathlib import Path

from lineage import config

PAGE = Path(__file__).resolve().parents[2] / "frontend" / "src" / "MethodPage.tsx"
NAME_TO_KEY = {
    "coverage": "coverage",
    "color residual": "color_residual",
    "blockiness": "blockiness",
    "resolution": "resolution",
    "chroma": "chroma",
    "entropy": "entropy",
    "blobs": "blobs",
    "caption removed": "caption_removed",
    "edit ops": "edit_op",
    "specificity": "specificity",
}


def test_method_page_weights_match_config():
    text = PAGE.read_text(encoding="utf-8")
    rows = dict(re.findall(r'name: "([^"]+)",\s*weight: "([^"]+)"', text))
    assert set(NAME_TO_KEY) <= set(rows), "method page lost a cost-term row"
    for name, key in NAME_TO_KEY.items():
        printed = float(re.match(r"[0-9.]+", rows[name]).group(0))
        assert printed == config.WEIGHTS[key], f"{name}: page says {printed}, config says {config.WEIGHTS[key]}"
    fallback = rows["semantic fallback"]
    assert str(config.WEIGHTS["semantic_offset"]) in fallback and str(config.WEIGHTS["semantic_scale"]) in fallback
