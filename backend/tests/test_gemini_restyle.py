"""Gemini restyle plug-in with a fake client (no network, no key)."""

from __future__ import annotations

import io
from types import SimpleNamespace

import pytest
from PIL import Image

from lineage.plugins import gemini_restyle
from tests.conftest import synthetic_photo


def png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class FakeModels:
    def __init__(self, behaviour: dict[str, object]) -> None:
        self.behaviour = behaviour  # model -> bytes | Exception | None
        self.calls: list[str] = []

    def generate_content(self, model, contents, config):
        self.calls.append(model)
        outcome = self.behaviour.get(model)
        if isinstance(outcome, Exception):
            raise outcome
        parts = []
        if outcome:
            parts.append(SimpleNamespace(inline_data=SimpleNamespace(data=outcome)))
        return SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=parts))])


def test_restyle_returns_image_and_params(photo):
    out = png_bytes(synthetic_photo(3))
    client = SimpleNamespace(models=FakeModels({gemini_restyle.DEFAULT_MODEL: out}))
    img, params = gemini_restyle.restyle(png_bytes(photo), "pop art", client=client)
    assert img.size == synthetic_photo(3).size
    assert params == {"style": "pop art", "model": gemini_restyle.DEFAULT_MODEL}
    assert client.models.calls == [gemini_restyle.DEFAULT_MODEL]


def test_restyle_falls_back_to_next_model(photo, monkeypatch):
    monkeypatch.delenv("GEMINI_IMAGE_MODEL", raising=False)
    out = png_bytes(synthetic_photo(3))
    client = SimpleNamespace(models=FakeModels({
        gemini_restyle.DEFAULT_MODEL: RuntimeError("404 model not found"),
        gemini_restyle.FALLBACK_MODELS[0]: out,
    }))
    _, params = gemini_restyle.restyle(png_bytes(photo), None, client=client)
    assert params["model"] == gemini_restyle.FALLBACK_MODELS[0]
    assert params["style"] == "watercolor"


def test_restyle_raises_when_no_model_returns_an_image(photo):
    client = SimpleNamespace(models=FakeModels({}))
    with pytest.raises(RuntimeError):
        gemini_restyle.restyle(png_bytes(photo), "neon", client=client)


def test_restyle_requires_key_without_client(monkeypatch, photo):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        gemini_restyle.restyle(png_bytes(photo), "neon")


def test_prompt_keeps_composition_and_names_style():
    prompt = gemini_restyle.build_prompt("pixel art")
    assert "pixel art" in prompt and "aspect ratio" in prompt


@pytest.mark.parametrize("style", ["watercolor", "pencil sketch", "oil painting", "pop art", "pixel art", "unknown"])
def test_local_restyle_runs_for_every_style(photo, style):
    from lineage.edits.image_edits import restyle_local

    out, params = restyle_local(photo, style)
    assert out.size == photo.size
    assert params["model"] == "local-opencv"
