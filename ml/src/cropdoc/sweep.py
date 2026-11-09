"""Run the experiment matrix, idempotently (``make sweep SWEEP_ARGS="--block B"``).

Every (experiment, seed) has a run id derived from its settings. Finished runs (``metrics.json``
present) are skipped; interrupted runs resume from ``last.pt``. So on Colab you can simply re-run the
same cell after a disconnect. Runs live in ``output.runs_dir`` (set CROPDOC_RUNS to a Drive folder).

    python -m cropdoc.sweep --block A            # run block A (all seeds)
    python -m cropdoc.sweep --status             # done / missing per block
    python -m cropdoc.sweep --block B --dry-run  # list what would run
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import yaml

from cropdoc import paths
from cropdoc.config import load_config, run_id
from cropdoc.utils import get_logger

log = get_logger("cropdoc.sweep")


def runs_dir(config: dict) -> Path:
    override = os.environ.get("CROPDOC_RUNS")
    path = Path(override or config["output"]["runs_dir"])
    return path if path.is_absolute() else paths.ROOT / path


def planned_runs(blocks: list[str] | None = None, overrides: list[str] | None = None) -> list[dict]:
    """[{block, experiment, seed, config, run_id, run_dir, done}] for the requested blocks."""
    sweep = yaml.safe_load((paths.CONFIGS / "sweep.yaml").read_text())
    rows = []
    for block, experiments in sweep["blocks"].items():
        if blocks and block not in blocks:
            continue
        for experiment in experiments:
            for seed in sweep["seeds"]:
                config = load_config(
                    f"experiments/{experiment}.yaml", overrides=[f"seed={seed}", *(overrides or [])]
                )
                rid = run_id(config)
                folder = runs_dir(config) / rid
                rows.append(
                    {
                        "block": block,
                        "experiment": experiment,
                        "seed": seed,
                        "config": config,
                        "run_id": rid,
                        "run_dir": folder,
                        "done": (folder / "metrics.json").exists(),
                    }
                )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--block", action="append", help="block letter(s) from sweep.yaml (default: all)")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("overrides", nargs="*")
    args = parser.parse_args(argv)
    rows = planned_runs(args.block, args.overrides)
    if args.status or args.dry_run:
        for block in sorted({r["block"] for r in rows}):
            block_rows = [r for r in rows if r["block"] == block]
            unique = {r["run_id"]: r["done"] for r in block_rows}
            print(f"block {block}: {sum(unique.values())}/{len(unique)} runs done")
            if args.dry_run:
                for r in block_rows:
                    print(
                        f"  {'done' if r['done'] else 'todo'}  {r['experiment']:<22} seed {r['seed']}  {r['run_id']}"
                    )
        return 0
    from cropdoc.train import train_run  # imported late: --status works without torch installed

    seen = set()
    for r in rows:
        if r["done"] or r["run_id"] in seen:
            continue
        seen.add(r["run_id"])
        log.info("running %s (block %s, seed %d) → %s", r["experiment"], r["block"], r["seed"], r["run_dir"])
        train_run(r["config"], r["run_dir"])
    log.info("sweep finished; run `make eval` to aggregate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
