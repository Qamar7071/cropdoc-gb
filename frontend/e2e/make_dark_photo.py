"""Make a very dark copy of a leaf photo (for the 'please take another photo' test).

Usage: python make_dark_photo.py <photo.jpg> <out.jpg>
"""

import sys

from PIL import Image, ImageEnhance

ImageEnhance.Brightness(Image.open(sys.argv[1]).convert("RGB")).enhance(0.12).save(sys.argv[2], "JPEG", quality=92)
