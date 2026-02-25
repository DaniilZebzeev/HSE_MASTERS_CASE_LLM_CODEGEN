"""Запись файлов: создаёт файлы в выходном каталоге."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ProjectWriter:
    """Записывает сгенерированное содержимое файлов на диск."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write(self, relative_path: str, content: str) -> Path:
        """Записать содержимое в файл относительно output_dir."""
        target = self.output_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        logger.info("Записан %s (%d байт)", target, len(content))
        return target
