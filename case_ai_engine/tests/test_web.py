"""Web API tests (FastAPI TestClient, run_pipeline mocked)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from web.app import _derive_chat_title, _parse_spec_dict, _strip_code_fence, app, jobs


@pytest.fixture(autouse=True)
def clean_jobs() -> None:
    jobs.clear()
    yield
    jobs.clear()


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture()
def run_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "abc123"
    directory.mkdir()
    (directory / "pyproject.toml").write_text('[project]\nname = "x"\n', encoding="utf-8")
    (directory / "app").mkdir()
    (directory / "app" / "main.py").write_text(
        "from fastapi import FastAPI\n",
        encoding="utf-8",
    )
    return directory


class TestSpecHelpers:
    def test_strip_code_fence(self) -> None:
        raw = "```yaml\nservice:\n  name: demo\n```\n"
        assert _strip_code_fence(raw) == "service:\n  name: demo"

    def test_parse_spec_dict_plain_yaml(self) -> None:
        parsed = _parse_spec_dict("service:\n  name: demo\n  stack: python-fastapi")
        assert isinstance(parsed, dict)
        assert parsed["service"]["name"] == "demo"

    def test_parse_spec_dict_fenced_yaml(self) -> None:
        parsed = _parse_spec_dict(
            "```yaml\nservice:\n  name: demo\n  stack: python-fastapi\n```"
        )
        assert isinstance(parsed, dict)
        assert parsed["service"]["stack"] == "python-fastapi"

    def test_parse_spec_dict_invalid(self) -> None:
        assert _parse_spec_dict("build me a fastapi endpoint") is None

    def test_derive_title_prefers_service_name_for_english_request(self) -> None:
        spec = {"service": {"name": "inventory_api"}}
        assert _derive_chat_title("Build user management API", spec) == "inventory api"

    def test_derive_title_prefers_user_text_for_russian_request(self) -> None:
        spec = {"service": {"name": "inventory_api"}}
        title = _derive_chat_title("Сделай API для заметок", spec)
        assert title == "Сделай API для заметок"

    def test_derive_title_uses_first_meaningful_line(self) -> None:
        title = _derive_chat_title(" \n\nWrite a user management API\nwith auth", None)
        assert title == "Write a user management API"


class TestCreateJob:
    def test_returns_202(self, client: TestClient, tmp_path: Path) -> None:
        with (
            patch("web.app.OUTPUTS_DIR", tmp_path),
            patch("web.app.run_pipeline", return_value="abc123"),
        ):
            res = client.post(
                "/api/jobs/generate",
                json={"spec_yaml": "service:\n  name: x\n  stack: python-fastapi\n"},
            )
        assert res.status_code == 202

    def test_contains_job_id(self, client: TestClient, tmp_path: Path) -> None:
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

    def test_pending_status(self, client: TestClient, tmp_path: Path) -> None:
        with (
            patch("web.app.OUTPUTS_DIR", tmp_path),
            patch("web.app.run_pipeline", return_value="abc123"),
        ):
            res = client.post(
                "/api/jobs/generate",
                json={"spec_yaml": "service:\n  name: x\n  stack: python-fastapi\n"},
            )
        assert res.json()["status"] == "pending"
        assert "title" in res.json()


class TestGetJob:
    def test_missing_job_returns_404(self, client: TestClient) -> None:
        res = client.get("/api/jobs/nonexistent")
        assert res.status_code == 404

    def test_done_job(self, client: TestClient) -> None:
        jobs["test01"] = {
            "status": "done",
            "run_id": "abc123",
            "title": "Inventory API",
            "error": None,
        }
        res = client.get("/api/jobs/test01")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "done"
        assert data["run_id"] == "abc123"
        assert data["title"] == "Inventory API"

    def test_error_job(self, client: TestClient) -> None:
        jobs["test02"] = {"status": "error", "run_id": None, "title": None, "error": "boom"}
        res = client.get("/api/jobs/test02")
        assert res.status_code == 200
        assert res.json()["error"] == "boom"


class TestListRuns:
    def test_returns_run_list(self, client: TestClient, tmp_path: Path) -> None:
        (tmp_path / "run1").mkdir()
        (tmp_path / "run2").mkdir()
        with patch("web.app.OUTPUTS_DIR", tmp_path):
            res = client.get("/api/runs")
        assert res.status_code == 200
        data = res.json()
        assert "runs" in data
        assert set(data["runs"]) == {"run1", "run2"}

    def test_empty_list(self, client: TestClient, tmp_path: Path) -> None:
        with patch("web.app.OUTPUTS_DIR", tmp_path):
            res = client.get("/api/runs")
        data = res.json()
        assert data["runs"] == []
        assert data["titles"] == {}

    def test_returns_titles_from_meta(self, client: TestClient, tmp_path: Path) -> None:
        run1 = tmp_path / "run1"
        run2 = tmp_path / "run2"
        run1.mkdir()
        run2.mkdir()
        (run1 / "_chat_meta.json").write_text(
            json.dumps({"title": "Item API"}, ensure_ascii=False),
            encoding="utf-8",
        )
        with patch("web.app.OUTPUTS_DIR", tmp_path):
            res = client.get("/api/runs")
        data = res.json()
        assert data["titles"]["run1"] == "Item API"
        assert "run2" not in data["titles"]


class TestListFiles:
    def test_returns_files(self, client: TestClient, tmp_path: Path, run_dir: Path) -> None:
        with patch("web.app.OUTPUTS_DIR", tmp_path):
            res = client.get("/api/runs/abc123/files")
        assert res.status_code == 200
        files = res.json()["files"]
        assert "pyproject.toml" in files
        assert "app/main.py" in files

    def test_missing_run_returns_404(self, client: TestClient, tmp_path: Path) -> None:
        with patch("web.app.OUTPUTS_DIR", tmp_path):
            res = client.get("/api/runs/nosuchrun/files")
        assert res.status_code == 404


class TestGetFile:
    def test_returns_content(self, client: TestClient, tmp_path: Path, run_dir: Path) -> None:
        with patch("web.app.OUTPUTS_DIR", tmp_path):
            res = client.get("/api/runs/abc123/file?path=pyproject.toml")
        assert res.status_code == 200
        assert "[project]" in res.json()["content"]

    def test_missing_file_returns_404(
        self, client: TestClient, tmp_path: Path, run_dir: Path
    ) -> None:
        with patch("web.app.OUTPUTS_DIR", tmp_path):
            res = client.get("/api/runs/abc123/file?path=nope.py")
        assert res.status_code == 404

    def test_path_traversal_blocked(
        self, client: TestClient, tmp_path: Path, run_dir: Path
    ) -> None:
        with patch("web.app.OUTPUTS_DIR", tmp_path):
            res = client.get("/api/runs/abc123/file?path=../../secret.txt")
        assert res.status_code == 400


class TestDownloadRun:
    def test_returns_zip(self, client: TestClient, tmp_path: Path, run_dir: Path) -> None:
        with patch("web.app.OUTPUTS_DIR", tmp_path):
            res = client.get("/api/runs/abc123/download")
        assert res.status_code == 200
        assert "zip" in res.headers.get("content-type", "")

    def test_zip_not_empty(self, client: TestClient, tmp_path: Path, run_dir: Path) -> None:
        with patch("web.app.OUTPUTS_DIR", tmp_path):
            res = client.get("/api/runs/abc123/download")
        assert len(res.content) > 0

    def test_missing_run_returns_404(self, client: TestClient, tmp_path: Path) -> None:
        with patch("web.app.OUTPUTS_DIR", tmp_path):
            res = client.get("/api/runs/nosuchrun/download")
        assert res.status_code == 404
