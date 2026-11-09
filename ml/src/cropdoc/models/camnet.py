"""CamNet: any feature extractor + global-average-pool + dropout + linear layer.

* ``forward(x)`` → class scores (logits), used for training.
* ``forward_with_cams(x)`` → (logits, CAMs). CAM for class c = Σ_k w[c, k] · feature_map[k].
  Because the head is linear after average pooling, this is exactly Grad-CAM (see tests).
* ``embed(x)`` → the pooled feature vector (used for duplicate detection and linear probes).
"""

from __future__ import annotations

import torch
from torch import nn

from cropdoc.models.small_cnn import SmallCNNFeatures

TIMM_FEATURE_DIMS = {"mobilenetv3_large_100": 960, "mobilenetv3_small_100": 576, "resnet18": 512}


class CamNet(nn.Module):
    """Backbone (returns a B×C×h×w feature map) + CAM-friendly classification head."""

    def __init__(self, backbone: nn.Module, feature_dim: int, num_classes: int, dropout: float = 0.2):
        super().__init__()
        self.backbone = backbone
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(feature_dim, num_classes)

    def feature_map(self, x: torch.Tensor) -> torch.Tensor:
        """Last convolutional feature map (B, C, h, w)."""
        if hasattr(self.backbone, "forward_features"):
            return self.backbone.forward_features(x)
        return self.backbone(x)

    def embed(self, x: torch.Tensor) -> torch.Tensor:
        """Pooled features (B, C)."""
        return self.pool(self.feature_map(x)).flatten(1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.fc(self.dropout(self.embed(x)))

    def forward_with_cams(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """(logits, CAMs of every class). Dropout is inactive in eval mode."""
        features = self.feature_map(x)
        logits = self.fc(self.pool(features).flatten(1))
        cams = torch.einsum("ck,bkhw->bchw", self.fc.weight, features)
        return logits, cams

    def head_parameters(self) -> list[nn.Parameter]:
        return list(self.fc.parameters())

    def freeze_backbone(self, trainable_tail_blocks: int = 0) -> None:
        """Freeze the backbone; optionally keep its last ``trainable_tail_blocks`` blocks trainable."""
        self.backbone.requires_grad_(False)
        blocks = getattr(self.backbone, "blocks", None) or getattr(self.backbone, "stages", None)
        if trainable_tail_blocks and blocks is not None:
            for block in list(blocks)[-trainable_tail_blocks:]:
                block.requires_grad_(True)
        elif trainable_tail_blocks and hasattr(self.backbone, "layer4"):  # resnet
            for name in ["layer4", "layer3"][:trainable_tail_blocks]:
                getattr(self.backbone, name).requires_grad_(True)

    def unfreeze(self) -> None:
        self.requires_grad_(True)


class OnnxCamWrapper(nn.Module):
    """Export wrapper: input ``image`` → outputs (``logits``, ``cams``)."""

    def __init__(self, model: CamNet):
        super().__init__()
        self.model = model

    def forward(self, image: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        return self.model.forward_with_cams(image)


def build_model(
    arch: str,
    num_classes: int,
    pretrained: bool = True,
    dropout: float = 0.2,
    weights_file: str | None = None,
) -> CamNet:
    """Create a CamNet. ``arch`` is 'small_cnn' or a timm name (mobilenetv3_large_100, resnet18, ...)."""
    if arch == "small_cnn":
        features = SmallCNNFeatures()
        return CamNet(features, features.out_channels, num_classes, dropout=0.3)

    import timm

    backbone = timm.create_model(arch, pretrained=False, num_classes=0)
    if pretrained:
        from cropdoc.models.weights import weight_path

        state = torch.load(weights_file or weight_path(arch), map_location="cpu", weights_only=True)
        state = {
            k: v for k, v in state.items() if not k.startswith(("classifier.", "fc.", "conv_head.", "head."))
        }
        missing, unexpected = backbone.load_state_dict(state, strict=False)
        bad_missing = [k for k in missing if not k.startswith(("conv_head", "classifier", "fc", "head"))]
        if bad_missing or unexpected:
            raise RuntimeError(
                f"weights do not match {arch}: missing={bad_missing[:5]} unexpected={unexpected[:5]}"
            )
    feature_dim = TIMM_FEATURE_DIMS.get(arch) or backbone.num_features
    return CamNet(backbone, feature_dim, num_classes, dropout=dropout)
