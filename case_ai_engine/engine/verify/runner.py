"""Раннер верификации: запускает black, ruff и pytest над сгенерированным проектом."""

from __future__ import annotations

import logging
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Таймауты (секунды)
_TIMEOUT_DEFAULT = 30
_TIMEOUT_PYTEST = 60


@dataclass
class VerifyResult:
    """Результат запуска одного инструмента верификации."""

    tool: str
    ok: bool
    exit_code: int
    stdout: str
    stderr: str

    def __repr__(self) -> str:
        status = "PASS" if self.ok else "FAIL"
        return f"VerifyResult(tool={self.tool!r}, status={status!r})"


def _run(
    tool: str,
    cmd: list[str],
    project_root: Path,
    timeout: int = _TIMEOUT_DEFAULT,
) -> VerifyResult:
    """Запустить команду и вернуть VerifyResult."""
    logger.debug("Запуск [%s]: %s в %s", tool, " ".join(cmd), project_root)
    try:
        proc = subprocess.run(
            cmd,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        logger.warning("%s превысил таймаут %ds", tool, timeout)
        return VerifyResult(
            tool=tool,
            ok=False,
            exit_code=-1,
            stdout="",
            stderr=f"TimeoutExpired: {tool} не завершился за {timeout}с",
        )
    ok = proc.returncode == 0
    logger.debug("%s завершился с кодом %d", tool, proc.returncode)
    return VerifyResult(
        tool=tool,
        ok=ok,
        exit_code=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )


def run_black(project_root: Path) -> VerifyResult:
    """Запустить black --check и вернуть VerifyResult."""
    cmd = [sys.executable, "-m", "black", "--check", "."]
    return _run("black", cmd, project_root)


def run_ruff(project_root: Path) -> VerifyResult:
    """Запустить ruff check и вернуть VerifyResult."""
    cmd = [sys.executable, "-m", "ruff", "check", "."]
    return _run("ruff", cmd, project_root)


def run_pytest(project_root: Path) -> VerifyResult:
    """Запустить pytest -q и вернуть VerifyResult."""
    cmd = [sys.executable, "-m", "pytest", "-q"]
    return _run("pytest", cmd, project_root, timeout=_TIMEOUT_PYTEST)


def verify_project(project_root: Path) -> list[VerifyResult]:
    """Запустить все инструменты верификации и вернуть список результатов."""
    return [
        run_black(project_root),
        run_ruff(project_root),
        run_pytest(project_root),
    ]
