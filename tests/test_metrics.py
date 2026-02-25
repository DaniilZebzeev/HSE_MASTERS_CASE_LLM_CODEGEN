"""Tests for engine.metrics.collector."""

from __future__ import annotations

import json
from pathlib import Path

from engine.metrics.collector import RunMetrics, TaskMetrics


def test_task_metrics_defaults() -> None:
    t = TaskMetrics(task_kind="models", output_path="models.py")
    assert t.repair_iterations == 0
    assert t.final_passed is False


def test_run_metrics_record_and_finish() -> None:
    m = RunMetrics(spec_name="todo", model="llama3")
    assert m.finished_at == 0.0

    m.record_task(TaskMetrics("models", "models.py", final_passed=True))
    m.record_task(TaskMetrics("main", "main.py", final_passed=True))
    m.finish()

    assert m.finished_at > 0.0
    assert len(m.tasks) == 2
    assert m.all_passed is True
    assert m.total_duration_s >= 0.0


def test_run_metrics_all_passed_false_when_one_fails() -> None:
    m = RunMetrics(spec_name="api", model="codellama")
    m.record_task(TaskMetrics("models", "models.py", final_passed=True))
    m.record_task(TaskMetrics("main", "main.py", final_passed=False))
    assert m.all_passed is False


def test_run_metrics_total_repair_iterations() -> None:
    m = RunMetrics(spec_name="api", model="llama3")
    m.record_task(TaskMetrics("models", "models.py", repair_iterations=2))
    m.record_task(TaskMetrics("main", "main.py", repair_iterations=1))
    assert m.total_repair_iterations == 3


def test_run_metrics_save_and_load(tmp_path: Path) -> None:
    m = RunMetrics(spec_name="todo", model="llama3")
    m.record_task(
        TaskMetrics("models", "models.py", final_passed=True, llm_latency_s=1.5)
    )
    m.finish()

    path = tmp_path / "run_metrics.json"
    m.save(path)

    assert path.exists()
    data = json.loads(path.read_text())
    assert data["spec_name"] == "todo"
    assert data["model"] == "llama3"
    assert len(data["tasks"]) == 1

    loaded = RunMetrics.load(path)
    assert loaded.spec_name == "todo"
    assert loaded.tasks[0].output_path == "models.py"
    assert loaded.tasks[0].llm_latency_s == 1.5


def test_run_metrics_summary_contains_key_info() -> None:
    m = RunMetrics(spec_name="my_api", model="llama3")
    m.record_task(TaskMetrics("main", "main.py", final_passed=True))
    m.finish()
    summary = m.summary()
    assert "my_api" in summary
    assert "llama3" in summary
