"""Валидатор DSL-спецификации: парсинг, нормализация, семантика."""

from __future__ import annotations

import logging
from typing import Any

from engine.spec.models import Spec

logger = logging.getLogger(__name__)


def validate_spec(raw: dict[str, Any]) -> Spec:
    """Провалидировать сырой словарь и вернуть нормализованный Spec.

    Выполняет:
    - парсинг через Pydantic (типы, структура);
    - проверку уникальности имён сущностей и эндпоинтов;
    - нормализацию method эндпоинтов в верхний регистр;
    - проверку, что endpoint.request.entity объявлена в entities.

    Raises:
        pydantic.ValidationError: при нарушении типов или структуры.
        ValueError: при нарушении семантических ограничений.
    """
    spec = Spec.model_validate(raw)

    # Уникальность имён сущностей
    entity_names = [e.name for e in spec.entities]
    duplicates = [n for n in entity_names if entity_names.count(n) > 1]
    if duplicates:
        raise ValueError(
            f"Имена сущностей должны быть уникальны: {list(set(duplicates))}"
        )

    # Уникальность имён эндпоинтов
    endpoint_names = [ep.name for ep in spec.endpoints]
    dup_ep = [n for n in endpoint_names if endpoint_names.count(n) > 1]
    if dup_ep:
        raise ValueError(f"Имена эндпоинтов должны быть уникальны: {list(set(dup_ep))}")

    # Нормализация method + проверка request.entity
    entity_set = set(entity_names)
    for ep in spec.endpoints:
        ep.method = ep.method.upper()
        if ep.request and ep.request.entity:
            if ep.request.entity not in entity_set:
                raise ValueError(
                    f"Эндпоинт '{ep.name}': entity '{ep.request.entity}' "
                    "не найдена в списке сущностей"
                )

    logger.info(
        "Спецификация провалидирована: service=%s entities=%d endpoints=%d",
        spec.service.name,
        len(spec.entities),
        len(spec.endpoints),
    )
    return spec
