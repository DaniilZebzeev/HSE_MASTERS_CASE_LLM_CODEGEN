"""Tests for engine.project.writer."""

from __future__ import annotations

from pathlib import Path

from engine.project.writer import write_project
from engine.spec.schema import ApiSpec


def test_write_project_creates_files(tmp_path: Path) -> None:
    spec = ApiSpec(name="my_api", version="0.2.0", description="Test API")
    generated = {
        "main.py": "# main\nfrom fastapi import FastAPI\napp = FastAPI()\n",
        "models.py": "# models\n",
        "routers/api.py": "# router\nfrom fastapi import APIRouter\nrouter = APIRouter()\n",
    }
    root = write_project(spec, generated, tmp_path / "out")

    assert (root / "main.py").exists()
    assert (root / "models.py").exists()
    assert (root / "routers" / "api.py").exists()
    assert (root / "requirements.txt").exists()
    assert (root / "pyproject.toml").exists()


def test_write_project_pyproject_contains_name(tmp_path: Path) -> None:
    spec = ApiSpec(name="awesome_api", version="1.2.3", description="Awesome")
    write_project(spec, {"main.py": "# x\n"}, tmp_path / "proj")
    content = (tmp_path / "proj" / "pyproject.toml").read_text()
    assert "awesome_api" in content
    assert "1.2.3" in content


def test_write_project_does_not_overwrite_existing(tmp_path: Path) -> None:
    spec = ApiSpec(name="api")
    out = tmp_path / "out"
    write_project(spec, {"main.py": "# v1\n"}, out)
    # Manually place a requirements.txt
    req = out / "requirements.txt"
    req.write_text("custom==1.0\n")
    # Run again — should not overwrite requirements.txt
    write_project(spec, {"main.py": "# v2\n"}, out)
    assert req.read_text() == "custom==1.0\n"


def test_write_project_creates_init_py_for_packages(tmp_path: Path) -> None:
    spec = ApiSpec(name="api")
    generated = {
        "routers/api.py": "# router\n",
        "tests/test_api.py": "# test\n",
    }
    root = write_project(spec, generated, tmp_path / "proj")
    assert (root / "__init__.py").exists()
    assert (root / "routers" / "__init__.py").exists()
    assert (root / "tests" / "__init__.py").exists()
