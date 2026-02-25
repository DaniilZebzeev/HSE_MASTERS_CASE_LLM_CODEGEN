"""Парсеры: разбор вывода black, ruff и pytest в структурированные ошибки."""

from __future__ import annotations

import re


def parse_ruff_errors(output: str) -> list[dict[str, str]]:
    """Разобрать вывод ruff в список словарей с описанием ошибок."""
    errors: list[dict[str, str]] = []
    pattern = re.compile(
        r"^(?P<file>[^:]+):(?P<line>\d+):(?P<col>\d+): (?P<code>\w+) (?P<msg>.+)$"
    )
    for line in output.splitlines():
        match = pattern.match(line)
        if match:
            errors.append(match.groupdict())
    return errors


def parse_pytest_errors(output: str) -> list[str]:
    """Извлечь имена упавших тестов из вывода pytest."""
    failed: list[str] = []
    for line in output.splitlines():
        if line.startswith("FAILED "):
            failed.append(line.removeprefix("FAILED ").strip())
    return failed
