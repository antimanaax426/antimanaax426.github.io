"""Per-frame waterline: slurry probability, tilt shear and threshold-free optimal split.

Excerpt from rod_level_v16.py (V1.6.5). Function bodies are copied verbatim from the source;
unrelated code (CLI, drawing, batch output) is omitted.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from roi_rectification import rectify_roi

STRIP_H = 512  # rows along the shaft, ~0.2% of ROI length each


STRIP_W = 96   # pixels across the shaft


@dataclass
class Params:
    white_lo: float = 222.0     # Lab L (0-255) where slurry evidence starts
    white_hi: float = 236.0     # Lab L where slurry evidence is full
    texture_hi: float = 12.0    # local std above which a pixel counts as textured
    texture_span: float = 8.0
    textured_weight: float = 0.4  # bright but textured pixels still count this much
    margin: int = 6             # columns ignored at each side of the strip
    min_conf: float = 0.6       # per-frame confidence needed to vote (fog/glare frames score ~0.4-0.45)
    window_seconds: float = 10.0
    min_valid_ratio: float = 0.3  # share of confident frames needed in the window
    hold_seconds: float = 10.0  # keep the last level this long when evidence drops out
    probe_white: float = 235.0  # probe region median Lab L at/above this = washed out (fog) or slurry, not a clear view
    below_ratio: float = 0.7    # share of window frames that must show a clear, fully exposed rod for 'below_rod'
    # camera under liquid: lower rod half blurred, but neither it nor the probe region is white
    sub_grad_max: float = 9.5   # mean Lab-L gradient of the lower strip half below this = blurred (dry rod: 10-12)
    sub_low_max: float = 225.0  # lower strip half median L below this = not covered by white slurry
    sub_probe_max: float = 230.0  # probe median L below this = not fog
    sub_ratio: float = 0.7      # share of window frames needed for 'submerged'
    # second check, only once 'submerged': milky liquid blurs the rod more than clear water
    turbid_grad_max: float = 5.5  # lower strip half mean gradient below this = milky (2026-10-12: milky 3-5, clear 6-8)
    turbid_ratio: float = 0.5     # share of the window's submerged frames needed for 'turbid', otherwise 'clear'
    # fog: probe washed out and the upper rod half washed out too (exposed rod above slurry stays dark: L <= ~150)
    fog_top_min: float = 158.0  # upper strip half median L at/above this = upper rod washed out
    fog_ratio: float = 0.5      # share of window frames needed for 'fog'


def slurry_probability(strip: np.ndarray, p: Params) -> np.ndarray:
    """Per-pixel probability that the strip pixel is covered by white slurry."""
    L = cv2.cvtColor(strip, cv2.COLOR_BGR2LAB)[..., 0].astype(np.float32)
    bright = np.clip((L - p.white_lo) / (p.white_hi - p.white_lo), 0, 1)
    mean = cv2.blur(L, (7, 7))
    sd = np.sqrt(np.maximum(cv2.blur(L * L, (7, 7)) - mean * mean, 0))
    flat = np.clip((p.texture_hi - sd) / p.texture_span, 0, 1)
    return bright * np.maximum(flat, p.textured_weight)


def split_rows(row_score: np.ndarray) -> tuple[int, float]:
    """Best split k: rows [0,k) exposed, rows [k,n) covered.

    Minimises the number of rows that disagree with the split (soft counts), which has
    no tunable thresholds. Returns (k, confidence).
    """
    n = len(row_score)
    cum = np.concatenate([[0.0], np.cumsum(row_score)])
    total = cum[-1]
    k = np.arange(n + 1)
    cost = cum + ((n - k) - (total - cum))
    best = int(np.argmin(cost))
    above = float(row_score[:best].mean()) if best > 0 else 0.0
    below = float(row_score[best:].mean()) if best < n else 0.0
    return best, below - above


CENTER_COL = (STRIP_W - 1) / 2.0


_shear_maps: dict = {}


def waterline_row(k: float, col: float, slope: float) -> float:
    """Strip row of the waterline at a column, given its row k on the shaft centre line."""
    return k + slope * (col - CENTER_COL)


def shear(prob: np.ndarray, slope: float) -> np.ndarray:
    """Resample so that each output row follows a waterline of the given slope.

    The liquid surface is horizontal, but in this camera view its intersection with the
    shaft is tilted relative to the ROI cross-lines. Output row k = waterline whose centre
    is at strip row k.
    """
    if abs(slope) < 1e-6:
        return prob
    maps = _shear_maps.get(slope)
    if maps is None:
        cols, rows = np.meshgrid(np.arange(STRIP_W, dtype=np.float32), np.arange(STRIP_H, dtype=np.float32))
        maps = (cols, rows + np.float32(slope) * (cols - np.float32(CENTER_COL)))
        _shear_maps[slope] = maps
    return cv2.remap(prob, maps[0], maps[1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def analyse_frame(frame: np.ndarray, roi: dict, p: Params):
    """Returns (level %, confidence, centre row k, inverse homography)."""
    strip, inverse = rectify_roi(frame, roi, STRIP_H, STRIP_W)
    prob = shear(slurry_probability(strip, p), float(roi.get('waterline_slope', 0.0)))
    rows = prob[:, p.margin:STRIP_W - p.margin].mean(axis=1)
    k, conf = split_rows(rows)
    level = 100.0 * (1.0 - k / STRIP_H)
    return level, conf, k, inverse
