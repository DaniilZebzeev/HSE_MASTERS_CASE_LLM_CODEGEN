"""DSL-модели спецификации проекта (Pydantic v2)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FieldConstraints(BaseModel):
    """Ограничения значений поля сущности."""

    min_length: int | None = None
    max_length: int | None = None
    ge: float | None = None
    le: float | None = None
    pattern: str | None = None


class FieldSpec(BaseModel):
    """Поле сущности доменной модели."""

    name: str
    type: str
    required: bool = True
    constraints: FieldConstraints | None = None


class Entity(BaseModel):
    """Сущность доменной модели."""

    name: str
    fields: list[FieldSpec] = Field(default_factory=list)


class RequestSpec(BaseModel):
    """Тело запроса эндпоинта."""

    entity: str | None = None


class ResponseSpec(BaseModel):
    """Спецификация HTTP-ответа."""

    status_code: int = 200
    entity: str | None = None


class Endpoint(BaseModel):
    """Спецификация API-эндпоинта."""

    name: str
    method: str
    path: str
    request: RequestSpec | None = None
    responses: list[ResponseSpec] = Field(default_factory=list)
    auth: str | None = None


class StyleConfig(BaseModel):
    """Конфигурация стилевых инструментов."""

    formatter: str = "black"
    linter: str = "ruff"


class RepairLoop(BaseModel):
    """Настройки цикла авторемонта."""

    max_iters: int = 3


class Generation(BaseModel):
    """Настройки генерации кода."""

    tests: bool = True
    style: StyleConfig = Field(default_factory=StyleConfig)
    repair_loop: RepairLoop = Field(default_factory=RepairLoop)


class Service(BaseModel):
    """Метаданные сервиса."""

    name: str
    description: str = ""
    stack: str = "python-fastapi"


class Spec(BaseModel):
    """Корневая спецификация проекта (DSL)."""

    service: Service
    entities: list[Entity] = Field(default_factory=list)
    endpoints: list[Endpoint] = Field(default_factory=list)
    generation: Generation = Field(default_factory=Generation)
