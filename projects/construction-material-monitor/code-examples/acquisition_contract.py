"""Public camera acquisition contract.

Selected directly from the final Demo / PoC source.

Business code selects a typed purpose and wait policy. Human-readable reason
is retained for logs/cache metadata only and must not control acquisition behavior.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Any

import numpy as np


class AcquisitionPurpose(str, Enum):
    MEASUREMENT = "MEASUREMENT"
    CHANGE_PROTECTION = "CHANGE_PROTECTION"
    BASELINE_VALIDATION = "BASELINE_VALIDATION"
    BASELINE_REGISTRATION = "BASELINE_REGISTRATION"
    ROI_VALIDATION = "ROI_VALIDATION"
    CAMERA_VALIDATION = "CAMERA_VALIDATION"
    MANUAL_REFRESH = "MANUAL_REFRESH"
    UI_PREVIEW = "UI_PREVIEW"


class AcquisitionPriority(IntEnum):
    """Business priority used by one CameraConnection's acquisition arbiter."""

    HIGH = 0
    MEDIUM = 1
    LOW = 2


_PRIORITY_BY_PURPOSE = {
    AcquisitionPurpose.MEASUREMENT: AcquisitionPriority.HIGH,
    AcquisitionPurpose.CHANGE_PROTECTION: AcquisitionPriority.HIGH,
    AcquisitionPurpose.BASELINE_VALIDATION: AcquisitionPriority.MEDIUM,
    AcquisitionPurpose.BASELINE_REGISTRATION: AcquisitionPriority.MEDIUM,
    AcquisitionPurpose.ROI_VALIDATION: AcquisitionPriority.MEDIUM,
    AcquisitionPurpose.CAMERA_VALIDATION: AcquisitionPriority.MEDIUM,
    AcquisitionPurpose.MANUAL_REFRESH: AcquisitionPriority.LOW,
    AcquisitionPurpose.UI_PREVIEW: AcquisitionPriority.LOW,
}


def priority_for_purpose(purpose: AcquisitionPurpose) -> AcquisitionPriority:
    if not isinstance(purpose, AcquisitionPurpose):
        raise TypeError("purpose must be AcquisitionPurpose")
    return _PRIORITY_BY_PURPOSE[purpose]


class AcquisitionWaitPolicy(str, Enum):
    """Whether a caller may wait for the single physical snapshot slot."""

    NO_WAIT = "NO_WAIT"
    BOUNDED = "BOUNDED"


@dataclass(frozen=True)
class AcquisitionResult:
    frame: np.ndarray | None
    status: str
    entry: dict[str, Any] | None

    @property
    def ok(self) -> bool:
        return self.status in {"ok", "cached"} and self.entry is not None
