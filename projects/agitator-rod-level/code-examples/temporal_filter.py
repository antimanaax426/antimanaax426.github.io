"""Rolling-median filter, and the no-level decision (submerged / below_rod / fog / unknown).

Excerpt from rod_level_v16.py (V1.6.4). Function bodies are copied verbatim from the source;
unrelated code (CLI, drawing, batch output) is omitted.
"""
from __future__ import annotations

from collections import deque

import cv2
import numpy as np

from boundary_detection import STRIP_H, STRIP_W, Params
from roi_rectification import order_endpoints, rectify_roi

class LevelFilter:
    """Rolling median of confident per-frame levels, with a short hold-over.

    When no level can be given, the window is checked in this order:
      submerged  - camera / rod under liquid (blurred, not white)
      below_rod  - rod clearly visible and fully exposed: level under the ROI bottom, or empty tank
      fog        - view washed out by fog
      unknown    - none of the above
    """

    SITUATIONS = (('submerged', 'sub_ratio'), ('exposed', 'below_ratio'), ('fog', 'fog_ratio'))
    STATUS = {'submerged': 'submerged', 'exposed': 'below_rod', 'fog': 'fog'}

    def __init__(self, fps: float, p: Params):
        self.p = p
        self.window = max(3, int(round(p.window_seconds * fps)))
        self.hold = int(round(p.hold_seconds * fps))
        self.buf: deque = deque(maxlen=self.window)
        self.flags = {k: deque(maxlen=self.window) for k, _ in self.SITUATIONS}
        self.last = None
        self.since_valid = 10 ** 9

    def update(self, level: float, conf: float, exposed: bool = False, flags: dict | None = None):
        """flags: per-frame evidence from view_flags. Without it, only 'exposed' is used."""
        if flags is None:
            flags = dict(exposed=exposed)
        low = conf < self.p.min_conf
        self.buf.append(None if low else level)
        for k, dq in self.flags.items():
            dq.append(bool(flags.get(k, False)) and low)
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
        for k, ratio in self.SITUATIONS:
            dq = self.flags[k]
            if len(dq) >= 3 and sum(dq) >= getattr(self.p, ratio) * len(dq):
                return None, self.STATUS[k], None
        return None, 'unknown', None


def view_features(frame: np.ndarray, roi: dict, probe: np.ndarray) -> dict:
    """Appearance numbers used when no level is found (see LevelFilter.update)."""
    strip, _ = rectify_roi(frame, roi, STRIP_H, STRIP_W)
    L = cv2.cvtColor(strip, cv2.COLOR_BGR2LAB)[..., 0].astype(np.float32)
    half = STRIP_H // 2
    low = L[half:, 6:STRIP_W - 6]
    gx, gy = cv2.Sobel(low, cv2.CV_32F, 1, 0), cv2.Sobel(low, cv2.CV_32F, 0, 1)
    return dict(probe_l=probe_brightness(frame, probe),
                low_l=float(np.median(low)),
                low_grad=float(np.sqrt(gx * gx + gy * gy).mean()),
                top_l=float(np.median(L[:half, 6:STRIP_W - 6])))


def view_flags(v: dict, p: Params) -> dict:
    """Per-frame evidence for each no-level situation (evaluated in this order by LevelFilter)."""
    pl = v['probe_l']
    clear = bool(np.isfinite(pl))
    submerged = clear and v['low_grad'] < p.sub_grad_max and v['low_l'] < p.sub_low_max and pl < p.sub_probe_max
    return dict(submerged=submerged,
                exposed=clear and pl < p.probe_white and not submerged,
                fog=clear and pl >= p.probe_white and v['top_l'] >= p.fog_top_min)


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


def rod_exposed(probe_l: float, p: Params) -> bool:
    """Clear view under the rod: the probe region is neither washed out by fog nor white slurry."""
    return bool(np.isfinite(probe_l) and probe_l < p.probe_white)
