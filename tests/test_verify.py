"""Tests for engine.verify (no actual tools required for unit tests)."""

from __future__ import annotations

import pytest

from engine.verify.runner import (
    ToolResult,
    VerifyResult,
    apply_diff,
)

# ---------------------------------------------------------------------------
# ToolResult / VerifyResult unit tests
# ---------------------------------------------------------------------------


def test_tool_result_passed() -> None:
    r = ToolResult(tool="black", passed=True, stdout="All good.", stderr="")
    assert r.passed is True
    assert "All good." in r.output


def test_tool_result_failed() -> None:
    r = ToolResult(tool="ruff", passed=False, stdout="", stderr="E302 error")
    assert r.passed is False
    assert "E302" in r.output


def test_verify_result_passed_when_all_pass() -> None:
    vr = VerifyResult(
        results=[
            ToolResult("black", True),
            ToolResult("ruff", True),
            ToolResult("pytest", True),
        ]
    )
    assert vr.passed is True
    assert vr.diagnostics == ""


def test_verify_result_failed_when_one_fails() -> None:
    vr = VerifyResult(
        results=[
            ToolResult("black", True),
            ToolResult("ruff", False, stderr="F401 unused import"),
            ToolResult("pytest", True),
        ]
    )
    assert vr.passed is False
    assert "ruff" in vr.diagnostics
    assert "F401" in vr.diagnostics


# ---------------------------------------------------------------------------
# apply_diff tests
# ---------------------------------------------------------------------------


def test_apply_diff_simple_addition() -> None:
    """A valid unified diff should be applied correctly."""
    original = "a = 1\nb = 2\n"
    # Build the diff manually using difflib for portability
    import difflib

    patched_expected = "a = 1\nb = 3\n"
    diff_lines = list(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            patched_expected.splitlines(keepends=True),
            fromfile="orig",
            tofile="new",
        )
    )
    unified_diff = "".join(diff_lines)
    result = apply_diff(original, unified_diff)
    assert result == patched_expected


def test_apply_diff_invalid_raises() -> None:
    with pytest.raises(RuntimeError):
        apply_diff("hello\n", "this is not a valid diff at all!!!@@##")
