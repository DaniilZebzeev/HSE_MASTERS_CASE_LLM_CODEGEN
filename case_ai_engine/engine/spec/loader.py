"""Загрузчик спецификации: читает YAML/JSON и возвращает Spec."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import yaml

from engine.spec.models import Spec
from engine.spec.validator import validate_spec

logger = logging.getLogger(__name__)


def load_spec(path: str | Path) -> Spec:
    """Загрузить файл спецификации YAML/JSON и вернуть провалидированный Spec."""
    path = Path(path)
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")

    if suffix in {".yaml", ".yml"}:
        raw = yaml.safe_load(text)
    elif suffix == ".json":
        raw = json.loads(text)
    else:
        raise ValueError(f"Неподдерживаемый формат спецификации: {suffix!r}")

    if not isinstance(raw, dict):
        raise ValueError(
            f"Спецификация должна быть словарём, получено: {type(raw).__name__}"
        )

    logger.info("Спецификация загружена из %s", path)
    return validate_spec(raw)
