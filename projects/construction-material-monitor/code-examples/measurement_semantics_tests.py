"""Selected regression tests from the final Demo / PoC source.

These tests demonstrate that validity, quality and business decision are
independent dimensions, and that normal 100/80/50/20% stock levels are not
rejected simply because material quantity decreases.
"""
import pytest

from backend.core.measurement_validity import MeasurementValidity
from backend.vision import confidence
from test_core import _complete_protection, _patch_measure_sequence


def test_normal_remaining_100_80_50_20_are_valid_accepted_business_results(
    make_site,
    ctx,
    scene,
    monkeypatch,
):
    site = make_site(
        [scene.SceneState(seed=i) for i in range(5)],
        rois=("red",),
    )

    # Isolate measurement semantics from the >5pp protection policy.
    ctx.engine.cfg_m["change_protection_threshold"] = 2.0
    _patch_measure_sequence(
        monkeypatch,
        ctx,
        [1.00, 0.80, 0.50, 0.20],
    )

    seen = []
    for _ in range(4):
        result = ctx.engine.run_camera(site["pid"], site["cid"])
        item = result["results"][0]
        seen.append(item["remaining_ratio"])

        assert item["validity"] == "VALID"
        assert item["quality_status"] == "OK"
        assert item["decision_status"] == "ACCEPTED"

    assert seen == pytest.approx([1.00, 0.80, 0.50, 0.20])

    rows = ctx.projects.ctx(site["pid"]).db.query(
        "SELECT validity,quality_status,decision_status,is_valid,"
        "remaining_ratio FROM measurements "
        "WHERE roi_id='ROI-1' ORDER BY id DESC LIMIT 4"
    )

    assert all(
        row["validity"] == "VALID"
        and row["quality_status"] == "OK"
        for row in rows
    )
    assert all(
        row["decision_status"] == "ACCEPTED"
        and row["is_valid"] == 1
        for row in rows
    )


def test_protection_candidate_is_valid_but_pending_then_final_is_accepted(
    make_site,
    ctx,
    scene,
    monkeypatch,
):
    site = make_site(
        [scene.SceneState(seed=0), scene.SceneState(seed=1)],
        rois=("red",),
    )
    _patch_measure_sequence(
        monkeypatch,
        ctx,
        [0.60, 0.61, 0.59, 0.60, 0.61],
    )

    started = ctx.engine.run_camera(site["pid"], site["cid"])
    pending = started["results"][0]

    assert pending["validity"] == "VALID"
    assert pending["quality_status"] == "OK"
    assert pending["decision_status"] == "PENDING_CONFIRMATION"
    assert pending["remaining_ratio"] is None

    final = _complete_protection(
        ctx,
        site["pid"],
        site["cid"],
        started["run_id"],
    )
    item = final["results"][0]

    assert item["quality_status"] == "OK"
    assert item["decision_status"] == "ACCEPTED"
    assert item["remaining_ratio"] == pytest.approx(0.61)


def test_detector_failure_is_invalid_without_using_confidence(
    make_site,
    ctx,
    scene,
    monkeypatch,
):
    site = make_site(
        [scene.SceneState(seed=0), scene.SceneState(seed=1)],
        rois=("red",),
    )

    def detector_failure(frame, lb, al, q):
        roi = next(r for r in lb.rois if r.get("enabled", True))
        return [{
            "roi": roi,
            "res": None,
            "status": "DETECTOR_UNAVAILABLE",
            "validity": MeasurementValidity.INVALID_DETECTOR,
            "remaining": None,
            "confidence": 0.99,
            "detail": {"forced": True},
        }]

    monkeypatch.setattr(ctx.engine, "_measure", detector_failure)

    item = ctx.engine.run_camera(
        site["pid"], site["cid"]
    )["results"][0]

    assert item["validity"] == "INVALID_DETECTOR"
    assert item["quality_status"] == "DETECTOR_UNAVAILABLE"
    assert item["decision_status"] == "REJECTED"
    assert item["confidence"] == pytest.approx(0.99)
    assert item["remaining_ratio"] is None


def test_low_confidence_is_quality_warning_not_invalidity(
    make_site,
    ctx,
    scene,
    monkeypatch,
):
    site = make_site(
        [scene.SceneState(seed=0), scene.SceneState(seed=1)],
        rois=("red",),
    )

    monkeypatch.setattr(
        confidence,
        "compute",
        lambda *args, **kwargs: 0.10,
    )

    item = ctx.engine.run_camera(
        site["pid"], site["cid"]
    )["results"][0]

    assert item["validity"] == "VALID"
    assert item["quality_status"] == "LOW_CONFIDENCE"
    assert item["decision_status"] == "ACCEPTED"
    assert item["remaining_ratio"] is not None
