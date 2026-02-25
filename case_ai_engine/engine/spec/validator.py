"""Валидатор спецификации: разбирает сырой словарь в типизированную ProjectSpec."""

from __future__ import annotations

import logging
from typing import Any

from engine.spec.models import ProjectSpec

logger = logging.getLogger(__name__)


def validate_spec(raw: dict[str, Any]) -> ProjectSpec:
    """Провалидировать и разобрать сырой словарь в объект ProjectSpec."""
    spec = ProjectSpec.model_validate(raw)
    logger.info(
        "Спецификация провалидирована: name=%s endpoints=%d",
        spec.name,
        len(spec.endpoints),
    )
    return spec
