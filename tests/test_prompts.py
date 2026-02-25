"""Tests for engine.prompts.templates."""

from __future__ import annotations

from engine.prompts.templates import (
    SYSTEM_PROMPT,
    main_prompt,
    models_prompt,
    repair_prompt,
    router_prompt,
    tests_prompt,
)
from engine.spec.schema import ApiSpec, EndpointDef, FieldDef, ModelDef


def _sample_spec() -> ApiSpec:
    return ApiSpec(
        name="test_api",
        version="0.2.0",
        description="A test API",
        models=[
            ModelDef(
                name="Item",
                fields=[
                    FieldDef(name="id", type="int", optional=True),
                    FieldDef(name="name", type="str"),
                ],
            )
        ],
        endpoints=[
            EndpointDef(path="/items", method="GET", response_model="list[Item]"),
            EndpointDef(
                path="/items",
                method="POST",
                request_body="Item",
                response_model="Item",
            ),
        ],
    )


def test_system_prompt_is_nonempty() -> None:
    assert len(SYSTEM_PROMPT) > 50


def test_models_prompt_contains_model_name() -> None:
    p = models_prompt(_sample_spec())
    assert "Item" in p
    assert "models.py" in p


def test_router_prompt_contains_endpoints() -> None:
    p = router_prompt(_sample_spec())
    assert "/items" in p
    assert "GET" in p
    assert "POST" in p
    assert "routers/api.py" in p


def test_main_prompt_contains_project_name() -> None:
    p = main_prompt(_sample_spec())
    assert "test_api" in p
    assert "main.py" in p
    assert "0.2.0" in p


def test_tests_prompt_contains_paths() -> None:
    p = tests_prompt(_sample_spec())
    assert "/items" in p
    assert "test_api.py" in p


def test_repair_prompt_structure() -> None:
    p = repair_prompt("main.py", "def foo():\n    pass\n", "E302 missing blank lines")
    assert "main.py" in p
    assert "E302" in p
    assert "diff" in p.lower()
