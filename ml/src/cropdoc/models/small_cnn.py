"""A small CNN trained from scratch (the "no pretraining" baseline).

Intuition: each block = two 3×3 convolutions (detect local patterns such as edges, spots, rings)
+ BatchNorm (keeps training stable) + ReLU (non-linearity) + max-pooling (halves the image size
so later layers see larger regions). Four blocks take 224×224 down to 14×14 feature maps.
"""

from __future__ import annotations

from torch import nn


def conv_block(in_ch: int, out_ch: int) -> nn.Sequential:
    return nn.Sequential(
        nn.Conv2d(in_ch, out_ch, 3, padding=1, bias=False),
        nn.BatchNorm2d(out_ch),
        nn.ReLU(inplace=True),
        nn.Conv2d(out_ch, out_ch, 3, padding=1, bias=False),
        nn.BatchNorm2d(out_ch),
        nn.ReLU(inplace=True),
        nn.MaxPool2d(2),
    )


class SmallCNNFeatures(nn.Module):
    """Stem (stride 2) + 4 conv blocks: 224 → 112 → 56 → 28 → 14 → 7 spatial; 256 channels."""

    out_channels = 256

    def __init__(self, widths: tuple[int, int, int, int] = (32, 64, 128, 256)):
        super().__init__()
        self.stem = nn.Sequential(
            nn.Conv2d(3, widths[0], 3, stride=2, padding=1, bias=False),
            nn.BatchNorm2d(widths[0]),
            nn.ReLU(inplace=True),
        )
        chans = (widths[0],) + tuple(widths)
        self.blocks = nn.Sequential(*[conv_block(chans[i], chans[i + 1]) for i in range(4)])
        self.out_channels = widths[-1]

    def forward(self, x):
        return self.blocks(self.stem(x))
