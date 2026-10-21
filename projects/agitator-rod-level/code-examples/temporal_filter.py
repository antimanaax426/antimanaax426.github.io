"""Rolling-median filter and the below_rod / no_surface decision with the probe region.

Excerpt from rod_level_v16.py (V1.6.3). Function bodies are copied verbatim from the source;
unrelated code (CLI, drawing, batch output) is omitted.
"""
from __future__ import annotations

from collections import deque

import cv2
import numpy as np

from boundary_detection import Params
from roi_rectification import order_endpoints

class LevelFilter:
    """Rolling median of confident per-frame levels, with a short hold-over.

    Statuses: ok / hold / below_rod (rod clearly visible and fully exposed for most of the
    window: level is under the ROI bottom, or the tank is empty) / no_surface (view unclear).
    """

    def __init__(self, fps: float, p: Params):
        self.p = p
        self.window = max(3, int(round(p.window_seconds * fps)))
        self.hold = int(round(p.hold_seconds * fps))
        self.buf: deque = deque(maxlen=self.window)
        self.exposed: deque = deque(maxlen=self.window)
        self.last = None
        self.since_valid = 10 ** 9

    def update(self, level: float, conf: float, exposed: bool = False):
        """exposed: this frame shows a clear view with no slurry on the rod (see rod_exposed)."""
        self.buf.append(level if conf >= self.p.min_conf else None)
        self.exposed.append(bool(exposed) and conf < self.p.min_conf)
        valid = [v for v in self.buf if v is not None]
        need = max(3, int(np.ceil(self.window * self.p.min_valid_ratio)))
        if len(valid) >= need:
            self.last = float(np.median(valid))
            self.since_valid = 0
            spread = float(np.percentile(valid, 75) - np.percentile(valid, 25))
            return self.last, 'ok', spread
        self.since_valid += 1
        if self.last is not None and self.since_valid <= self.hold:
            return self.last, 'hold', None
        if len(self.exposed) >= 3 and sum(self.exposed) >= self.p.below_ratio * len(self.exposed):
            return None, 'below_rod', None
        return None, 'no_surface', None


def rod_exposed(probe_l: float, p: Params) -> bool:
    """Clear view under the rod: the probe region is neither washed out by fog nor white slurry."""
    return bool(np.isfinite(probe_l) and probe_l < p.probe_white)


def probe_quad(roi: dict) -> np.ndarray:
    """Image region used to tell 'rod clearly exposed' from 'view washed out'.

    Default: the lower half of the ROI (50%..0% along the shaft), moved one ROI width further
    down in the image, so it sits just under the rod. Override with 'probe_quad' (4 [x, y]
    points) in the ROI JSON.
    """
    if 'probe_quad' in roi:
        return np.float32(roi['probe_quad'])
    tl, tr, br, bl = order_endpoints(roi)
    mid_a, mid_b = (tl + bl) / 2, (tr + br) / 2
    axis = (bl + br) / 2 - (tl + tr) / 2
    normal = np.float32([-axis[1], axis[0]]) / (np.linalg.norm(axis) + 1e-6)
    if normal[1] < 0:  # point down the image
        normal = -normal
    width = float(np.linalg.norm(tr - tl))
    shift = normal * width * 1.1
    return np.float32([mid_a, mid_b, br, bl]) + shift


def probe_brightness(frame: np.ndarray, quad: np.ndarray) -> float:
    """Median Lab L inside the probe region (clipped to the frame)."""
    h, w = frame.shape[:2]
    q = np.clip(quad, [0, 0], [w - 1, h - 1]).astype(np.int32)
    x, y, bw, bh = cv2.boundingRect(q)
    if bw < 2 or bh < 2:
        return float('nan')
    crop = frame[y:y + bh, x:x + bw]
    mask = np.zeros((bh, bw), np.uint8)
    cv2.fillPoly(mask, [q - [x, y]], 255)
    L = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB)[..., 0]
    return float(np.median(L[mask > 0]))
