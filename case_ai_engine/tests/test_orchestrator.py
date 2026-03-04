"""Интеграционные тесты оркестратора (без реального Ollama)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from engine.orchestrator import run_pipeline
from engine.verify.runner import VerifyResult

# ---------------------------------------------------------------------------
# Вспомогательные данные
# ---------------------------------------------------------------------------

# Заготовленное содержимое файлов (заменяет вывод LLM)
_FAKE_FILES: dict[str, str] = {
    "pyproject.toml": '[project]\nname = "test-api"\nversion = "0.1.0"\n',
    "app/main.py": "from fastapi import FastAPI\n\napp = FastAPI()\n",
    "app/schemas/item.py": (
        "from pydantic import BaseModel\n\n\nclass Item(BaseModel):\n    id: int\n"
    ),
    "app/routers/item.py": "from fastapi import APIRouter\n\nrouter = APIRouter()\n",
    "tests/test_smoke.py": "def test_placeholder() -> None:\n    assert True\n",
    "tests/test_item_crud.py": (
        "def test_placeholder_item() -> None:\n    assert True\n"
    ),
}

_FAKE_DIFF = (
    "--- a/app/main.py\n"
    "+++ b/app/main.py\n"
    "@@ -1,3 +1,3 @@\n"
    " from fastapi import FastAPI\n"
    "-\n"
    "+\n"
    " app = FastAPI()\n"
)


@pytest.fixture()
def minimal_spec(tmp_path: Path) -> Path:
    """Минимальная спецификация во временной директории."""
    spec = {
        "service": {"name": "test_api", "stack": "python-fastapi"},
        "entities": [
            {
                "name": "Item",
                "fields": [{"name": "id", "type": "int", "required": True}],
            }
        ],
        "endpoints": [
            {
                "name": "health",
                "method": "GET",
                "path": "/health",
                "responses": [{"status_code": 200}],
            }
        ],
        "generation": {"tests": True},
    }
    spec_file = tmp_path / "spec.yaml"
    spec_file.write_text(yaml.dump(spec, allow_unicode=True), encoding="utf-8")
    return spec_file


def _ok_result(tool: str) -> VerifyResult:
    return VerifyResult(tool=tool, ok=True, exit_code=0, stdout="", stderr="")


def _ok_verify() -> list[VerifyResult]:
    return [_ok_result("black"), _ok_result("ruff"), _ok_result("pytest")]


def _configure_client(MockClient: MagicMock, side_effect) -> MagicMock:
    """Настроить мок OllamaClient как контекстный менеджер."""
    instance = MagicMock()
    instance.generate.side_effect = side_effect
    instance.__enter__ = MagicMock(return_value=instance)
    instance.__exit__ = MagicMock(return_value=False)
    MockClient.return_value = instance
    return instance


def _round_robin(items: list[str]):
    """Замыкание: возвращает элементы списка по кругу."""
    call = [0]

    def _fn(_prompt: str) -> str:
        result = items[call[0] % len(items)]
        call[0] += 1
        return result

    return _fn


# ---------------------------------------------------------------------------
# Основные тесты
# ---------------------------------------------------------------------------


class TestRunPipeline:
    """Unit/интеграционные тесты run_pipeline."""

    def test_возвращает_run_id_строкой(
        self, minimal_spec: Path, tmp_path: Path
    ) -> None:
        """Функция возвращает непустую строку."""
        out = tmp_path / "out"
        with (
            patch("engine.orchestrator.OllamaClient") as MockClient,
            patch("engine.orchestrator.verify_project", return_value=_ok_verify()),
        ):
            _configure_client(MockClient, _round_robin(list(_FAKE_FILES.values())))
            run_id = run_pipeline(str(minimal_spec), model="test", output_dir=out)
        assert isinstance(run_id, str)
        assert len(run_id) > 0

    def test_создаёт_подкаталог_с_run_id(
        self, minimal_spec: Path, tmp_path: Path
    ) -> None:
        """В output_dir создаётся подкаталог output_dir/run_id."""
        out = tmp_path / "out"
        with (
            patch("engine.orchestrator.OllamaClient") as MockClient,
            patch("engine.orchestrator.verify_project", return_value=_ok_verify()),
        ):
            _configure_client(MockClient, _round_robin(list(_FAKE_FILES.values())))
            run_id = run_pipeline(str(minimal_spec), model="test", output_dir=out)
        assert (out / run_id).is_dir()

    def test_записывает_pyproject_и_main(
        self, minimal_spec: Path, tmp_path: Path
    ) -> None:
        """После генерации в run_dir находятся pyproject.toml и app/main.py."""
        out = tmp_path / "out"
        with (
            patch("engine.orchestrator.OllamaClient") as MockClient,
            patch("engine.orchestrator.verify_project", return_value=_ok_verify()),
        ):
            _configure_client(MockClient, _round_robin(list(_FAKE_FILES.values())))
            run_id = run_pipeline(str(minimal_spec), model="test", output_dir=out)
        run_dir = out / run_id
        assert (run_dir / "pyproject.toml").exists()
        assert (run_dir / "app" / "main.py").exists()

    def test_llm_вызывается_для_каждого_шага(
        self, minimal_spec: Path, tmp_path: Path
    ) -> None:
        """generate() вызывается ровно 6 раз (6 шагов плана)."""
        out = tmp_path / "out"
        with (
            patch("engine.orchestrator.OllamaClient") as MockClient,
            patch("engine.orchestrator.verify_project", return_value=_ok_verify()),
        ):
            instance = _configure_client(
                MockClient, _round_robin(list(_FAKE_FILES.values()))
            )
            run_pipeline(str(minimal_spec), model="test", output_dir=out)
        # minimal_spec: 1 entity, tests=True → 6 шагов плана
        assert instance.generate.call_count == 6

    def test_файлы_записаны_с_нужным_содержимым(
        self, minimal_spec: Path, tmp_path: Path
    ) -> None:
        """Содержимое pyproject.toml соответствует первому ответу LLM."""
        files = list(_FAKE_FILES.items())
        call_idx = [0]

        def ordered_gen(_prompt: str) -> str:
            idx = call_idx[0]
            call_idx[0] += 1
            _, content = files[idx % len(files)]
            return content

        out = tmp_path / "out"
        with (
            patch("engine.orchestrator.OllamaClient") as MockClient,
            patch("engine.orchestrator.verify_project", return_value=_ok_verify()),
        ):
            _configure_client(MockClient, ordered_gen)
            run_id = run_pipeline(str(minimal_spec), model="test", output_dir=out)
        run_dir = out / run_id
        assert "[project]" in (run_dir / "pyproject.toml").read_text(encoding="utf-8")

    def test_создаёт_report_json_и_report_md(
        self, minimal_spec: Path, tmp_path: Path
    ) -> None:
        """После завершения pipeline в run_dir есть report.json и report.md."""
        out = tmp_path / "out"
        with (
            patch("engine.orchestrator.OllamaClient") as MockClient,
            patch("engine.orchestrator.verify_project", return_value=_ok_verify()),
        ):
            _configure_client(MockClient, _round_robin(list(_FAKE_FILES.values())))
            run_id = run_pipeline(str(minimal_spec), model="test", output_dir=out)
        run_dir = out / run_id
        assert (run_dir / "report.json").exists()
        assert (run_dir / "report.md").exists()

    def test_report_json_содержит_success_true(
        self, minimal_spec: Path, tmp_path: Path
    ) -> None:
        """При успешной верификации report.json содержит success=true."""
        import json

        out = tmp_path / "out"
        with (
            patch("engine.orchestrator.OllamaClient") as MockClient,
            patch("engine.orchestrator.verify_project", return_value=_ok_verify()),
        ):
            _configure_client(MockClient, _round_robin(list(_FAKE_FILES.values())))
            run_id = run_pipeline(str(minimal_spec), model="test", output_dir=out)
        data = json.loads((out / run_id / "report.json").read_text(encoding="utf-8"))
        assert data["success"] is True
        assert data["iterations"] == 0
        assert data["files_generated"] == 6


# ---------------------------------------------------------------------------
# Repair-loop
# ---------------------------------------------------------------------------


class TestRepairLoop:
    """Repair-loop: верификация запуска цикла исправлений."""

    def test_repair_запускается_при_ошибке(
        self, minimal_spec: Path, tmp_path: Path
    ) -> None:
        """При первой верификации fail → repair-промпт отправляется к LLM."""
        fail = VerifyResult(
            tool="ruff",
            ok=False,
            exit_code=1,
            stdout="app/main.py:1:1: F401 unused",
            stderr="",
        )
        verify_seq = [
            [fail, fail, fail],
            [_ok_result("black"), _ok_result("ruff"), _ok_result("pytest")],
        ]
        file_contents = list(_FAKE_FILES.values())
        call_idx = [0]

        def gen_fn(_prompt: str) -> str:
            if call_idx[0] < len(file_contents):
                result = file_contents[call_idx[0]]
            else:
                result = _FAKE_DIFF
            call_idx[0] += 1
            return result

        out = tmp_path / "out"
        with (
            patch("engine.orchestrator.OllamaClient") as MockClient,
            patch("engine.orchestrator.verify_project", side_effect=verify_seq),
            patch("engine.orchestrator.apply_diff_to_project"),
        ):
            instance = _configure_client(MockClient, gen_fn)
            run_pipeline(str(minimal_spec), model="test", output_dir=out, max_iters=3)
        # 6 шагов плана + 1 repair-вызов = 7
        assert instance.generate.call_count == 7

    def test_repair_останавливается_по_макс_итер(
        self, minimal_spec: Path, tmp_path: Path
    ) -> None:
        """Если все итерации провалились — pipeline завершается с run_id."""
        fail = VerifyResult(
            tool="pytest", ok=False, exit_code=1, stdout="", stderr="1 failed"
        )
        out = tmp_path / "out"
        with (
            patch("engine.orchestrator.OllamaClient") as MockClient,
            patch(
                "engine.orchestrator.verify_project",
                return_value=[fail, fail, fail],
            ),
            patch("engine.orchestrator.apply_diff_to_project"),
        ):
            all_items = list(_FAKE_FILES.values()) + [_FAKE_DIFF]
            _configure_client(MockClient, _round_robin(all_items))
            run_id = run_pipeline(
                str(minimal_spec), model="test", output_dir=out, max_iters=2
            )
        assert isinstance(run_id, str)
