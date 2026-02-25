"""Раннер верификации: запускает black, ruff и pytest над сгенерированным проектом."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# Максимальное число итераций repair-loop
MAX_REPAIR_ITERATIONS = 3


class VerifyResult:
    """Результат запуска одного инструмента верификации."""

    def __init__(self, tool: str, passed: bool, output: str) -> None:
        self.tool = tool
        self.passed = passed
        self.output = output

    def __repr__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return f"VerifyResult(tool={self.tool!r}, status={status!r})"


def run_tool(cmd: list[str], cwd: Path) -> VerifyResult:
    """Запустить внешний инструмент и вернуть VerifyResult."""
    tool_name = cmd[0]
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    passed = result.returncode == 0
    output = result.stdout + result.stderr
    logger.debug("%s завершился с кодом %d", tool_name, result.returncode)
    return VerifyResult(tool=tool_name, passed=passed, output=output)


def verify_project(project_dir: Path) -> list[VerifyResult]:
    """Запустить все инструменты верификации для каталога проекта."""
    results: list[VerifyResult] = []
    for cmd in [
        ["black", "--check", "."],
        ["ruff", "check", "."],
        ["pytest", "-q"],
    ]:
        results.append(run_tool(cmd, cwd=project_dir))
    return results
