"""Turn a leaf photo into a Y4M video file that Chromium can use as a fake webcam in e2e tests.

Usage: python make_fake_camera.py <photo.jpg> <out.y4m> [width height cover|contain]
Default: the photo fills a 640x480 landscape frame (webcam). For a phone held upright use
720 1280 contain (the leaf fills the width, like a farmer holding the phone over one leaf).
Converted to YUV 4:2:0, one frame (Chromium loops it).
"""

import sys

import numpy as np
from PIL import Image, ImageOps

W, H = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (640, 480)
mode = sys.argv[5] if len(sys.argv) > 5 else "cover"
source = Image.open(sys.argv[1]).convert("RGB")
if mode == "contain":
    photo = ImageOps.pad(source, (W, H), Image.Resampling.BICUBIC, color=(38, 44, 36))
else:
    photo = ImageOps.fit(source, (W, H), Image.Resampling.BICUBIC)
ycbcr = np.asarray(photo.convert("YCbCr"), dtype=np.float32)
y = ycbcr[:, :, 0].astype(np.uint8)
# 4:2:0 = colour at half resolution: average each 2x2 block
cb = ycbcr[:, :, 1].reshape(H // 2, 2, W // 2, 2).mean(axis=(1, 3)).round().astype(np.uint8)
cr = ycbcr[:, :, 2].reshape(H // 2, 2, W // 2, 2).mean(axis=(1, 3)).round().astype(np.uint8)
with open(sys.argv[2], "wb") as out:
    out.write(f"YUV4MPEG2 W{W} H{H} F15:1 Ip A1:1 C420jpeg\n".encode())
    out.write(b"FRAME\n" + y.tobytes() + cb.tobytes() + cr.tobytes())
