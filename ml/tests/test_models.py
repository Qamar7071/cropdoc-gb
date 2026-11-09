"""Model tests: forward/backward smoke test and the CAM ≡ Grad-CAM property."""

from __future__ import annotations

import torch

from cropdoc.models import build_model
from cropdoc.models.camnet import CamNet
from cropdoc.models.small_cnn import SmallCNNFeatures


def test_small_cnn_forward_backward():
    model = build_model("small_cnn", num_classes=5)
    x = torch.randn(2, 3, 224, 224)
    logits = model(x)
    assert logits.shape == (2, 5)
    logits.sum().backward()
    assert all(p.grad is not None for p in model.parameters() if p.requires_grad)


def test_timm_backbone_without_download_forward_backward():
    model = build_model("mobilenetv3_small_100", num_classes=4, pretrained=False)
    logits, cams = model.forward_with_cams(torch.randn(2, 3, 224, 224))
    assert logits.shape == (2, 4) and cams.shape == (2, 4, 7, 7)
    model(torch.randn(2, 3, 224, 224)).mean().backward()


def grad_cam(model: CamNet, x: torch.Tensor, class_index: int) -> torch.Tensor:
    """Textbook Grad-CAM with autograd: weights = spatial mean of d(score)/d(feature map)."""
    features = model.feature_map(x)
    features.retain_grad()
    score = model.fc(model.pool(features).flatten(1))[:, class_index].sum()
    score.backward()
    weights = features.grad.mean(dim=(2, 3), keepdim=True)
    return torch.relu((weights * features).sum(dim=1))


def test_cam_equals_grad_cam_up_to_scale():
    torch.manual_seed(0)
    features = SmallCNNFeatures(widths=(8, 8, 16, 16))
    model = CamNet(features, 16, num_classes=3).eval()
    x = torch.randn(1, 3, 64, 64)
    _, cams = model.forward_with_cams(x)
    for c in range(3):
        cam = torch.relu(cams[0, c])
        gcam = grad_cam(model, x, c)[0].detach()
        if cam.max() == 0:
            assert gcam.max() == 0
            continue
        # identical after normalizing to [0, 1] (Grad-CAM = CAM / number of spatial cells)
        assert torch.allclose(cam / cam.max(), gcam / gcam.max(), atol=1e-5)


def test_freeze_backbone_keeps_head_and_tail_trainable():
    model = build_model("mobilenetv3_small_100", num_classes=3, pretrained=False)
    model.freeze_backbone(trainable_tail_blocks=2)
    trainable = {
        n.split(".")[1] for n, p in model.named_parameters() if p.requires_grad and n.startswith("backbone")
    }
    assert trainable == {"blocks"}
    assert all(p.requires_grad for p in model.fc.parameters())
    assert not model.backbone.conv_stem.weight.requires_grad
