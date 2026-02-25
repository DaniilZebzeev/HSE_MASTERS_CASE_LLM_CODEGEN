"""Оркестратор: координирует планирование, генерацию и верификацию."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class Orchestrator:
    """Главный контроллер конвейера кодогенерации."""

    def __init__(self, model: str, output_dir: Path) -> None:
        self.model = model
        self.output_dir = output_dir

    def run(self, spec_path: Path) -> None:
        """Запустить полный конвейер генерации для заданной спецификации."""
        logger.info("Orchestrator.run: spec=%s", spec_path)
