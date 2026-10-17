"""The fixed edit menu, as pure functions on PIL images.

Used by the synthetic chain generator (Phase 0), the pre-seed script, and the
server side of the /edit tablet page. Every edit returns the new image plus the
parameters that were used, so the generator can store them as ground truth.

AI restyle (Gemini) lives in plugins/gemini_restyle.py because it needs a network
call and a billing-enabled key. `restyle_local` below is the offline stand-in the
server uses when Gemini is unavailable, so the demo never dead-ends.
"""

from __future__ import annotations

import io
import math
import random

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

EDIT_TYPES: tuple[str, ...] = ("crop", "rotate", "filter", "caption", "jpeg")
FILTER_KINDS: tuple[str, ...] = ("warm", "cool", "brighter", "darker", "contrast", "grayscale")

CAPTIONS: tuple[str, ...] = (
    "me irl", "no context", "art history final boss", "when the deadline is 8am",
    "Gators", "this is fine", "SwampHacks XII", "mood", "vibes", "certified classic",
)


def crop(img: Image.Image, rng: random.Random, fraction: float | None = None) -> tuple[Image.Image, dict]:
    """Keep a random sub-rectangle covering `fraction` of the area (default 0.45-0.85)."""
    w, h = img.size
    fraction = fraction if fraction is not None else rng.uniform(0.45, 0.85)
    scale = math.sqrt(fraction)
    # Never ask for more than the image has: tiny images (after many crops) just keep everything.
    cw, ch = min(w, max(32, int(w * scale))), min(h, max(32, int(h * scale)))
    x0 = rng.randint(0, w - cw)
    y0 = rng.randint(0, h - ch)
    box = (x0, y0, x0 + cw, y0 + ch)
    return img.crop(box), {"fraction": round(fraction, 3), "box": list(box)}


def _largest_inner_rect(w: int, h: int, angle_rad: float) -> tuple[float, float]:
    """Largest axis-aligned rectangle inside a w x h rectangle rotated by angle_rad."""
    width_is_longer = w >= h
    side_long, side_short = (w, h) if width_is_longer else (h, w)
    sin_a, cos_a = abs(math.sin(angle_rad)), abs(math.cos(angle_rad))
    if side_short <= 2.0 * sin_a * cos_a * side_long or abs(sin_a - cos_a) < 1e-10:
        x = 0.5 * side_short
        wr, hr = (x / sin_a, x / cos_a) if width_is_longer else (x / cos_a, x / sin_a)
    else:
        cos_2a = cos_a * cos_a - sin_a * sin_a
        wr, hr = (w * cos_a - h * sin_a) / cos_2a, (h * cos_a - w * sin_a) / cos_2a
    return wr, hr


def rotate(img: Image.Image, rng: random.Random, angle: float | None = None) -> tuple[Image.Image, dict]:
    """Rotate by a small angle (3-12 degrees either way) and crop away the empty corners."""
    if angle is None:
        angle = rng.choice([-1, 1]) * rng.uniform(3.0, 12.0)
    w, h = img.size
    rotated = img.rotate(angle, resample=Image.Resampling.BICUBIC, expand=False)
    wr, hr = _largest_inner_rect(w, h, math.radians(angle))
    cw, ch = int(wr), int(hr)
    x0, y0 = (w - cw) // 2, (h - ch) // 2
    return rotated.crop((x0, y0, x0 + cw, y0 + ch)), {"angle": round(angle, 2)}


