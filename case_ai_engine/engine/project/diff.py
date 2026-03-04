"""Утилиты diff: применение unified diff к файлам проекта."""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Паттерн заголовка ханка: @@ -start[,count] +start[,count] @@
_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def apply_diff(original: str, diff_text: str) -> str:
    """Применить unified diff к исходному содержимому файла.

    Args:
        original: исходное содержимое файла.
        diff_text: unified diff для одного файла.

    Returns:
        Новое содержимое файла после применения патча.
    """
    result = original.splitlines(keepends=True)
    diff_lines = diff_text.splitlines(keepends=True)
    offset = 0
    i = 0

    while i < len(diff_lines):
        m = _HUNK_RE.match(diff_lines[i])
        if not m:
            i += 1
            continue

        orig_start = int(m.group(1)) - 1  # конвертация в 0-индекс
        i += 1

        old_lines: list[str] = []
        new_lines: list[str] = []

        while i < len(diff_lines):
            ln = diff_lines[i]
            tag = ln[0] if ln else ""
            if tag == "@":
                break
            if ln.startswith("---") or ln.startswith("+++"):
                break
            if tag == "-":
                old_lines.append(ln[1:])
            elif tag == "+":
                new_lines.append(ln[1:])
            elif tag == " ":
                old_lines.append(ln[1:])
                new_lines.append(ln[1:])
            i += 1

        actual_start = orig_start + offset
        result[actual_start : actual_start + len(old_lines)] = new_lines
        offset += len(new_lines) - len(old_lines)

    return "".join(result)


def apply_diff_to_project(diff_text: str, project_root: Path) -> list[Path]:
    """Разобрать мульти-файловый unified diff и применить к файлам проекта.

    Args:
        diff_text: unified diff (может затрагивать несколько файлов).
        project_root: корневой каталог проекта.

    Returns:
        Список изменённых файлов.
    """
    changed: list[Path] = []
    current_path: str | None = None
    diff_block: list[str] = []

    def _flush() -> None:
        if current_path and diff_block:
            target = project_root / current_path
            original = target.read_text(encoding="utf-8") if target.exists() else ""
            new_content = apply_diff(original, "".join(diff_block))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(new_content, encoding="utf-8")
            changed.append(target)
            logger.info("Применён diff к %s", target)

    for line in diff_text.splitlines(keepends=True):
        if line.startswith("--- "):
            _flush()
            diff_block = [line]
            current_path = None
        elif line.startswith("+++ ") and diff_block is not None:
            raw = line[4:].strip()
            current_path = raw[2:] if raw.startswith("b/") else raw
            diff_block.append(line)
        else:
            diff_block.append(line)

    _flush()
    return changed
