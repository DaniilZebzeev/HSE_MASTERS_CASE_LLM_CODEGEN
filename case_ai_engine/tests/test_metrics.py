"""Тесты модуля метрик и отчётов."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.metrics.metrics import RunMetrics
from engine.metrics.report import write_report_json, write_report_md

# ---------------------------------------------------------------------------
# Фикстуры
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_metrics() -> RunMetrics:
    """Типичные метрики успешного запуска."""
    return RunMetrics(
        run_id="abc123",
        model="codellama:7b-instruct",
        spec_path="examples/spec_min.yaml",
        success=True,
        iterations=0,
        time_total_sec=12.5,
        fail_profile={"format": 0, "lint": 0, "tests": 0},
        patch_volume_lines=0,
        files_generated=6,
        started_at="2026-01-01T00:00:00+00:00",
    )


@pytest.fixture()
def fail_metrics() -> RunMetrics:
    """Метрики неудачного запуска с repair-итерациями."""
    return RunMetrics(
        run_id="def456",
        model="codellama:7b-instruct",
        spec_path="examples/spec_min.yaml",
        success=False,
        iterations=2,
        time_total_sec=45.0,
        fail_profile={"format": 1, "lint": 3, "tests": 2},
        patch_volume_lines=17,
        files_generated=6,
        started_at="2026-01-02T00:00:00+00:00",
    )


# ---------------------------------------------------------------------------
# write_report_json
# ---------------------------------------------------------------------------


class TestWriteReportJson:
    """Тесты write_report_json."""

    def test_создаёт_файл(self, tmp_path: Path, sample_metrics: RunMetrics) -> None:
        """report.json появляется в run_dir."""
        write_report_json(tmp_path, sample_metrics)
        assert (tmp_path / "report.json").exists()

    def test_возвращает_путь(self, tmp_path: Path, sample_metrics: RunMetrics) -> None:
        """Функция возвращает Path к файлу."""
        result = write_report_json(tmp_path, sample_metrics)
        assert result == tmp_path / "report.json"

    def test_валидный_json(self, tmp_path: Path, sample_metrics: RunMetrics) -> None:
        """Содержимое файла является валидным JSON."""
        write_report_json(tmp_path, sample_metrics)
        raw = (tmp_path / "report.json").read_text(encoding="utf-8")
        parsed = json.loads(raw)
        assert isinstance(parsed, dict)

    def test_содержит_run_id(self, tmp_path: Path, sample_metrics: RunMetrics) -> None:
        """JSON содержит run_id."""
        write_report_json(tmp_path, sample_metrics)
        data = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
        assert data["run_id"] == "abc123"

    def test_содержит_success(self, tmp_path: Path, sample_metrics: RunMetrics) -> None:
        """JSON содержит поле success."""
        write_report_json(tmp_path, sample_metrics)
        data = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
        assert data["success"] is True

    def test_содержит_fail_profile(
        self, tmp_path: Path, sample_metrics: RunMetrics
    ) -> None:
        """JSON содержит fail_profile как словарь."""
        write_report_json(tmp_path, sample_metrics)
        data = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
        assert isinstance(data["fail_profile"], dict)
        assert data["fail_profile"]["format"] == 0

    def test_содержит_все_поля(
        self, tmp_path: Path, sample_metrics: RunMetrics
    ) -> None:
        """JSON содержит все поля RunMetrics."""
        write_report_json(tmp_path, sample_metrics)
        data = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
        expected_keys = {
            "run_id",
            "model",
            "spec_path",
            "success",
            "iterations",
            "time_total_sec",
            "fail_profile",
            "patch_volume_lines",
            "files_generated",
            "started_at",
        }
        assert expected_keys == set(data.keys())

    def test_fail_metrics_success_false(
        self, tmp_path: Path, fail_metrics: RunMetrics
    ) -> None:
        """Для fail_metrics success=False сохраняется верно."""
        write_report_json(tmp_path, fail_metrics)
        data = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
        assert data["success"] is False
        assert data["iterations"] == 2
        assert data["fail_profile"]["lint"] == 3


# ---------------------------------------------------------------------------
# write_report_md
# ---------------------------------------------------------------------------


class TestWriteReportMd:
    """Тесты write_report_md."""

    def test_создаёт_файл(self, tmp_path: Path, sample_metrics: RunMetrics) -> None:
        """report.md появляется в run_dir."""
        write_report_md(tmp_path, sample_metrics)
        assert (tmp_path / "report.md").exists()

    def test_возвращает_путь(self, tmp_path: Path, sample_metrics: RunMetrics) -> None:
        """Функция возвращает Path к файлу."""
        result = write_report_md(tmp_path, sample_metrics)
        assert result == tmp_path / "report.md"

    def test_содержит_run_id(self, tmp_path: Path, sample_metrics: RunMetrics) -> None:
        """Markdown содержит run_id в заголовке."""
        write_report_md(tmp_path, sample_metrics)
        content = (tmp_path / "report.md").read_text(encoding="utf-8")
        assert "abc123" in content

    def test_содержит_статус_pass(
        self, tmp_path: Path, sample_metrics: RunMetrics
    ) -> None:
        """При success=True в тексте есть PASS."""
        write_report_md(tmp_path, sample_metrics)
        content = (tmp_path / "report.md").read_text(encoding="utf-8")
        assert "PASS" in content

    def test_содержит_статус_fail(
        self, tmp_path: Path, fail_metrics: RunMetrics
    ) -> None:
        """При success=False в тексте есть FAIL."""
        write_report_md(tmp_path, fail_metrics)
        content = (tmp_path / "report.md").read_text(encoding="utf-8")
        assert "FAIL" in content

    def test_содержит_модель(self, tmp_path: Path, sample_metrics: RunMetrics) -> None:
        """Markdown содержит имя модели."""
        write_report_md(tmp_path, sample_metrics)
        content = (tmp_path / "report.md").read_text(encoding="utf-8")
        assert "codellama:7b-instruct" in content

    def test_содержит_время(self, tmp_path: Path, sample_metrics: RunMetrics) -> None:
        """Markdown содержит время выполнения."""
        write_report_md(tmp_path, sample_metrics)
        content = (tmp_path / "report.md").read_text(encoding="utf-8")
        assert "12.5" in content

    def test_содержит_профиль_ошибок(
        self, tmp_path: Path, fail_metrics: RunMetrics
    ) -> None:
        """Markdown содержит значения fail_profile."""
        write_report_md(tmp_path, fail_metrics)
        content = (tmp_path / "report.md").read_text(encoding="utf-8")
        assert "3" in content  # lint: 3
        assert "2" in content  # tests: 2


# ---------------------------------------------------------------------------
# Интеграция: оба файла создаются вместе
# ---------------------------------------------------------------------------


def test_оба_отчёта_создаются(tmp_path: Path, sample_metrics: RunMetrics) -> None:
    """write_report_json + write_report_md оба создают файлы."""
    write_report_json(tmp_path, sample_metrics)
    write_report_md(tmp_path, sample_metrics)
    assert (tmp_path / "report.json").exists()
    assert (tmp_path / "report.md").exists()
