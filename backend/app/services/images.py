"""Safe handling of uploaded photos.

Checks, in order: size limit → real image decode with Pillow (the extension is ignored) →
JPEG/PNG only → decompression-bomb guard → rotate per EXIF → copy pixels into a fresh image so
EXIF/GPS and any other metadata are dropped.
"""

from __future__ import annotations

import io
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"JPEG", "PNG"}


class ImageRejected(ValueError):
    """Raised when an upload is not acceptable; ``status_code`` is the HTTP status to return."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def check_size(data: bytes, max_bytes: int) -> None:
    """Reject empty or oversized uploads."""
    if not data:
        raise ImageRejected("The file is empty.", 400)
    if len(data) > max_bytes:
        raise ImageRejected(f"File too large: max {max_bytes // (1024 * 1024)} MB.", 413)


def load_clean_image(data: bytes, max_bytes: int, max_pixels: int) -> Image.Image:
    """Validate an upload and return a clean RGB image without any metadata."""
    check_size(data, max_bytes)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            probe = Image.open(io.BytesIO(data))
            image_format = probe.format
            width, height = probe.size
            if image_format not in ALLOWED_FORMATS:
                raise ImageRejected("Only JPG and PNG images are supported.", 415)
            if width * height > max_pixels:
                raise ImageRejected("Image dimensions are too large.", 413)
            probe.verify()  # detects truncated/corrupted files
            image = Image.open(io.BytesIO(data))
            image.load()
    except ImageRejected:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ImageRejected("Image dimensions are too large.", 413) from exc
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise ImageRejected("The file is not a valid JPG or PNG image (it may be corrupted).", 415) from exc

    image = ImageOps.exif_transpose(image)  # phone photos: apply rotation, then drop EXIF
    return _flatten_to_rgb(image)


def _flatten_to_rgb(image: Image.Image) -> Image.Image:
    """Drop metadata and transparency: paste onto white, return a brand-new RGB image."""
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    rgb = image.convert("RGB")
    clean = Image.new("RGB", rgb.size)
    clean.paste(rgb)
    return clean


def downscale(image: Image.Image, max_side: int) -> Image.Image:
    """Shrink so the longest side is at most ``max_side`` (never enlarges)."""
    copy = image.copy()
    copy.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return copy
