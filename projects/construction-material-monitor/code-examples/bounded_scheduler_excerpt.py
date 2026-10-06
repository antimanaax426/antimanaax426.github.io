"""Bounded scheduler excerpt from the final Demo / PoC source.

The full module also exposes health/heartbeat views and lifecycle helpers.
This excerpt keeps the concurrency semantics relevant to AI-07.
"""
from __future__ import annotations

import threading
import traceback
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable


@dataclass
class Job:
    job_id: str
    kind: str
    interval_sec: float
    func: Callable[[], object]
    next_run: datetime | None = None
    last_run: datetime | None = None
    last_finished: datetime | None = None
    status: str = "WAITING"
    last_outcome: str | None = None
    last_error: str | None = None
    queued_since: datetime | None = None
    running_since: datetime | None = None
    next_run_fn: Callable[[datetime], datetime] | None = None
    future: Future | None = field(default=None, repr=False)


class Scheduler:
    def __init__(
        self,
        *,
        clock: Callable[[], datetime],
        max_workers: int = 4,
        max_queued: int | None = None,
    ):
        self.max_workers = max(1, int(max_workers))
        self.max_queued = (
            self.max_workers
            if max_queued is None
            else max(0, int(max_queued))
        )
        self.jobs: dict[str, Job] = {}
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._pool = ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix="job",
        )

        # Count every submitted Future until the worker wrapper exits.
        # ThreadPoolExecutor itself has an unbounded queue.
        self._inflight_count = 0
        self._running_count = 0
        self.clock = clock
        self.heartbeat: datetime | None = None

    @staticmethod
    def _dispatch_priority(job: Job) -> tuple[int, datetime, str]:
        # Protection should not be starved by a large measurement backlog.
        if job.kind == "protection":
            rank = 0
        elif job.kind in {"sync", "retention"}:
            rank = 1
        elif job.kind == "measure":
            rank = 2
        else:
            rank = 1

        due = job.next_run or datetime.max.replace(tzinfo=timezone.utc)
        return rank, due, job.job_id

    def _execute(self, job: Job) -> None:
        # submit() means QUEUED. RUNNING begins only when a worker starts.
        with self._lock:
            if self._stop.is_set() or self.jobs.get(job.job_id) is not job:
                job.queued_since = None
                job.future = None
                if job.status == "QUEUED":
                    job.status = "WAITING"
                self._inflight_count = max(0, self._inflight_count - 1)
                return

            started = self.clock()
            self._running_count += 1
            job.status = "RUNNING"
            job.queued_since = None
            job.running_since = started
            job.last_run = started

            # Measurement is fixed-delay. Other jobs retain their own schedule.
            if job.kind != "measure":
                job.next_run = (
                    job.next_run_fn(started)
                    if job.next_run_fn
                    else started + timedelta(seconds=job.interval_sec)
                )

        try:
            result = job.func()
            with self._lock:
                job.last_outcome = "OK"
                job.last_error = None
        except Exception as exc:
            with self._lock:
                job.last_outcome = "ERROR"
                job.last_error = (
                    f"{exc.__class__.__name__}: {exc}\n"
                    f"{traceback.format_exc()}"
                )
        finally:
            with self._lock:
                finished = self.clock()
                job.last_finished = finished

                # No catch-up burst: next measurement is based on completion,
                # not on an old scheduled timestamp.
                if job.kind == "measure" and job.next_run_fn is None:
                    job.next_run = (
                        finished + timedelta(seconds=job.interval_sec)
                    )

                job.running_since = None
                job.future = None
                self._running_count = max(0, self._running_count - 1)
                self._inflight_count = max(0, self._inflight_count - 1)

                if self.jobs.get(job.job_id) is job:
                    job.status = "WAITING"

    def run_pending(self) -> list[str]:
        """Submit due jobs only up to worker + pending capacity."""

        submitted: list[str] = []
        now = self.clock()

        with self._lock:
            self.heartbeat = now
            if self._stop.is_set():
                return submitted

            capacity = (
                self.max_workers + self.max_queued
            ) - self._inflight_count
            if capacity <= 0:
                return submitted

            due = [
                job
                for job in self.jobs.values()
                if job.running_since is None
                and job.status != "QUEUED"
                and job.next_run
                and job.next_run <= now
            ]
            due.sort(key=self._dispatch_priority)

            for job in due[:capacity]:
                if self._stop.is_set():
                    break

                job.status = "QUEUED"
                job.queued_since = now
                job.running_since = None
                self._inflight_count += 1

                try:
                    job.future = self._pool.submit(self._execute, job)
                except Exception:
                    self._inflight_count = max(
                        0, self._inflight_count - 1
                    )
                    job.status = "WAITING"
                    job.queued_since = None
                    raise

                submitted.append(job.job_id)

        return submitted