def color_filter(img: Image.Image, rng: random.Random, kind: str | None = None) -> tuple[Image.Image, dict]:
    """Apply one named color filter."""
    kind = kind or rng.choice(FILTER_KINDS)
    if kind == "grayscale":
        out = ImageOps.grayscale(img).convert("RGB")
    elif kind in ("warm", "cool"):
        r, g, b = img.split()
        shift = rng.randint(18, 40)
        if kind == "warm":
            r = r.point(lambda v: min(255, v + shift))
            b = b.point(lambda v: max(0, v - shift))
        else:
            b = b.point(lambda v: min(255, v + shift))
            r = r.point(lambda v: max(0, v - shift))
        out = Image.merge("RGB", (r, g, b))
    elif kind == "brighter":
        out = ImageEnhance.Brightness(img).enhance(rng.uniform(1.25, 1.6))
    elif kind == "darker":
        out = ImageEnhance.Brightness(img).enhance(rng.uniform(0.55, 0.8))
    elif kind == "contrast":
        out = ImageEnhance.Contrast(img).enhance(rng.uniform(1.4, 1.9))
    else:
        raise ValueError(f"unknown filter kind: {kind}")
    return out, {"kind": kind}


def caption(img: Image.Image, rng: random.Random, text: str | None = None) -> tuple[Image.Image, dict]:
    """Draw white text with a black outline across the bottom of the image."""
    text = text or rng.choice(CAPTIONS)
    out = img.copy()
    w, h = out.size
    size = max(14, int(h * 0.08))
    font = ImageFont.load_default(size=size)
    draw = ImageDraw.Draw(out)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = max(4, (w - tw) // 2)
    y = max(4, h - th - int(h * 0.06))
    draw.text((x, y), text, font=font, fill="white", stroke_width=max(2, size // 10), stroke_fill="black")
    return out, {"text": text}


def jpeg(img: Image.Image, rng: random.Random, quality: int | None = None) -> tuple[Image.Image, dict]:
    """Re-encode as a low-quality JPEG (quality 8-25) and decode again."""
    quality = quality if quality is not None else rng.randint(8, 25)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    buf.seek(0)
    return Image.open(buf).convert("RGB"), {"quality": quality}


def apply_edit(img: Image.Image, edit_type: str, rng: random.Random, **params) -> tuple[Image.Image, dict]:
    """Dispatch by name. Returns (new_image, params_used)."""
    img = img.convert("RGB")
    if edit_type == "crop":
        return crop(img, rng, **params)
    if edit_type == "rotate":
        return rotate(img, rng, **params)
    if edit_type == "filter":
        return color_filter(img, rng, **params)
    if edit_type == "caption":
        return caption(img, rng, **params)
    if edit_type == "jpeg":
        return jpeg(img, rng, **params)
    raise ValueError(f"unknown edit type: {edit_type}")


LOCAL_STYLES: tuple[str, ...] = ("watercolor", "pencil sketch", "oil painting", "pop art", "pixel art")


def restyle_local(img: Image.Image, style: str | None = None) -> tuple[Image.Image, dict]:
    """Offline stylization (OpenCV / Pillow). Used when the Gemini call fails.
    Strong enough that ORB registration usually breaks, which is exactly the case
    the semantic (CLIP) edge exists for."""
    style = style if style in LOCAL_STYLES else "watercolor"
    bgr = cv2.cvtColor(np.asarray(img.convert("RGB")), cv2.COLOR_RGB2BGR)
    if style == "watercolor":
        out = cv2.stylization(bgr, sigma_s=60, sigma_r=0.45)
    elif style == "pencil sketch":
        _, out = cv2.pencilSketch(bgr, sigma_s=60, sigma_r=0.07, shade_factor=0.05)
    elif style == "oil painting":
        out = cv2.edgePreservingFilter(bgr, flags=cv2.RECURS_FILTER, sigma_s=80, sigma_r=0.6)
        out = cv2.detailEnhance(out, sigma_s=10, sigma_r=0.15)
    elif style == "pop art":
        quant = (bgr // 64) * 64 + 32  # 4 levels per channel
        edges = cv2.adaptiveThreshold(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), 255,
                                      cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 9, 5)
        out = cv2.bitwise_and(quant, quant, mask=edges)
    else:  # pixel art
        h, w = bgr.shape[:2]
        small = cv2.resize(bgr, (max(8, w // 12), max(8, h // 12)), interpolation=cv2.INTER_AREA)
        out = cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)
    result = Image.fromarray(cv2.cvtColor(out, cv2.COLOR_BGR2RGB))
    return result, {"style": style, "model": "local-opencv"}
