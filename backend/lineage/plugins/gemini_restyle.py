"""AI restyle via the Gemini image-editing models (the "restyle" menu edit).

Model ids were checked against ai.google.dev/gemini-api/docs/image-generation on
2026-10-16 (via the Gemini CLI): the current image models are
gemini-nano-banana-2.1 (recommended), gemini-3.1-flash-image and gemini-3-pro-image.
Override with GEMINI_IMAGE_MODEL in .env. The key is GEMINI_API_KEY (read by the
SDK itself). Image models have no free tier: a billing-enabled key is required.

We ask the model to keep composition, framing and aspect ratio and only change
the rendering style, so the restyled child still registers to its parent when
it can, and otherwise falls back to the semantic (CLIP) edge.
"""

from __future__ import annotations

import io
import os

from PIL import Image

STYLES: dict[str, str] = {
    "watercolor": "a loose watercolor painting with visible paper texture and bleeding colors",
    "pencil sketch": "a detailed graphite pencil sketch on white paper",
    "oil painting": "a thick impasto oil painting with visible brushstrokes",
    "pop art": "a bold pop-art screen print with flat colors and halftone dots",
    "pixel art": "16-bit pixel art with a limited palette",
    "stained glass": "a stained-glass window with black lead lines",
    "neon": "a neon-lit cyberpunk scene at night",
    "claymation": "a claymation stop-motion scene with soft studio lighting",
}
DEFAULT_MODEL = "gemini-nano-banana-2.1"
FALLBACK_MODELS = ("gemini-3.1-flash-image", "gemini-3-pro-image")


def build_prompt(style: str) -> str:
    description = STYLES.get(style, style)
    return (
        f"Re-render this exact image as {description}. Keep the composition, subject, "
        "framing, crop and aspect ratio identical. Change only the artistic rendering style. "
        "Return only the edited image."
    )


def _extract_image(response) -> bytes | None:
    """First inline image in a generate_content response, or None."""
    for candidate in getattr(response, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            inline = getattr(part, "inline_data", None)
            if inline is not None and getattr(inline, "data", None):
                data = inline.data
                return data if isinstance(data, (bytes, bytearray)) else bytes(data)
    return None


def restyle(image_bytes: bytes, style: str | None = None, client=None) -> tuple[Image.Image, dict]:
    """Return (restyled PIL image, params). Raises RuntimeError on API failure.

    `client` is injectable for tests; by default a google-genai Client that reads
    GEMINI_API_KEY from the environment is created.
    """
    style = style or "watercolor"
    if client is None:
        if not os.getenv("GEMINI_API_KEY"):
            raise RuntimeError("GEMINI_API_KEY is not set")
        from google import genai

        client = genai.Client()
    from google.genai import types

    prompt = build_prompt(style)
    models = [os.getenv("GEMINI_IMAGE_MODEL", DEFAULT_MODEL), *FALLBACK_MODELS]
    last_error: Exception | None = None
    for model in dict.fromkeys(models):  # de-duplicated, order kept
        try:
            response = client.models.generate_content(
                model=model,
                contents=[types.Part.from_bytes(data=image_bytes, mime_type="image/png"), prompt],
                config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
            )
        except Exception as exc:  # try the next model id on any API error
            last_error = exc
            continue
        data = _extract_image(response)
        if data:
            img = Image.open(io.BytesIO(data)).convert("RGB")
            return img, {"style": style, "model": model}
        last_error = RuntimeError(f"{model} returned no image")
    raise RuntimeError(f"Gemini restyle failed: {last_error}")
