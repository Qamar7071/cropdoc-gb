"""CropDoc GB training and research package.

Modules
-------
paths        central file locations (data, splits, results, models)
utils        seeding, logging, hashing, JSON helpers
data/        dataset download, manifest, duplicate groups, splits, datasets, transforms
models/      small CNN and pretrained backbones with a CAM-friendly head
train        training loop (AMP, AdamW, cosine LR, early stopping, checkpoint/resume)
evaluate     metrics from saved logits, tables, bootstrap CIs
calibration  ECE, reliability diagrams, temperature scaling
ood          max-softmax / energy scores, AUROC, selective prediction
shift        lab-vs-field evaluation, crop-conditioned scoring, few-shot adaptation
explain      Grad-CAM / CAM, CAM-mass-outside-leaf metric
export       ONNX export, parity check, CPU latency benchmark
"""

__version__ = "1.0.0"
