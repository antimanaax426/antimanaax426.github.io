# Code Examples

These files are excerpts from `rod_level_v16.py` (V1.6.4) and `geometry.py`. Function bodies are copied verbatim; only the CLI, drawing, batch output and interactive ROI marking are omitted.

The excerpts import each other and run as-is with `opencv-python` and `numpy`.

## Files

- [roi_rectification.py](roi_rectification.py) — orders the ROI corner points and rectifies the shaft into a fixed-size strip.
- [boundary_detection.py](boundary_detection.py) — slurry probability (brightness × smoothness), tilt shear, threshold-free optimal split and per-frame level / confidence.
- [tilt_calibration.py](tilt_calibration.py) — measures the waterline tilt from frames with a clear surface.
- [temporal_filter.py](temporal_filter.py) — rolling median with hold-over, and the no-level decision in the order `submerged` → `below_rod` → `fog` → `unknown`, from the sharpness and brightness of the shaft halves and of the probe region under the shaft.

## Reading order

1. boundary_detection.py — `slurry_probability`, `split_rows`, `analyse_frame`
2. temporal_filter.py — `LevelFilter.update`, `view_features`, `view_flags`
3. tilt_calibration.py
4. roi_rectification.py

## Minimal use

```python
import json, cv2
from boundary_detection import Params, analyse_frame
from temporal_filter import LevelFilter, probe_quad, view_features, view_flags

roi = json.load(open("roi.json"))      # {"top_edge": [[x, y], [x, y]], "bottom_edge": [...], "waterline_slope": ...}
p = Params()
cap = cv2.VideoCapture("clip.mp4")
filt = LevelFilter(cap.get(cv2.CAP_PROP_FPS), p)
probe = probe_quad(roi)
while True:
    ok, frame = cap.read()
    if not ok:
        break
    raw, conf, _, _ = analyse_frame(frame, roi, p)
    level, status, iqr = filt.update(raw, conf, flags=view_flags(view_features(frame, roi, probe), p))
```
