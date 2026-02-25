"""PromptBuilder: рендеринг Jinja2-шаблонов промптов."""

from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent


class PromptBuilder:
    """Рендерит Jinja2-шаблоны промптов для генерации и ремонта."""

    def __init__(self, prompts_dir: Path = _PROMPTS_DIR) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(prompts_dir)),
            undefined=StrictUndefined,
            keep_trailing_newline=True,
        )

    def render_generate_file(
        self,
        file_path: str,
        purpose: str,
        spec_snippet: str,
        project_conventions: str = "",
    ) -> str:
        """Сформировать промпт для генерации файла.

        Args:
            file_path: относительный путь генерируемого файла.
            purpose: назначение файла (из PlanStep).
            spec_snippet: фрагмент спецификации, релевантный файлу.
            project_conventions: дополнительные соглашения проекта.
        """
        tmpl = self._env.get_template("generate_file.j2")
        result = tmpl.render(
            file_path=file_path,
            purpose=purpose,
            spec_snippet=spec_snippet,
            project_conventions=project_conventions,
        )
        logger.debug(
            "render_generate_file: file_path=%s len=%d", file_path, len(result)
        )
        return result

    def render_repair_diff(
        self,
        logs: str,
        failing_files: list[str],
        snippets: dict[str, str],
        constraints: str = "",
    ) -> str:
        """Сформировать промпт для repair-diff.

        Args:
            logs: вывод верификатора (black/ruff/pytest).
            failing_files: список путей файлов с ошибками.
            snippets: содержимое проблемных файлов {path: content}.
            constraints: дополнительные ограничения для LLM.
        """
        tmpl = self._env.get_template("repair_diff.j2")
        result = tmpl.render(
            logs=logs,
            failing_files=failing_files,
            snippets=snippets,
            constraints=constraints,
        )
        logger.debug("render_repair_diff: files=%s len=%d", failing_files, len(result))
        return result
