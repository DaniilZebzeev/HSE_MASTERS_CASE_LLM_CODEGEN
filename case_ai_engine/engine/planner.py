"""Планировщик: детерминированный план генерации файлов из спецификации."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from engine.spec.models import Spec

logger = logging.getLogger(__name__)


@dataclass
class PlanStep:
    """Один шаг плана генерации файлов."""

    file_path: str
    purpose: str
    depends_on: list[str] = field(default_factory=list)
    priority: int = 0


def build_plan(spec: Spec) -> list[PlanStep]:
    """Построить детерминированный план генерации файлов по спецификации.

    Порядок шагов:
    1. pyproject.toml
    2. app/main.py
    3. app/schemas/<entity>.py  — по каждой сущности
    4. app/routers/<entity>.py  — по каждой сущности
    5. tests/test_smoke.py
    6. tests/test_<entity>_crud.py — если generation.tests=True
    """
    steps: list[PlanStep] = []

    # 1. pyproject.toml
    steps.append(
        PlanStep(
            file_path="pyproject.toml",
            purpose="Конфигурация проекта: зависимости, инструменты",
            depends_on=[],
            priority=0,
        )
    )

    # 2. app/main.py
    steps.append(
        PlanStep(
            file_path="app/main.py",
            purpose="Точка входа FastAPI-приложения",
            depends_on=["pyproject.toml"],
            priority=10,
        )
    )

    # 3. app/schemas/<entity>.py
    for entity in spec.entities:
        name = entity.name.lower()
        steps.append(
            PlanStep(
                file_path=f"app/schemas/{name}.py",
                purpose=f"Pydantic-схемы для сущности {entity.name}",
                depends_on=["app/main.py"],
                priority=20,
            )
        )

    # 4. app/routers/<entity>.py
    for entity in spec.entities:
        name = entity.name.lower()
        steps.append(
            PlanStep(
                file_path=f"app/routers/{name}.py",
                purpose=f"CRUD-роутер для сущности {entity.name}",
                depends_on=[f"app/schemas/{name}.py"],
                priority=30,
            )
        )

    # 5. tests/test_smoke.py
    steps.append(
        PlanStep(
            file_path="tests/test_smoke.py",
            purpose="Дымовой тест: проверка запуска приложения",
            depends_on=["app/main.py"],
            priority=40,
        )
    )

    # 6. tests/test_<entity>_crud.py (если generation.tests=True)
    if spec.generation.tests:
        for entity in spec.entities:
            name = entity.name.lower()
            steps.append(
                PlanStep(
                    file_path=f"tests/test_{name}_crud.py",
                    purpose=f"CRUD-тесты для сущности {entity.name}",
                    depends_on=[f"app/routers/{name}.py"],
                    priority=50,
                )
            )

    steps.sort(key=lambda s: s.priority)
    logger.info(
        "Построен план: %d шагов для сервиса '%s'",
        len(steps),
        spec.service.name,
    )
    return steps
