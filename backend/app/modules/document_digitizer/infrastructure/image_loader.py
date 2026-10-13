"""Image Ingestion, Decoding, and Format Validation Infrastructure (Module 7)."""

import io
import base64
from pathlib import Path
from typing import Union, Tuple
from PIL import Image


class ImageLoader:
    """Robust image loader supporting raw bytes, base64 strings, and filesystem paths."""

    @staticmethod
    def from_bytes(data: bytes) -> Image.Image:
        try:
            img = Image.open(io.BytesIO(data))
            img.load()
            return img
        except Exception as exc:
            raise ValueError(f"Unable to parse image bytes: {exc}")

    @staticmethod
    def from_base64(b64_str: str) -> Image.Image:
        # Strip header like 'data:image/png;base64,' if present
        if "," in b64_str:
            b64_str = b64_str.split(",", 1)[1]
        try:
            raw_bytes = base64.b64decode(b64_str)
            return ImageLoader.from_bytes(raw_bytes)
        except Exception as exc:
            raise ValueError(f"Invalid base64 image data: {exc}")

    @staticmethod
    def from_file_path(path: Union[str, Path]) -> Image.Image:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Image file not found at: {p}")
        try:
            img = Image.open(p)
            img.load()
            return img
        except Exception as exc:
            raise ValueError(f"Unable to open image file {p}: {exc}")

