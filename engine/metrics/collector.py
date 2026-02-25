"""Metrics collector for code-generation runs.

Each :class:`RunMetrics` instance accumulates timing, token, and quality
information for a single end-to-end generation run.  Results can be
persisted as JSON for later analysis.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class TaskMetrics:
    """Per-task metrics."""

    task_kind: str
    output_path: str
    prompt_tokens_approx: int = 0  # rough character-based estimate
    response_tokens_approx: int = 0
    llm_latency_s: float = 0.0
    repair_iterations: int = 0
    final_passed: bool = False


@dataclass
class RunMetrics:
    """Metrics for a complete generation run.

    Attributes
    ----------
    spec_name:
        Name taken from the DSL spec.
    model:
        Ollama model used.
    started_at:
        Unix timestamp when the run started.
    finished_at:
        Unix timestamp when the run finished (set by :meth:`finish`).
    tasks:
        Per-task metrics appended by :meth:`record_task`.
    """

    spec_name: str
    model: str
    started_at: float = field(default_factory=time.time)
    finished_at: float = 0.0
    tasks: list[TaskMetrics] = field(default_factory=list)

    # ------------------------------------------------------------------

    def record_task(self, task: TaskMetrics) -> None:
        """Append *task* metrics to this run."""
        self.tasks.append(task)

    def finish(self) -> None:
        """Record the run end-time."""
        self.finished_at = time.time()

    @property
    def total_duration_s(self) -> float:
        return self.finished_at - self.started_at

    @property
    def all_passed(self) -> bool:
        return all(t.final_passed for t in self.tasks)

    @property
    def total_repair_iterations(self) -> int:
        return sum(t.repair_iterations for t in self.tasks)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str | Path) -> Path:
        """Serialise metrics to a JSON file at *path*.

        Returns
        -------
        Path
            Absolute path to the written file.
        """
        dest = Path(path).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        return dest

    @classmethod
    def load(cls, path: str | Path) -> RunMetrics:
        """Deserialise metrics from a JSON file."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        tasks = [TaskMetrics(**t) for t in data.pop("tasks", [])]
        instance = cls(**data)
        instance.tasks = tasks
        return instance

    def summary(self) -> str:
        """Return a short human-readable summary string."""
        status = "✓ PASSED" if self.all_passed else "✗ FAILED"
        return (
            f"Run: {self.spec_name} | model: {self.model} | {status} | "
            f"duration: {self.total_duration_s:.1f}s | "
            f"tasks: {len(self.tasks)} | repairs: {self.total_repair_iterations}"
        )
