"""Pydantic models that represent a validated DSL specification."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class FieldDef(BaseModel):
    """A single field in a DSL model definition."""

    name: str
    type: str  # Python type annotation string, e.g. "int", "str", "bool"
    optional: bool = False
    default: Any = None
    description: str = ""


class ModelDef(BaseModel):
    """A data model referenced by endpoints."""

    name: str
    fields: list[FieldDef] = Field(default_factory=list)
    description: str = ""


class EndpointDef(BaseModel):
    """A single HTTP endpoint definition."""

    path: str
    method: str = "GET"
    summary: str = ""
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    request_body: str | None = None  # model name
    response_model: str | None = None  # model name or "List[<model>]"
    status_code: int = 200

    @field_validator("method")
    @classmethod
    def _method_upper(cls, v: str) -> str:
        return v.upper()


class ApiSpec(BaseModel):
    """Root DSL specification object."""

    name: str
    version: str = "0.1.0"
    description: str = ""
    models: list[ModelDef] = Field(default_factory=list)
    endpoints: list[EndpointDef] = Field(default_factory=list)
    extra_dependencies: list[str] = Field(default_factory=list)
