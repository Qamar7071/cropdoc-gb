"""Download the public datasets used by CropDoc GB.

Intuition
---------
* PlantVillage lives in a public GitHub repo with three copies of every photo
  (colour, grayscale, background-removed). We only need the colour photos and the
  background-removed ("segmented") copies, so we use git's *sparse checkout* to
  fetch just those folders. No API keys are needed.
* PlantDoc is a small set of real-world (web) leaf photos. We use it as a public
  "field-like" test set while the Gilgit-Baltistan field photos are being collected.

Usage
-----
    python scripts/download_data.py                 # PlantVillage colour + masks
    python scripts/download_data.py --plantdoc      # also PlantDoc
    python scripts/download_data.py --no-segmented  # colour only (smaller)

Manual fallback (if git is blocked): see data/README.md.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

PLANTVILLAGE_URL = "https://github.com/spMohanty/PlantVillage-Dataset"
PLANTDOC_URL = "https://github.com/pratikkayal/PlantDoc-Dataset"


def run(cmd: list[str], cwd: Path | None = None) -> str:
    """Run a command, echo it, and return stdout (raises on failure)."""
    print("+", " ".join(cmd), flush=True)
    result = subprocess.run(cmd, cwd=cwd, check=True, text=True, capture_output=True)
    return result.stdout.strip()


def sparse_clone(url: str, dest: Path, paths: list[str]) -> str:
    """Shallow, blob-less, sparse clone of ``url`` containing only ``paths``.

    Returns the commit hash so the exact data version is recorded.
    """
    if not (dest / ".git").exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--depth", "1", "--filter=blob:none", "--sparse", url, str(dest)])
    run(["git", "sparse-checkout", "set", *paths], cwd=dest)
    return run(["git", "rev-parse", "HEAD"], cwd=dest)


def record_source(name: str, url: str, commit: str, paths: list[str]) -> None:
    """Append/overwrite an entry in data/raw/SOURCES.json (provenance log)."""
    sources_file = RAW / "SOURCES.json"
    sources = json.loads(sources_file.read_text()) if sources_file.exists() else {}
    sources[name] = {
        "url": url,
        "commit": commit,
        "paths": paths,
        "downloaded_utc": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    sources_file.write_text(json.dumps(sources, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--no-segmented", action="store_true", help="skip background-removed copies")
    parser.add_argument("--plantdoc", action="store_true", help="also download PlantDoc")
    parser.add_argument("--plantdoc-only", action="store_true", help="only download PlantDoc")
    args = parser.parse_args(argv)

    if not args.plantdoc_only:
        pv_paths = ["raw/color"] + ([] if args.no_segmented else ["raw/segmented"])
        commit = sparse_clone(PLANTVILLAGE_URL, RAW / "PlantVillage-Dataset", pv_paths)
        record_source("plantvillage", PLANTVILLAGE_URL, commit, pv_paths + ["leaf-map.json"])
        print(f"PlantVillage ready at commit {commit}")

    if args.plantdoc or args.plantdoc_only:
        pd_paths = ["train", "test"]
        commit = sparse_clone(PLANTDOC_URL, RAW / "PlantDoc-Dataset", pd_paths)
        record_source("plantdoc", PLANTDOC_URL, commit, pd_paths)
        print(f"PlantDoc ready at commit {commit}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
