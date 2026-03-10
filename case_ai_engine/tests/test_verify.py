"""Тесты раннера верификации и парсеров логов."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from engine.verify.parsers import parse_pytest, parse_ruff
from engine.verify.runner import VerifyResult, run_black, run_pytest, run_ruff

# ---------------------------------------------------------------------------
# Вспомогательные фикстуры
# ---------------------------------------------------------------------------

RUFF_OUTPUT_WITH_ERRORS = """\
app/main.py:3:1: F401 'os' imported but unused
app/main.py:10:5: E501 line too long (92 > 88 characters)
app/schemas/item.py:7:9: UP006 Use 'list' instead of 'List'
"""

RUFF_OUTPUT_CLEAN = """\
All checks passed!
"""

PYTEST_OUTPUT_FAILURES = """\
FAILED tests/test_smoke.py::test_health_check - AssertionError: assert 404 == 200
FAILED tests/test_item_crud.py::test_create_item
FAILED tests/test_item_crud.py::test_list_items - TypeError: 'NoneType'
"""

PYTEST_OUTPUT_PASS = """\
...
3 passed in 0.42s
"""

PYTEST_OUTPUT_MIXED = """\
.F.
FAILED tests/test_foo.py::test_bar - assert False
1 failed, 2 passed in 1.23s
"""


# ---------------------------------------------------------------------------
# parse_ruff
# ---------------------------------------------------------------------------


class TestParseRuff:
    """Тесты parse_ruff."""

    def test_возвращает_список_строк(self) -> None:
        """Результат — список строк."""
        result = parse_ruff(RUFF_OUTPUT_WITH_ERRORS)
        assert isinstance(result, list)
        assert all(isinstance(e, str) for e in result)

    def test_парсит_три_ошибки(self) -> None:
        """Три строки с ошибками → три элемента."""
        result = parse_ruff(RUFF_OUTPUT_WITH_ERRORS)
        assert len(result) == 3

    def test_содержит_код_ошибки(self) -> None:
        """Каждая строка содержит код ошибки ruff."""
        result = parse_ruff(RUFF_OUTPUT_WITH_ERRORS)
        assert any("F401" in e for e in result)
        assert any("E501" in e for e in result)
        assert any("UP006" in e for e in result)

    def test_содержит_путь_к_файлу(self) -> None:
        """Строки содержат путь к файлу."""
        result = parse_ruff(RUFF_OUTPUT_WITH_ERRORS)
        assert any("app/main.py" in e for e in result)

    def test_чистый_вывод_даёт_пустой_список(self) -> None:
        """Чистый вывод ruff → пустой список."""
        result = parse_ruff(RUFF_OUTPUT_CLEAN)
        assert result == []

    def test_пустая_строка_даёт_пустой_список(self) -> None:
        """Пустой ввод → пустой список."""
        assert parse_ruff("") == []

    def test_игнорирует_нерелевантные_строки(self) -> None:
        """Строки без паттерна ruff игнорируются."""
        mixed = "Found 2 errors.\n" + RUFF_OUTPUT_WITH_ERRORS + "No fixes available.\n"
        result = parse_ruff(mixed)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# parse_pytest
# ---------------------------------------------------------------------------


class TestParsePytest:
    """Тесты parse_pytest."""

    def test_возвращает_список_строк(self) -> None:
        """Результат — список строк."""
        result = parse_pytest(PYTEST_OUTPUT_FAILURES)
        assert isinstance(result, list)

    def test_парсит_три_упавших_теста(self) -> None:
        """Три строки FAILED → три элемента."""
        result = parse_pytest(PYTEST_OUTPUT_FAILURES)
        assert len(result) == 3

    def test_содержит_имена_тестов(self) -> None:
        """Результат содержит идентификаторы тестов."""
        result = parse_pytest(PYTEST_OUTPUT_FAILURES)
        assert "tests/test_smoke.py::test_health_check" in result
        assert "tests/test_item_crud.py::test_create_item" in result

    def test_убирает_причину_после_тире(self) -> None:
        """Часть ' - <причина>' обрезается."""
        result = parse_pytest(PYTEST_OUTPUT_FAILURES)
        assert all(" - " not in e for e in result)

    def test_нет_префикса_failed(self) -> None:
        """Строки не начинаются с 'FAILED '."""
        result = parse_pytest(PYTEST_OUTPUT_FAILURES)
        assert all(not e.startswith("FAILED ") for e in result)

    def test_успешный_вывод_даёт_пустой_список(self) -> None:
        """Вывод без FAILED → пустой список."""
        result = parse_pytest(PYTEST_OUTPUT_PASS)
        assert result == []

    def test_смешанный_вывод(self) -> None:
        """Один FAILED среди прочих строк."""
        result = parse_pytest(PYTEST_OUTPUT_MIXED)
        assert len(result) == 1
        assert result[0] == "tests/test_foo.py::test_bar"

    def test_пустая_строка_даёт_пустой_список(self) -> None:
        """Пустой ввод → пустой список."""
        assert parse_pytest("") == []


# ---------------------------------------------------------------------------
# runner: run_black / run_ruff / run_pytest
# ---------------------------------------------------------------------------


def _make_proc(returncode: int, stdout: str = "", stderr: str = "") -> MagicMock:
    """Сформировать мок CompletedProcess."""
    mock = MagicMock(spec=subprocess.CompletedProcess)
    mock.returncode = returncode
    mock.stdout = stdout
    mock.stderr = stderr
    return mock


class TestRunner:
    """Тесты функций run_black, run_ruff, run_pytest."""

    @pytest.fixture()
    def root(self, tmp_path: Path) -> Path:
        return tmp_path

    def test_run_black_ok_при_нулевом_коде(self, root: Path) -> None:
        """run_black возвращает ok=True при returncode=0."""
        with patch("subprocess.run", return_value=_make_proc(0)):
            result = run_black(root)
        assert isinstance(result, VerifyResult)
        assert result.ok is True
        assert result.exit_code == 0
        assert result.tool == "black"

    def test_run_black_fail_при_ненулевом_коде(self, root: Path) -> None:
        """run_black возвращает ok=False при returncode!=0."""
        with patch(
            "subprocess.run", return_value=_make_proc(1, stderr="would reformat")
        ):
            result = run_black(root)
        assert result.ok is False
        assert result.exit_code == 1
        assert result.stderr == "would reformat"

    def test_run_ruff_ok(self, root: Path) -> None:
        """run_ruff возвращает ok=True при returncode=0."""
        with patch("subprocess.run", return_value=_make_proc(0)):
            result = run_ruff(root)
        assert result.ok is True

    def test_run_ruff_fail_содержит_stdout(self, root: Path) -> None:
        """run_ruff сохраняет stdout с ошибками."""
        with patch(
            "subprocess.run",
            return_value=_make_proc(1, stdout="app/main.py:1:1: F401 unused"),
        ):
            result = run_ruff(root)
        assert result.ok is False
        assert "F401" in result.stdout

    def test_run_pytest_ok(self, root: Path) -> None:
        """run_pytest возвращает ok=True при returncode=0."""
        with patch("subprocess.run", return_value=_make_proc(0, stdout="3 passed")):
            result = run_pytest(root)
        assert result.ok is True
        assert result.stdout == "3 passed"

    def test_run_pytest_timeout_даёт_fail(self, root: Path) -> None:
        """TimeoutExpired преобразуется в ok=False с exit_code=-1."""
        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=["pytest"], timeout=60),
        ):
            result = run_pytest(root)
        assert result.ok is False
        assert result.exit_code == -1
        assert "TimeoutExpired" in result.stderr

    def test_run_ruff_normalizes_none_streams(self, root: Path) -> None:
        """If subprocess returns None in streams, runner normalizes them to empty strings."""
        with patch(
            "subprocess.run",
            return_value=_make_proc(1, stdout=None, stderr=None),
        ):
            result = run_ruff(root)
        assert result.ok is False
        assert result.stdout == ""
        assert result.stderr == ""
    def test_verify_result_repr(self) -> None:
        """VerifyResult.__repr__ содержит статус."""
        r = VerifyResult(tool="black", ok=True, exit_code=0, stdout="", stderr="")
        assert "PASS" in repr(r)
        r2 = VerifyResult(tool="ruff", ok=False, exit_code=1, stdout="", stderr="err")
        assert "FAIL" in repr(r2)
