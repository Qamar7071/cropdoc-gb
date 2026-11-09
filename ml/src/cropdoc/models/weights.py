"""Pretrained ImageNet weights, downloaded once and verified.

We fetch timm's weight files from its GitHub release assets (reachable even where
download.pytorch.org / huggingface.co are blocked). timm file names end in the first 8 hex digits
of the file's SHA256, which we verify after download.
"""

from __future__ import annotations

import re
import shutil
import urllib.request
from pathlib import Path

from cropdoc import paths
from cropdoc.utils import get_logger, sha256_file

_RELEASES = "https://github.com/huggingface/pytorch-image-models/releases/download"
WEIGHT_URLS: dict[str, str] = {
    "mobilenetv3_large_100": f"{_RELEASES}/v0.1-weights/mobilenetv3_large_100_ra-f55367f5.pth",
    "mobilenetv3_small_100": f"{_RELEASES}/v0.1-weights/mobilenetv3_small_100_lamb-266a294c.pth",
    "resnet18": f"{_RELEASES}/v0.1-rsb-weights/resnet18_a1_0-d63eafa0.pth",
}


def weight_path(arch: str, folder: Path | None = None) -> Path:
    """Local path of the weight file for ``arch`` (downloaded if missing, hash-checked)."""
    url = WEIGHT_URLS[arch]
    folder = folder or paths.WEIGHTS
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / url.rsplit("/", 1)[1]
    if not target.exists():
        get_logger().info("downloading %s weights from %s", arch, url)
        tmp = target.with_suffix(".part")
        with urllib.request.urlopen(url, timeout=120) as response, tmp.open("wb") as out:
            shutil.copyfileobj(response, out)
        tmp.rename(target)
    expected = re.search(r"-([0-9a-f]{8})\.pth$", target.name)
    if expected and not sha256_file(target).startswith(expected.group(1)):
        target.unlink()
        raise RuntimeError(f"checksum mismatch for {target.name}; deleted, please retry")
    return target
