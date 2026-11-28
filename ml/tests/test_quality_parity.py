"""The calibration (ml) and the web app (backend) must measure photo quality identically."""

import numpy as np
from PIL import Image

from app.services.quality import measure as backend_measure
from cropdoc.quality import measure as ml_measure


def test_quality_measurement_is_identical():
    rng = np.random.default_rng(0)
    for size in ((640, 480), (256, 256), (120, 900)):
        image = Image.fromarray(rng.integers(0, 255, (size[1], size[0], 3), dtype=np.uint8))
        assert ml_measure(image) == backend_measure(image)
