"""Планировщик: строит упорядоченный план генерации файлов по спецификации."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class Planner:
    """Преобразует провалидированную спецификацию в план генерации."""

    def plan(self, spec: dict) -> list[Path]:  # type: ignore[type-arg]
        """Вернуть упорядоченный список путей файлов для генерации."""
        logger.debug("Планирование по ключам спецификации: %s", list(spec.keys()))
        return []
