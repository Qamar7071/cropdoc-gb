"""ONNX export with a built-in parity check, plus a CPU latency/size benchmark.

Lesson learned (logged in docs/decisions.md, D9): a freshly created wrapper module starts in
*training* mode, and the exporter may keep that mode for the whole model. BatchNorm then gets
frozen with the statistics of the dummy input, and the exported model ignores most of the image.
We therefore force eval mode explicitly AND compare ONNX Runtime with PyTorch on random inputs
after every export, failing loudly on any mismatch.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn

from cropdoc.utils import get_logger, write_json

log = get_logger("cropdoc.export")


def export_and_verify(
    module: nn.Module, path: Path, output_names: list[str], atol: float = 1e-3, input_size: int = 224
) -> Path:
    """Export ``module`` (eval mode) to ONNX and check ONNX Runtime matches PyTorch on random inputs."""
    import onnxruntime as ort

    module = module.eval()
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        module,
        torch.randn(1, 3, input_size, input_size),
        str(path),
        input_names=["image"],
        output_names=output_names,
        dynamic_axes={"image": {0: "N"}, **{name: {0: "N"} for name in output_names}},
        opset_version=17,
        training=torch.onnx.TrainingMode.EVAL,
        dynamo=False,
    )
    check = torch.randn(3, 3, input_size, input_size)
    with torch.inference_mode():
        expected = module(check)
    expected = expected if isinstance(expected, tuple) else (expected,)
    session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    actual = session.run(output_names, {"image": check.numpy()})
    for name, e, a in zip(output_names, expected, actual, strict=True):
        diff = float(np.abs(e.numpy() - a).max())
        scale = float(np.abs(e.numpy()).max()) + 1e-6
        if diff > atol * max(1.0, scale):
            path.unlink(missing_ok=True)
            raise RuntimeError(
                f"ONNX parity failed for '{name}': max abs diff {diff:.3g} (scale {scale:.3g})"
            )
    return path


def benchmark(onnx_path: Path, runs: int = 50, threads: int | None = None) -> dict:
    """Median single-image latency on CPU with ONNX Runtime, and the file size."""
    import onnxruntime as ort

    options = ort.SessionOptions()
    if threads:
        options.intra_op_num_threads = threads
    session = ort.InferenceSession(str(onnx_path), options, providers=["CPUExecutionProvider"])
    image = np.random.default_rng(0).normal(size=(1, 3, 224, 224)).astype(np.float32)
    for _ in range(5):
        session.run(None, {"image": image})
    timings = []
    for _ in range(runs):
        start = time.perf_counter()
        session.run(None, {"image": image})
        timings.append((time.perf_counter() - start) * 1000)
    return {
        "file": str(onnx_path),
        "size_mb": round(onnx_path.stat().st_size / 1e6, 2),
        "latency_ms_median": round(float(np.median(timings)), 2),
        "latency_ms_p90": round(float(np.percentile(timings, 90)), 2),
        "runs": runs,
        "threads": threads or "default",
    }


def main(argv: list[str] | None = None) -> int:
    """``make export``: benchmark the active model (export itself happens in training scripts)."""
    from cropdoc import paths

    parser = argparse.ArgumentParser(description="Benchmark the active ONNX model on this CPU.")
    parser.add_argument("--model", type=Path, default=paths.MODELS_ACTIVE / "model.onnx")
    args = parser.parse_args(argv)
    results = {"one_thread": benchmark(args.model, threads=1), "all_threads": benchmark(args.model)}
    write_json(paths.RESULTS / "export" / "benchmark.json", results)
    log.info("%s", results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
