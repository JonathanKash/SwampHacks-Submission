"""Image plug-in 1/3: fingerprint(item) -> compact codes for candidate search.

- 64-bit pHash (DCT of a 32x32 grayscale thumbnail, top-left 8x8, > median).
- 512-bit sign-binarized CLIP ViT-B/32 embedding (open_clip, CPU). CLIP is loaded
  lazily on first use; if open_clip/torch are missing we degrade to pHash only.

Also owns image loading (`load_image_data`) so every module sees the same
downscaled pixels.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from lineage import config
from lineage.types import Fingerprint, ImageData

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")


def load_rgb(path: Path | str, max_side: int = config.MAX_SIDE) -> np.ndarray:
    """Decode an image file to an (H, W, 3) uint8 RGB array, downscaled to max_side."""
    img = Image.open(path).convert("RGB")
    w, h = img.size
    scale = max_side / max(w, h)
    if scale < 1.0:
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)
    return np.asarray(img)


def phash(gray: np.ndarray) -> int:
    """64-bit perceptual hash of a grayscale uint8 image."""
    small = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    dct = cv2.dct(small)[:8, :8]
    bits = (dct > np.median(dct)).flatten()
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return value


class ClipEmbedder:
    """Lazy wrapper around open_clip ViT-B/32. embed() returns a unit-norm float32 vector."""

    def __init__(self, model_name: str = "ViT-B-32", pretrained: str = "openai") -> None:
        self.model_name = model_name
        self.pretrained = pretrained
        self._model = None
        self._preprocess = None
        self.available: bool | None = None  # unknown until first use

    def _load(self) -> bool:
        if self.available is not None:
            return self.available
        try:
            import open_clip  # noqa: WPS433 (lazy import on purpose)
            import torch

            torch.set_num_threads(max(1, torch.get_num_threads()))
            model, _, preprocess = open_clip.create_model_and_transforms(
                self.model_name, pretrained=self.pretrained
            )
            model.eval()
            self._model, self._preprocess = model, preprocess
            self.available = True
        except Exception as exc:  # pragma: no cover - depends on local install
            print(f"[fingerprint] CLIP unavailable ({exc!r}); using pHash only")
            self.available = False
        return self.available

    def embed(self, rgb: np.ndarray) -> np.ndarray | None:
        if not self._load():
            return None
        import torch

        tensor = self._preprocess(Image.fromarray(rgb)).unsqueeze(0)
        with torch.no_grad():
            feats = self._model.encode_image(tensor)[0].float().numpy()
        norm = np.linalg.norm(feats)
        return (feats / norm).astype(np.float32) if norm > 0 else feats.astype(np.float32)


def binarize(embedding: np.ndarray) -> np.ndarray:
    """Sign-binarize an embedding into packed bits (512 dims -> 64 uint8 bytes)."""
    return np.packbits(embedding > 0)


def _cached_embedding(path: Path, rgb: np.ndarray, embedder: ClipEmbedder) -> np.ndarray | None:
    """Embeddings are deterministic per file, so cache them on disk keyed by path+mtime+size.
    This makes repeated eval runs (cost tuning) take seconds instead of minutes."""
    stat = path.stat()
    key = hashlib.sha1(f"{path.resolve()}|{stat.st_mtime_ns}|{stat.st_size}".encode()).hexdigest()
    cache_file = config.DATA_DIR / ".cache" / "clip" / f"{key}.npy"
    if cache_file.exists():
        return np.load(cache_file)
    embedding = embedder.embed(rgb)
    if embedding is not None:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        np.save(cache_file, embedding)
    return embedding


def load_image_data(item_id: str, path: Path | str, embedder: ClipEmbedder | None) -> ImageData:
    path = Path(path)
    rgb = load_rgb(path)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    embedding = _cached_embedding(path, rgb, embedder) if embedder is not None else None
    return ImageData(id=item_id, rgb=rgb, gray=gray, embedding=embedding, phash=phash(gray))


def fingerprint(data: ImageData) -> Fingerprint:
    """Plug-in entry point: compact codes from already-decoded image data."""
    code = binarize(data.embedding) if data.embedding is not None else None
    return Fingerprint(phash=data.phash, code=code, embedding=data.embedding)
