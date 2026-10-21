"""ROI ordering and perspective rectification of the shaft.

Excerpt from geometry.py (V1.6.3). Function bodies are copied verbatim from the source;
unrelated code (CLI, drawing, batch output) is omitted.
"""
from __future__ import annotations

import cv2
import numpy as np

def order_endpoints(config):
    """Four ordered points: top-left, top-right, bottom-right, bottom-left.
    'top'/'bottom' is physical meaning, independent of screen Y.
    """
    top = np.asarray(config['top_edge'], dtype=np.float32)
    bottom = np.asarray(config['bottom_edge'], dtype=np.float32)
    if top.shape != (2,2) or bottom.shape != (2,2):
        raise ValueError('Each edge must contain two [x,y] points.')
    return np.float32([top[0], top[1], bottom[1], bottom[0]])


def rectify_roi(frame, config, target_height=320, target_width=80):
    q=order_endpoints(config)
    target=np.float32([[0,0],[target_width-1,0],[target_width-1,target_height-1],[0,target_height-1]])
    matrix=cv2.getPerspectiveTransform(q,target)
    patch=cv2.warpPerspective(frame,matrix,(target_width,target_height),flags=cv2.INTER_LINEAR)
    return patch,cv2.getPerspectiveTransform(target,q)
