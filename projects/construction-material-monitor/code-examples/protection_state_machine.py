"""Change-protection pure state model.

Selected from the final Demo / PoC source. Persistence helpers are omitted here
to keep the portfolio excerpt focused on state-transition semantics.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from statistics import median


class ProtectionState(str, Enum):
    IDLE = "IDLE"
    WAITING_SAMPLE = "WAITING_SAMPLE"
    COLLECTING = "COLLECTING"
    RECOVERED_TRANSIENT = "RECOVERED_TRANSIENT"
    STABLE_CONFIRMED = "STABLE_CONFIRMED"
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class ChangeProtectionPolicy:
    change_threshold: float = 0.05
    interval_sec: float = 300.0
    max_retries: int = 4
    stability_tolerance: float = 0.03
    recovery_tolerance: float = 0.05
    min_valid_samples: int = 3

    @classmethod
    def from_measurement_config(cls, cfg: dict) -> "ChangeProtectionPolicy":
        return cls(
            change_threshold=float(cfg.get("change_protection_threshold", 0.05)),
            interval_sec=max(float(cfg.get("change_protection_interval_sec", 300.0)), 0.0),
            max_retries=max(int(cfg.get("change_protection_max_retries", 4)), 1),
            stability_tolerance=max(float(cfg.get("change_protection_stability_tolerance", 0.03)), 0.0),
            recovery_tolerance=max(float(cfg.get("change_protection_recovery_tolerance", 0.05)), 0.0),
            min_valid_samples=max(int(cfg.get("change_protection_min_valid_samples", 3)), 2),
        )

    def requires_protection(
        self,
        *,
        initial_valid: bool,
        previous_remaining: float | None,
        initial_candidate: float | None,
    ) -> bool:
        if not initial_valid or previous_remaining is None or initial_candidate is None:
            return False
        return abs(float(initial_candidate) - float(previous_remaining)) > (
            self.change_threshold + 1e-9
        )


@dataclass(frozen=True)
class ProtectionSample:
    sequence_index: int
    remaining: float


@dataclass
class ProtectionSession:
    policy: ChangeProtectionPolicy
    previous_remaining: float | None
    initial_candidate: float | None
    state: ProtectionState = ProtectionState.IDLE
    samples: list[ProtectionSample] = field(default_factory=list)
    invalid_sequences: list[int] = field(default_factory=list)
    recovered_at_sequence: int | None = None
    recovered_remaining: float | None = None

    @classmethod
    def evaluate(
        cls,
        policy: ChangeProtectionPolicy,
        *,
        initial_valid: bool,
        previous_remaining: float | None,
        initial_candidate: float | None,
    ) -> "ProtectionSession":
        session = cls(
            policy=policy,
            previous_remaining=previous_remaining,
            initial_candidate=initial_candidate,
        )
        if not policy.requires_protection(
            initial_valid=initial_valid,
            previous_remaining=previous_remaining,
            initial_candidate=initial_candidate,
        ):
            return session

        session.samples.append(ProtectionSample(0, float(initial_candidate)))
        session.state = ProtectionState.WAITING_SAMPLE
        return session

    @property
    def is_terminal(self) -> bool:
        return self.state in {
            ProtectionState.IDLE,
            ProtectionState.RECOVERED_TRANSIENT,
            ProtectionState.STABLE_CONFIRMED,
            ProtectionState.PENDING_CONFIRMATION,
            ProtectionState.CANCELLED,
        }

    @property
    def values(self) -> list[float]:
        return [sample.remaining for sample in self.samples]

    @property
    def valid_sample_count(self) -> int:
        return len(self.samples)

    @property
    def reached_final_retry(self) -> bool:
        return any(
            sample.sequence_index == self.policy.max_retries
            for sample in self.samples
        )

    @property
    def median_remaining(self) -> float | None:
        values = self.values
        return float(median(values)) if values else None

    def waiting_for_sample(self) -> None:
        if self.state is ProtectionState.COLLECTING:
            self.state = ProtectionState.WAITING_SAMPLE

    def record_invalid_sample(self, sequence_index: int) -> ProtectionState:
        if self.is_terminal:
            return self.state
        self.invalid_sequences.append(int(sequence_index))
        self.state = ProtectionState.WAITING_SAMPLE
        return self.state

    def record_valid_sample(
        self, sequence_index: int, remaining: float
    ) -> ProtectionState:
        if self.is_terminal:
            return self.state

        value = float(remaining)
        self.samples.append(ProtectionSample(int(sequence_index), value))

        assert self.previous_remaining is not None
        if abs(value - float(self.previous_remaining)) <= self.policy.recovery_tolerance:
            self.recovered_at_sequence = int(sequence_index)
            self.recovered_remaining = value
            self.state = ProtectionState.RECOVERED_TRANSIENT
            return self.state

        self.state = ProtectionState.COLLECTING
        return self.state

    def finalize(self) -> ProtectionState:
        if self.is_terminal:
            return self.state

        med = self.median_remaining
        stable = (
            self.valid_sample_count >= self.policy.min_valid_samples
            and self.reached_final_retry
            and med is not None
            and all(
                abs(value - med) <= self.policy.stability_tolerance
                for value in self.values
            )
        )
        self.state = (
            ProtectionState.STABLE_CONFIRMED
            if stable
            else ProtectionState.PENDING_CONFIRMATION
        )
        return self.state

    def cancel(self) -> ProtectionState:
        if not self.is_terminal:
            self.state = ProtectionState.CANCELLED
        return self.state
