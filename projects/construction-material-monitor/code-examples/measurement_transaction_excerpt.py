"""Measurement transaction excerpt from the final Demo / PoC source.

This file is intentionally an excerpt, not a standalone module. It shows the
P1-1 transaction boundary and the AI-04 Commit Before Publish rule used by the
full MeasurementEngine.
"""


class MeasurementEngineTransactionExcerpt:
    def _commit_initial_measurement_run(
        self,
        pid: str,
        run_row: dict,
        *,
        capture: dict | None,
        rows: list[dict],
        protection_run=None,
        wait_for_protection: bool = False,
        final_status: str = "MEASUREMENT_FINISHED",
        detail: dict | None = None,
    ) -> int | None:
        """Commit all durable state produced by one initial camera run.

        The transaction includes:
        - measurement_run parent
        - physical capture identity
        - ROI measurement rows
        - initial protection state, when armed

        Later protection samples use their own transaction.
        """
        ctx = self.projects.ctx(pid)
        committed_at = iso(self._clock())
        protection_version: int | None = None

        with ctx.db.transaction() as c:
            ctx.measurement_runs.create_in_tx(c, run_row)

            if capture is not None:
                ctx.measurements.add_capture_in_tx(
                    c,
                    run_row["run_id"],
                    capture["camera_id"],
                    capture["captured_at"],
                    capture.get("sequence_index", 0),
                    capture.get("capture_role", "INITIAL"),
                    capture.get("image_path"),
                    capture.get("capture_status", "CAPTURED"),
                    capture.get("detail"),
                    frame_id=capture.get("frame_id"),
                    purpose=capture.get("purpose"),
                    acquisition_result=capture.get("acquisition_result"),
                )

            if rows:
                ctx.measurements.insert_many_in_tx(c, rows)

            if protection_run is not None:
                protection_version = self._persist_protection_run_in_tx(
                    c,
                    protection_run,
                    active=True,
                    now_s=committed_at,
                )

            if wait_for_protection:
                # New protection owner normally uses the same run_id.
                # Keep this fallback so future callers cannot accidentally
                # leave the parent in ACTIVE state.
                if (
                    protection_run is None
                    or protection_run.run_id != run_row["run_id"]
                ):
                    ctx.measurement_runs.set_state_in_tx(
                        c,
                        run_row["run_id"],
                        "WAITING_PROTECTION",
                        committed_at,
                        detail=detail,
                    )
            else:
                ctx.measurement_runs.finish_in_tx(
                    c,
                    run_row["run_id"],
                    committed_at,
                    final_status,
                    detail=detail,
                )

        return protection_version

    def _publish_intents(self, pid: str, intents: list) -> None:
        """Publish externally-visible effects only after DB commit succeeds."""
        for intent in intents:
            if isinstance(intent, MeasurementFailureStateIntent):
                if intent.success:
                    self.cameras.record_measurement_success(
                        pid, intent.camera_id
                    )
                else:
                    self.cameras.record_measurement_failure(
                        pid, intent.camera_id
                    )
                continue

            if isinstance(intent, CameraAlignmentStateIntent):
                self.cameras.set_alignment_error(
                    pid,
                    intent.camera_id,
                    intent.active,
                    intent.message,
                )
                continue

            self.alerts.raise_alert(
                pid,
                intent.alert_type,
                intent.message,
                intent.camera_id,
                intent.roi_id,
                intent.image,
                intent.detail,
                run_id=intent.run_id,
            )


def post_commit_sequence(engine, pid, post_commit_intents):
    """Equivalent ordering used by the full run path.

    The real MeasurementEngine first calls _commit_initial_measurement_run().
    Only after that context manager exits successfully are alerts/UI-visible
    state published.
    """

    # All durable run/capture/measurement/protection writes have committed.
    engine._publish_intents(pid, post_commit_intents)

    # Protection scheduling also happens after durable initial state exists.
    # engine._schedule_protection_job(...)
