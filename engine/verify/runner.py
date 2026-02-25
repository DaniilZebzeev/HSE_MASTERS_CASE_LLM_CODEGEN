"""Verification runner (black, ruff, pytest) and repair-loop.

The :func:`verify` function runs the three tools against a project directory
and returns a :class:`VerifyResult`.  The :func:`repair_loop` orchestrates
repeated LLM-assisted repair attempts until verification passes or the
maximum number of iterations is reached.
"""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ToolResult:
    """Output of a single verification tool."""

    tool: str
    passed: bool
    stdout: str = ""
    stderr: str = ""

    @property
    def output(self) -> str:
        return (self.stdout + "\n" + self.stderr).strip()


@dataclass
class VerifyResult:
    """Aggregated result of running all verification tools."""

    results: list[ToolResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def diagnostics(self) -> str:
        """Human-readable summary of all failures."""
        lines: list[str] = []
        for r in self.results:
            if not r.passed:
                lines.append(f"=== {r.tool} ===\n{r.output}")
        return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# Individual tool runners
# ---------------------------------------------------------------------------


def _run(cmd: list[str], cwd: Path) -> ToolResult:
    tool = cmd[0]
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )
    return ToolResult(
        tool=tool,
        passed=proc.returncode == 0,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )


def run_black(project_dir: Path) -> ToolResult:
    """Run ``black --check`` on *project_dir*."""
    return _run(["black", "--check", "."], project_dir)


def run_ruff(project_dir: Path) -> ToolResult:
    """Run ``ruff check`` on *project_dir*."""
    return _run(["ruff", "check", "."], project_dir)


def run_pytest(project_dir: Path) -> ToolResult:
    """Run ``pytest`` in *project_dir*."""
    return _run(["pytest", "--tb=short", "-q"], project_dir)


def verify(project_dir: str | Path) -> VerifyResult:
    """Run black, ruff, and pytest against *project_dir*.

    Parameters
    ----------
    project_dir:
        Root of the generated FastAPI project.

    Returns
    -------
    VerifyResult
        Aggregated pass/fail status and diagnostics.
    """
    root = Path(project_dir).resolve()
    return VerifyResult(
        results=[
            run_black(root),
            run_ruff(root),
            run_pytest(root),
        ]
    )


# ---------------------------------------------------------------------------
# Unified-diff repair helpers
# ---------------------------------------------------------------------------


def apply_diff(source: str, unified_diff: str) -> str:
    """Apply a unified diff to *source* and return the patched content.

    Uses the system ``patch`` command so the diff is applied correctly even
    for complex hunks.

    Parameters
    ----------
    source:
        Original file content.
    unified_diff:
        A unified diff string as produced by ``diff -u`` or an LLM.

    Returns
    -------
    str
        Patched file content.

    Raises
    ------
    RuntimeError
        If ``patch`` exits with a non-zero status.
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(source)
        tmp_path = Path(tmp.name)

    diff_path = tmp_path.with_suffix(".patch")
    diff_path.write_text(unified_diff, encoding="utf-8")

    try:
        proc = subprocess.run(
            ["patch", "-u", str(tmp_path), str(diff_path)],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"patch failed (exit {proc.returncode}):\n{proc.stdout}\n{proc.stderr}"
            )
        return tmp_path.read_text(encoding="utf-8")
    finally:
        tmp_path.unlink(missing_ok=True)
        diff_path.unlink(missing_ok=True)
        # also remove any .orig file created by patch
        orig = tmp_path.with_suffix(".py.orig")
        orig.unlink(missing_ok=True)


async def repair_loop(
    project_dir: str | Path,
    generated_files: dict[str, str],
    llm_client: object,
    model: str,
    max_iterations: int = 3,
) -> tuple[dict[str, str], VerifyResult]:
    """Attempt to repair generated files until verification passes.

    Parameters
    ----------
    project_dir:
        Root of the generated project (files already written to disk).
    generated_files:
        Mutable mapping of relative path → source that was written to disk.
        Updated in-place when repairs are applied.
    llm_client:
        An :class:`~engine.llm.client.OllamaClient` (already entered as
        async context manager).
    model:
        Ollama model name to use for repair prompts.
    max_iterations:
        Maximum number of repair attempts before giving up.

    Returns
    -------
    tuple[dict[str, str], VerifyResult]
        The (possibly repaired) files mapping and the final verification result.
    """
    from engine.prompts.templates import repair_prompt

    root = Path(project_dir).resolve()
    result = verify(root)

    for _iteration in range(1, max_iterations + 1):
        if result.passed:
            break

        for tool_result in result.results:
            if tool_result.passed:
                continue
            # Find which files are mentioned in the diagnostics and try to repair them
            for rel_path, source in list(generated_files.items()):
                if (
                    rel_path not in tool_result.output
                    and Path(rel_path).name not in tool_result.output
                ):
                    continue
                prompt = repair_prompt(rel_path, source, tool_result.output)
                diff_text: str = await llm_client.generate(
                    model=model,
                    prompt=prompt,
                )
                try:
                    patched = apply_diff(source, diff_text)
                except RuntimeError:
                    # Diff didn't apply cleanly — skip this file this round
                    continue
                generated_files[rel_path] = patched
                (root / rel_path).write_text(patched, encoding="utf-8")

        result = verify(root)

    return generated_files, result
