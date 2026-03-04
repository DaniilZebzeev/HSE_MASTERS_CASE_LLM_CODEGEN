"""Парсеры вывода black, ruff и pytest в структурированные списки ошибок."""

from __future__ import annotations

import re


def parse_ruff(output: str) -> list[str]:
    """Извлечь строки ошибок из вывода ruff check.

    Формат строки ruff: ``path/file.py:line:col: CODE сообщение``

    Args:
        output: объединённый stdout/stderr ruff.

    Returns:
        Список строк вида "path/file.py:line:col: CODE сообщение".
    """
    pattern = re.compile(r"^[^:]+:\d+:\d+: \w+ .+$")
    return [line for line in output.splitlines() if pattern.match(line)]


def parse_pytest(output: str) -> list[str]:
    """Извлечь имена упавших тестов из вывода pytest -q.

    Строки формата ``FAILED tests/test_foo.py::test_bar - AssertionError``
    или просто ``FAILED tests/test_foo.py::test_bar``.

    Args:
        output: stdout pytest.

    Returns:
        Список строк с именами упавших тестов (без префикса "FAILED ").
    """
    failed: list[str] = []
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("FAILED "):
            # Убираем " - <причина>" если есть
            entry = stripped.removeprefix("FAILED ").split(" - ")[0].strip()
            failed.append(entry)
    return failed
