"""Pydantic-модели для спецификации проекта."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EndpointSpec(BaseModel):
    """Спецификация одного API-эндпоинта."""

    path: str
    method: str = "GET"
    summary: str = ""
    tags: list[str] = Field(default_factory=list)


class ProjectSpec(BaseModel):
    """Корневая спецификация проекта."""

    name: str
    version: str = "0.1.0"
    description: str = ""
    endpoints: list[EndpointSpec] = Field(default_factory=list)
