"""Отчёт: форматирование метрик для вывода и экспорта."""

from __future__ import annotations

import json
from pathlib import Path

from engine.metrics.metrics import MetricsCollector


def summary_text(collector: MetricsCollector) -> str:
    """Вернуть читаемое резюме всех метрик."""
    lines = [f"Общее время: {collector.elapsed():.1f}с", ""]
    for m in collector.all():
        status = "PASS" if m.passed else "FAIL"
        lines.append(
            f"  [{status}] {m.file_path}"
            f"  итераций={m.iterations}"
            f"  вызовов_llm={m.llm_calls}"
        )
    return "\n".join(lines)


def export_json(collector: MetricsCollector, path: Path) -> None:
    """Экспортировать метрики в JSON-файл."""
    data = [
        {
            "file_path": m.file_path,
            "model": m.model,
            "iterations": m.iterations,
            "llm_calls": m.llm_calls,
            "total_tokens": m.total_tokens,
            "elapsed_seconds": m.elapsed_seconds,
            "passed": m.passed,
            "errors": m.errors,
        }
        for m in collector.all()
    ]
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
