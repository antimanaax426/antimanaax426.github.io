"""AUTO_FUSION detector excerpt from the final Demo / PoC source.

This excerpt keeps the production detector logic that fixed confidence coupling
to remaining material quantity. Legacy detector construction code is omitted.
"""
from __future__ import annotations

import cv2
import numpy as np

# In the full project these are imported from backend.vision.*
# from .background.detector import BackgroundDiffDetector
# from .base import DetectContext, DetectorResult
# from .color.detector import ColorDetector


class AutoFusionDetector:
    mode = "AUTO_FUSION"

    def __init__(
        self,
        color_detector,
        background_detector,
        color_weight: float,
        background_weight: float,
        score_threshold: float,
        confidence_factor: float = 1.0,
        difficult_condition: bool = False,
    ):
        self.color = color_detector
        self.background = background_detector
        self.color_weight = float(color_weight)
        self.background_weight = float(background_weight)
        self.score_threshold = float(score_threshold)

        # Backward-compatible config name. This is static profile difficulty
        # metadata, not a per-measurement confidence multiplier.
        self.profile_difficulty_factor = float(confidence_factor)
        self.confidence_factor = self.profile_difficulty_factor
        self.difficult_condition = bool(difficult_condition)

    @staticmethod
    def _iou(a: np.ndarray, b: np.ndarray) -> float:
        """Legacy diagnostic IoU.

        IoU is intentionally not used as the AUTO_FUSION confidence input.
        When the true remaining material becomes small, a fixed number of
        disagreeing pixels occupies a larger share of the union and makes IoU
        fall even if image/detection quality has not changed.
        """
        aa, bb = a > 0, b > 0
        union = int(np.logical_or(aa, bb).sum())
        if union == 0:
            return 1.0
        return float(np.logical_and(aa, bb).sum()) / union

    @staticmethod
    def _fixed_support_agreement(
        a: np.ndarray,
        b: np.ndarray,
        support: np.ndarray,
    ) -> float:
        """Binary agreement on a fixed, quantity-independent support.

        COLOR and BACKGROUND_DIFF are compared inside the material region
        captured at Baseline. Both 1/1 (material remains) and 0/0
        (material has been removed) count as agreement.

        The denominator therefore stays constant as stock decreases.
        """
        sel = support > 0
        n = int(sel.sum())
        if n <= 0:
            return 0.0

        aa = a > 0
        bb = b > 0
        matches = int((aa[sel] == bb[sel]).sum())
        return float(matches) / float(n)

    def detect(self, ctx):
        c = self.color.detect(ctx)
        if not c.available:
            return ctx.result_type(
                mask=np.zeros_like(ctx.roi_mask),
                available=False,
                info={"reason": "COLOR_UNAVAILABLE", "color": c.info},
            )

        # Baseline registration has no baseline_material_mask yet.
        # Initial material support is therefore created from color detection.
        if ctx.baseline_material_mask is None:
            mask = c.mask.copy()
            mask[ctx.roi_mask == 0] = 0
            return ctx.result_type(
                mask=mask,
                confidence_hint=max(0.0, min(1.0, c.confidence_hint)),
                info={
                    "fusion": "WEIGHTED_SCORE",
                    "phase": "BASELINE_COLOR_ONLY",
                    "color_weight": self.color_weight,
                    "background_weight": self.background_weight,
                    "score_threshold": self.score_threshold,
                    "profile_difficulty_factor": self.profile_difficulty_factor,
                    "measurement_agreement_factor": 1.0,
                    "color": c.info,
                },
            )

        b = self.background.detect(ctx)
        if not b.available:
            mask = c.mask.copy()
            mask[ctx.roi_mask == 0] = 0
            return ctx.result_type(
                mask=mask,
                confidence_hint=max(0.0, min(1.0, c.confidence_hint * 0.65)),
                info={
                    "fusion": "WEIGHTED_SCORE",
                    "degraded": True,
                    "reason": b.info.get("reason"),
                    "profile_difficulty_factor": self.profile_difficulty_factor,
                    "measurement_agreement_factor": 0.65,
                    "color": c.info,
                },
            )

        baseline_gate = (ctx.baseline_material_mask > 0).astype(np.uint8) * 255
        bg_mask = cv2.bitwise_and(b.mask, baseline_gate)

        color_score = (c.mask > 0).astype(np.float32)
        background_score = (bg_mask > 0).astype(np.float32)
        score = (
            self.color_weight * color_score
            + self.background_weight * background_score
        )

        mask_bool = score >= self.score_threshold

        # Material newly appearing outside the baseline mask is treated as
        # replenishment when color matches and the reference image changed.
        changed_from_reference = b.mask == 0
        replenished = (
            (c.mask > 0)
            & (baseline_gate == 0)
            & changed_from_reference
            & (ctx.roi_mask > 0)
        )
        mask_bool |= replenished

        mask = mask_bool.astype(np.uint8) * 255
        mask[ctx.roi_mask == 0] = 0

        # Confidence describes observation quality, not material quantity.
        agreement = self._fixed_support_agreement(
            c.mask,
            bg_mask,
            baseline_gate,
        )
        legacy_iou = self._iou(c.mask, bg_mask)

        measurement_agreement_factor = 0.65 + 0.35 * agreement
        hint = (
            min(c.confidence_hint, b.confidence_hint)
            * measurement_agreement_factor
        )

        selected = ctx.roi_mask > 0
        mean_score = float(score[selected].mean()) if selected.any() else 0.0

        return ctx.result_type(
            mask=mask,
            confidence_hint=max(0.0, min(1.0, hint)),
            info={
                "fusion": "WEIGHTED_SCORE",
                "color_weight": self.color_weight,
                "background_weight": self.background_weight,
                "score_threshold": self.score_threshold,
                "agreement": round(agreement, 3),
                "agreement_metric": "FIXED_BASELINE_SUPPORT",
                "legacy_iou": round(legacy_iou, 3),
                "mean_score": round(mean_score, 3),
                "profile_difficulty_factor": self.profile_difficulty_factor,
                "measurement_agreement_factor": round(
                    measurement_agreement_factor, 3
                ),
                "replenished_area_px": int(replenished.sum()),
                "color": c.info,
                "background": b.info,
            },
        )
