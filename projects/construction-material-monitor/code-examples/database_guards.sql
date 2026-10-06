-- Selected SQLite architecture guards from the final Demo / PoC schema.
-- These rules enforce invariants at the database layer instead of relying only
-- on Python call order.

-- AI-03: one ACTIVE protection owner per project/camera.
CREATE UNIQUE INDEX IF NOT EXISTS ux_protection_one_active_per_camera
ON protection_runs(project_id, camera_id)
WHERE state = 'ACTIVE';


-- AI-08: a persisted capture must belong to a valid run/camera scope.
CREATE TRIGGER IF NOT EXISTS trg_capture_scope_guard_insert
BEFORE INSERT ON measurement_captures
FOR EACH ROW
WHEN NOT EXISTS (
        SELECT 1
        FROM measurement_runs mr
        WHERE mr.run_id = NEW.run_id
          AND mr.camera_id = NEW.camera_id
    )
    OR (
        NEW.image_path IS NOT NULL
        AND (NEW.frame_id IS NULL OR NEW.frame_id = '')
    )
BEGIN
    SELECT RAISE(
        ABORT,
        'measurement capture requires measurement_run parent and matching frame provenance'
    );
END;


-- AI-01 + AI-08: measurement identity and frame provenance must agree.
CREATE TRIGGER IF NOT EXISTS trg_measurement_identity_guard_insert
BEFORE INSERT ON measurements
FOR EACH ROW
WHEN
    (
        NEW.run_id IS NOT NULL
        AND NEW.run_id <> ''
        AND NOT EXISTS (
            SELECT 1
            FROM measurement_runs mr
            WHERE mr.run_id = NEW.run_id
              AND mr.project_id = NEW.project_id
              AND mr.camera_id = NEW.camera_id
              AND mr.baseline_id IS NEW.baseline_id
        )
    )
    OR
    (
        NEW.frame_id IS NOT NULL
        AND NEW.frame_id <> ''
        AND (
            NEW.run_id IS NULL
            OR NEW.run_id = ''
            OR NEW.captured_at IS NULL
            OR NOT EXISTS (
                SELECT 1
                FROM measurement_captures mc
                WHERE mc.frame_id = NEW.frame_id
                  AND mc.run_id = NEW.run_id
                  AND mc.camera_id = NEW.camera_id
                  AND mc.captured_at = NEW.captured_at
            )
        )
    )
    OR
    (
        NEW.run_id IS NOT NULL
        AND NEW.run_id <> ''
        AND NEW.image_path IS NOT NULL
        AND (NEW.frame_id IS NULL OR NEW.frame_id = '')
    )
BEGIN
    SELECT RAISE(
        ABORT,
        'measurement violates atomic identity/frame provenance guard'
    );
END;


-- Referenced capture identity is immutable.
CREATE TRIGGER IF NOT EXISTS trg_capture_referenced_guard_update
BEFORE UPDATE OF run_id, camera_id, captured_at, frame_id
ON measurement_captures
FOR EACH ROW
WHEN
    (
        OLD.frame_id IS NOT NULL
        AND EXISTS (
            SELECT 1
            FROM measurements m
            WHERE m.frame_id = OLD.frame_id
        )
    )
    OR EXISTS (
        SELECT 1
        FROM baseline_versions b
        WHERE b.capture_id = OLD.id
    )
    OR (
        OLD.frame_id IS NOT NULL
        AND EXISTS (
            SELECT 1
            FROM protection_sessions ps
            WHERE ps.initial_frame_id = OLD.frame_id
        )
    )
BEGIN
    SELECT RAISE(
        ABORT,
        'referenced capture identity is immutable'
    );
END;


-- Protection run must have a matching measurement_run parent.
CREATE TRIGGER IF NOT EXISTS trg_protection_run_parent_guard_insert
BEFORE INSERT ON protection_runs
FOR EACH ROW
WHEN NOT EXISTS (
    SELECT 1
    FROM measurement_runs mr
    WHERE mr.run_id = NEW.run_id
      AND mr.project_id = NEW.project_id
      AND mr.camera_id = NEW.camera_id
)
BEGIN
    SELECT RAISE(
        ABORT,
        'protection run requires matching measurement_run parent'
    );
END;


-- Protection session must resolve to both its camera owner and source frame.
CREATE TRIGGER IF NOT EXISTS trg_protection_session_owner_guard_insert
BEFORE INSERT ON protection_sessions
FOR EACH ROW
WHEN
    NOT EXISTS (
        SELECT 1
        FROM protection_runs pr
        WHERE pr.run_id = NEW.run_id
          AND pr.project_id = NEW.project_id
          AND pr.camera_id = NEW.camera_id
    )
    OR (
        NEW.source_run_id IS NOT NULL
        AND NEW.source_run_id <> ''
        AND NOT EXISTS (
            SELECT 1
            FROM measurement_runs mr
            WHERE mr.run_id = NEW.source_run_id
              AND mr.project_id = NEW.project_id
              AND mr.camera_id = NEW.camera_id
        )
    )
    OR (
        NEW.initial_frame_id IS NOT NULL
        AND NEW.initial_frame_id <> ''
        AND NOT EXISTS (
            SELECT 1
            FROM measurement_captures mc
            WHERE mc.frame_id = NEW.initial_frame_id
              AND mc.run_id = COALESCE(
                    NULLIF(NEW.source_run_id, ''),
                    NEW.run_id
                  )
              AND mc.camera_id = NEW.camera_id
              AND mc.captured_at = NEW.initial_timestamp
        )
    )
BEGIN
    SELECT RAISE(
        ABORT,
        'protection session violates owner/source provenance guard'
    );
END;
