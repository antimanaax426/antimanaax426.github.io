"""One-off calibration of the waterline tilt from frames with a clear surface.

Excerpt from rod_level_v16.py (V1.6.5). Function bodies are copied verbatim from the source;
unrelated code (CLI, drawing, batch output) is omitted.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from boundary_detection import STRIP_H, STRIP_W, Params, slurry_probability, split_rows
from roi_rectification import rectify_roi

def estimate_waterline_slope(videos: list[Path], roi: dict, p: Params, frames: int = 150, min_conf: float = 0.8,
                             seed: int = 0) -> tuple[float, int]:
    """Measure the waterline tilt (strip rows per column) from frames with a clear surface.

    The shaft is split into 8 bands across its width; each band gets its own boundary and a
    line is fitted through them. The median slope over confident frames is returned.
    """
    rng = np.random.default_rng(seed)
    edges = np.linspace(p.margin, STRIP_W - p.margin, 9).astype(int)
    centres = (edges[:-1] + edges[1:]) / 2.0
    A = np.vstack([centres, np.ones_like(centres)]).T
    slopes = []
    per_video = max(1, int(np.ceil(frames / len(videos))))
    for v in videos:
        cap = cv2.VideoCapture(str(v))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        for idx in sorted(rng.choice(total, size=min(per_video, total), replace=False)) if total > 0 else []:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
            ok, frame = cap.read()
            if not ok:
                continue
            strip, _ = rectify_roi(frame, roi, STRIP_H, STRIP_W)
            prob = slurry_probability(strip, p)
            _, conf = split_rows(prob[:, p.margin:STRIP_W - p.margin].mean(axis=1))
            if conf < min_conf:
                continue
            ks = np.array([split_rows(prob[:, a:b].mean(axis=1))[0] for a, b in zip(edges[:-1], edges[1:])], float)
            (slope, _), *_ = np.linalg.lstsq(A, ks, rcond=None)
            slopes.append(slope)
        cap.release()
    if len(slopes) < 10:
        raise RuntimeError(f'Only {len(slopes)} frames with a clear surface; use videos where slurry is visible')
    return round(float(np.median(slopes)), 3), len(slopes)
