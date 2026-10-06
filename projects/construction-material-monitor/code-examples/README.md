# Code Examples

These files are selected excerpts from the final Demo / PoC source archive. They are not rewritten toy examples.

The full application is not published here because it contains project-specific UI, configuration, runtime paths and operational details that are unnecessary for portfolio review. The excerpts below preserve the actual implementation patterns used in the project.

## Files

- [acquisition_contract.py](acquisition_contract.py) — typed acquisition purpose / priority / wait-policy contract used by the single camera acquisition boundary.
- [protection_state_machine.py](protection_state_machine.py) — pure business state machine for multi-sample change protection.
- [auto_fusion_detector.py](auto_fusion_detector.py) — COLOR + BACKGROUND_DIFF fusion and the fixed-baseline-support confidence fix.
- [bounded_scheduler_excerpt.py](bounded_scheduler_excerpt.py) — bounded submission, WAITING / QUEUED / RUNNING semantics and no-catch-up scheduling.
- [measurement_transaction_excerpt.py](measurement_transaction_excerpt.py) — atomic run/capture/measurement/protection persistence and post-commit publication.
- [database_guards.sql](database_guards.sql) — SQLite guards for provenance, parent identity and one-active-protection ownership.
- [measurement_semantics_tests.py](measurement_semantics_tests.py) — regression tests showing separation of validity, quality and business decision.

## Reading order

For a quick review, start with:

1. auto_fusion_detector.py
2. measurement_transaction_excerpt.py
3. protection_state_machine.py
4. bounded_scheduler_excerpt.py
5. database_guards.sql

The excerpts intentionally omit unrelated imports / surrounding application code where a whole source module would add noise. Those files are marked as excerpts in their header.
