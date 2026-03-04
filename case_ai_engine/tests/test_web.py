"""Тесты web-API (FastAPI TestClient, run_pipeline замокан)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from web.app import app, jobs

# ---------------------------------------------------------------------------
# Фикстуры
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_jobs():
    """Очистить jobs до и после каждого теста."""
    jobs.clear()
    yield
    jobs.clear()


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def run_dir(tmp_path: Path) -> Path:
    """Создать имитацию run-каталога с несколькими файлами."""
    d = tmp_path / "abc123"
    d.mkdir()
    (d / "pyproject.toml").write_text('[project]\nname = "x"\n', encoding="utf-8")
    (d / "app").mkdir()
    (d / "app" / "main.py").write_text(
        "from fastapi import FastAPI\n", encoding="utf-8"
    )
    return d


# ---------------------------------------------------------------------------
# POST /api/jobs/generate
# ---------------------------------------------------------------------------


class TestCreateJob:
    """Тесты создания задачи генерации."""

    def test_возвращает_202(self, client: TestClient, tmp_path: Path) -> None:
        """Статус-код 202 при корректном запросе."""
        with (
            patch("web.app.OUTPUTS_DIR", tmp_path),
            patch("web.app.run_pipeline", return_value="abc123"),
        ):
            res = client.post(
                "/api/jobs/generate",
                json={"spec_yaml": "service:\n  name: x\n  stack: python-fastapi\n"},
            )
        assert res.status_code == 202

    def test_содержит_job_id(self, client: TestClient, tmp_path: Path) -> None:
        """Ответ содержит непустой job_id."""
        with (
            patch("web.app.OUTPUTS_DIR", tmp_path),
            patch("web.app.run_pipeline", return_value="abc123"),
        ):
            res = client.post(
                "/api/jobs/generate",
                json={"spec_yaml": "service:\n  name: x\n  stack: python-fastapi\n"},
            )
        data = res.json()
        assert "job_id" in data
        assert len(data["job_id"]) > 0

    def test_статус_pending(self, client: TestClient, tmp_path: Path) -> None:
        """Начальный статус — pending."""
        with (
            patch("web.app.OUTPUTS_DIR", tmp_path),
            patch("web.app.run_pipeline", return_value="abc123"),
        ):
            res = client.post(
                "/api/jobs/generate",
                json={"spec_yaml": "service:\n  name: x\n  stack: python-fastapi\n"},
            )
        assert res.json()["status"] == "pending"


# ---------------------------------------------------------------------------
# GET /api/jobs/{job_id}
# ---------------------------------------------------------------------------


class TestGetJob:
    """Тесты получения статуса задачи."""

    def test_несуществующий_job_404(self, client: TestClient) -> None:
        """Несуществующий job_id → 404."""
        res = client.get("/api/jobs/nonexistent")
        assert res.status_code == 404

    def test_статус_done(self, client: TestClient) -> None:
        """Задача со статусом done возвращается корректно."""
        jobs["test01"] = {"status": "done", "run_id": "abc123", "error": None}
        res = client.get("/api/jobs/test01")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "done"
        assert data["run_id"] == "abc123"

    def test_статус_error(self, client: TestClient) -> None:
        """Задача со статусом error содержит текст ошибки."""
        jobs["test02"] = {"status": "error", "run_id": None, "error": "boom"}
        res = client.get("/api/jobs/test02")
        assert res.status_code == 200
        assert res.json()["error"] == "boom"


# ---------------------------------------------------------------------------
# GET /api/runs
# ---------------------------------------------------------------------------


class TestListRuns:
    """Тесты списка запусков."""

    def test_возвращает_список(self, client: TestClient, tmp_path: Path) -> None:
        """Ответ содержит ключ 'runs' со списком."""
        (tmp_path / "run1").mkdir()
        (tmp_path / "run2").mkdir()
        with patch("web.app.OUTPUTS_DIR", tmp_path):
            res = client.get("/api/runs")
        assert res.status_code == 200
        data = res.json()
        assert "runs" in data
        assert set(data["runs"]) == {"run1", "run2"}

    def test_пустой_список(self, client: TestClient, tmp_path: Path) -> None:
        """Пустая outputs-директория → пустой список."""
        with patch("web.app.OUTPUTS_DIR", tmp_path):
            res = client.get("/api/runs")
        assert res.json()["runs"] == []


# ---------------------------------------------------------------------------
# GET /api/runs/{run_id}/files
# ---------------------------------------------------------------------------


class TestListFiles:
    """Тесты списка файлов внутри run."""

    def test_возвращает_файлы(
        self, client: TestClient, tmp_path: Path, run_dir: Path
    ) -> None:
        """Список содержит ожидаемые пути."""
        with patch("web.app.OUTPUTS_DIR", tmp_path):
            res = client.get("/api/runs/abc123/files")
        assert res.status_code == 200
        files = res.json()["files"]
        assert "pyproject.toml" in files
        assert "app/main.py" in files

    def test_несуществующий_run_404(self, client: TestClient, tmp_path: Path) -> None:
        """Несуществующий run_id → 404."""
        with patch("web.app.OUTPUTS_DIR", tmp_path):
            res = client.get("/api/runs/nosuchrun/files")
        assert res.status_code == 404

    def test_path_traversal_в_run_id(self, client: TestClient, tmp_path: Path) -> None:
        """run_id с '..' → 400."""
        with patch("web.app.OUTPUTS_DIR", tmp_path):
            res = client.get("/api/runs/../files")
        assert res.status_code in (400, 404)


# ---------------------------------------------------------------------------
# GET /api/runs/{run_id}/file
# ---------------------------------------------------------------------------


class TestGetFile:
    """Тесты получения содержимого файла."""

    def test_возвращает_содержимое(
        self, client: TestClient, tmp_path: Path, run_dir: Path
    ) -> None:
        """Корректный файл возвращает content."""
        with patch("web.app.OUTPUTS_DIR", tmp_path):
            res = client.get("/api/runs/abc123/file?path=pyproject.toml")
        assert res.status_code == 200
        assert "[project]" in res.json()["content"]

    def test_несуществующий_файл_404(
        self, client: TestClient, tmp_path: Path, run_dir: Path
    ) -> None:
        """Несуществующий файл → 404."""
        with patch("web.app.OUTPUTS_DIR", tmp_path):
            res = client.get("/api/runs/abc123/file?path=nope.py")
        assert res.status_code == 404

    def test_path_traversal_защита(
        self, client: TestClient, tmp_path: Path, run_dir: Path
    ) -> None:
        """Попытка path-traversal через path= → 400."""
        with patch("web.app.OUTPUTS_DIR", tmp_path):
            res = client.get("/api/runs/abc123/file?path=../../secret.txt")
        assert res.status_code == 400

    def test_вложенный_файл(
        self, client: TestClient, tmp_path: Path, run_dir: Path
    ) -> None:
        """Файл в поддиректории возвращается корректно."""
        with patch("web.app.OUTPUTS_DIR", tmp_path):
            res = client.get("/api/runs/abc123/file?path=app/main.py")
        assert res.status_code == 200
        assert "FastAPI" in res.json()["content"]


# ---------------------------------------------------------------------------
# GET /api/runs/{run_id}/download
# ---------------------------------------------------------------------------


class TestDownloadRun:
    """Тесты скачивания ZIP-архива."""

    def test_возвращает_zip(
        self, client: TestClient, tmp_path: Path, run_dir: Path
    ) -> None:
        """Ответ имеет Content-Type application/zip."""
        with patch("web.app.OUTPUTS_DIR", tmp_path):
            res = client.get("/api/runs/abc123/download")
        assert res.status_code == 200
        assert "zip" in res.headers.get("content-type", "")

    def test_zip_непустой(
        self, client: TestClient, tmp_path: Path, run_dir: Path
    ) -> None:
        """ZIP-архив непустой (content-length > 0)."""
        with patch("web.app.OUTPUTS_DIR", tmp_path):
            res = client.get("/api/runs/abc123/download")
        assert len(res.content) > 0

    def test_несуществующий_run_404(self, client: TestClient, tmp_path: Path) -> None:
        """Несуществующий run_id → 404."""
        with patch("web.app.OUTPUTS_DIR", tmp_path):
            res = client.get("/api/runs/nosuchrun/download")
        assert res.status_code == 404
