# Texture patches for the uniform details, cut straight from the reference art and unwarped into rectangles:
# a curved band in the picture is given by its top and bottom edge polylines (image pixels); columns are sampled
# between them at equal arc length. Output: art/3d/textures/ref_*.png (read by build_details.py).
# .venv\Scripts\python.exe art\3d\extract_ref_textures.py
import os
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', 'source')
OUT = os.path.join(HERE, 'textures')


def resample(poly, n):
    """n points at equal arc length along a polyline."""
    p = np.asarray(poly, np.float64)
    seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))]
    t = np.linspace(0, seg[-1], n)
    return np.stack([np.interp(t, seg, p[:, 0]), np.interp(t, seg, p[:, 1])], 1)


def bilinear(img, x, y):
    h, w = img.shape[:2]
    x = np.clip(x, 0, w - 1.001); y = np.clip(y, 0, h - 1.001)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = (x - x0)[..., None], (y - y0)[..., None]
    a, b = img[y0, x0], img[y0, x0 + 1]
    c, d = img[y0 + 1, x0], img[y0 + 1, x0 + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def unwarp(img, top, bottom, w, h):
    """Band between two polylines -> w x h image (row 0 = top edge, column 0 = first point of the polylines)."""
    t, b = resample(top, w), resample(bottom, w)
    v = np.linspace(0, 1, h)[:, None, None]
    p = t[None] + (b - t)[None] * v
    return bilinear(img, p[..., 0], p[..., 1])


def save(arr, name):
    Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).save(os.path.join(OUT, name))
    print(name, arr.shape[1], 'x', arr.shape[0])


short = np.asarray(Image.open(os.path.join(SRC, 'alexander_ii_short.png')).convert('RGB'), np.float32)
full = np.asarray(Image.open(os.path.join(SRC, 'alexander_ii_full.png')).convert('RGB'), np.float32)
os.makedirs(OUT, exist_ok=True)

# Collar, the wearer's right half (left in the picture): from the piped front edge (column 0) round to the side.
# Top edge just under the white shirt collar, bottom edge on the tunic.
save(unwarp(short,
            top=[(662, 475), (620, 461), (580, 450), (540, 437), (522, 432)],
            bottom=[(668, 561), (630, 550), (580, 532), (540, 520), (500, 508)], w=512, h=256), 'ref_collar.png')

# Belt: the straight run right of the buckle (full figure).
save(unwarp(full, top=[(577, 565), (630, 567)], bottom=[(577, 604), (630, 602)], w=256, h=192), 'ref_belt.png')

# Buckle plate (full figure), its bounding box.
save(unwarp(full, top=[(487, 553), (570, 553)], bottom=[(487, 609), (570, 609)], w=256, h=176), 'ref_buckle.png')

# Cuff flap of the left sleeve (full figure): red-piped gold plate; rows run along the arm towards the hand.
save(unwarp(full, top=[(710, 611), (747, 629)], bottom=[(676, 651), (714, 668)], w=160, h=200), 'ref_cuff_flap.png')
