"""Tests for engine.planner."""

from __future__ import annotations

from engine.planner.planner import TaskKind, plan
from engine.spec.schema import ApiSpec, EndpointDef, FieldDef, ModelDef


def _spec_with_both() -> ApiSpec:
    return ApiSpec(
        name="test_api",
        models=[ModelDef(name="Item", fields=[FieldDef(name="id", type="int")])],
        endpoints=[
            EndpointDef(path="/items", method="GET", response_model="list[Item]")
        ],
    )


def _spec_no_endpoints() -> ApiSpec:
    return ApiSpec(
        name="models_only",
        models=[ModelDef(name="Foo", fields=[])],
    )


def _spec_no_models() -> ApiSpec:
    return ApiSpec(
        name="no_models",
        endpoints=[EndpointDef(path="/ping", method="GET")],
    )


def test_plan_order_with_full_spec() -> None:
    tasks = plan(_spec_with_both())
    kinds = [t.kind for t in tasks]
    assert kinds == [TaskKind.MODELS, TaskKind.ROUTER, TaskKind.MAIN, TaskKind.TESTS]


def test_plan_no_endpoints_skips_router_and_tests() -> None:
    tasks = plan(_spec_no_endpoints())
    kinds = [t.kind for t in tasks]
    assert TaskKind.ROUTER not in kinds
    assert TaskKind.TESTS not in kinds
    assert TaskKind.MODELS in kinds
    assert TaskKind.MAIN in kinds


def test_plan_no_models_skips_models_task() -> None:
    tasks = plan(_spec_no_models())
    kinds = [t.kind for t in tasks]
    assert TaskKind.MODELS not in kinds
    assert TaskKind.MAIN in kinds


def test_plan_output_paths() -> None:
    tasks = plan(_spec_with_both())
    paths = {t.output_path for t in tasks}
    assert "models.py" in paths
    assert "routers/api.py" in paths
    assert "main.py" in paths
    assert "tests/test_api.py" in paths


def test_plan_prompt_builders_are_callable() -> None:
    tasks = plan(_spec_with_both())
    for task in tasks:
        prompt = task.prompt_builder()  # type: ignore[operator]
        assert isinstance(prompt, str)
        assert len(prompt) > 10


def test_plan_metadata() -> None:
    tasks = plan(_spec_with_both())
    models_task = next(t for t in tasks if t.kind == TaskKind.MODELS)
    assert models_task.metadata["model_count"] == 1

    router_task = next(t for t in tasks if t.kind == TaskKind.ROUTER)
    assert router_task.metadata["endpoint_count"] == 1
