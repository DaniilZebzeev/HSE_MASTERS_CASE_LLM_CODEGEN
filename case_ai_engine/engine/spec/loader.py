"""Загрузчик спецификации: читает YAML или JSON в сырой словарь."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


def load_spec(path: Path) -> dict[str, Any]:
    """Загрузить файл спецификации YAML/JSON и вернуть сырой словарь."""
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")

    if suffix in {".yaml", ".yml"}:
        data = yaml.safe_load(text)
    elif suffix == ".json":
        data = json.loads(text)
    else:
        raise ValueError(f"Неподдерживаемый формат спецификации: {suffix!r}")

    if not isinstance(data, dict):
        raise ValueError(
            f"Спецификация должна быть словарём, получено: {type(data).__name__}"
        )

    logger.info("Спецификация загружена из %s", path)
    return data
