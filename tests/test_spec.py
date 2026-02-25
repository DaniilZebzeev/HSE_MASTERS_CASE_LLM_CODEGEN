"""Tests for engine.spec (loader + schema)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from engine.spec.loader import load_spec
from engine.spec.schema import ApiSpec, EndpointDef, FieldDef, ModelDef

# ---------------------------------------------------------------------------
# Schema unit tests
# ---------------------------------------------------------------------------


def test_field_def_defaults() -> None:
    f = FieldDef(name="id", type="int")
    assert f.optional is False
    assert f.default is None


def test_model_def() -> None:
    m = ModelDef(
        name="Todo",
        fields=[
            FieldDef(name="id", type="int", optional=True),
            FieldDef(name="title", type="str"),
        ],
    )
    assert len(m.fields) == 2
    assert m.fields[0].optional is True


def test_endpoint_method_is_uppercased() -> None:
    ep = EndpointDef(path="/items", method="get")
    assert ep.method == "GET"


def test_api_spec_minimal() -> None:
    spec = ApiSpec(name="my_api")
    assert spec.version == "0.1.0"
    assert spec.models == []
    assert spec.endpoints == []


def test_api_spec_full() -> None:
    spec = ApiSpec(
        name="todo",
        version="1.0.0",
        models=[ModelDef(name="Todo", fields=[FieldDef(name="id", type="int")])],
        endpoints=[
            EndpointDef(path="/todos", method="GET", response_model="list[Todo]")
        ],
    )
    assert spec.models[0].name == "Todo"
    assert spec.endpoints[0].response_model == "list[Todo]"


# ---------------------------------------------------------------------------
# Loader tests (using tmp files)
# ---------------------------------------------------------------------------


def _write_yaml(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "spec.yaml"
    p.write_text(yaml.dump(data), encoding="utf-8")
    return p


def _write_json(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "spec.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


VALID_DATA: dict = {
    "name": "todo_api",
    "version": "0.1.0",
    "models": [
        {
            "name": "Todo",
            "fields": [
                {"name": "id", "type": "int", "optional": True},
                {"name": "title", "type": "str"},
            ],
        }
    ],
    "endpoints": [
        {"path": "/todos", "method": "GET", "response_model": "list[Todo]"},
    ],
}


def test_load_yaml(tmp_path: Path) -> None:
    p = _write_yaml(tmp_path, VALID_DATA)
    spec = load_spec(p)
    assert spec.name == "todo_api"
    assert len(spec.models) == 1
    assert len(spec.endpoints) == 1


def test_load_json(tmp_path: Path) -> None:
    p = _write_json(tmp_path, VALID_DATA)
    spec = load_spec(p)
    assert spec.name == "todo_api"


def test_load_examples_todo_yaml() -> None:
    """The bundled example must load without errors."""
    here = Path(__file__).parent.parent
    spec = load_spec(here / "examples" / "todo_api.yaml")
    assert spec.name == "todo_api"
    assert len(spec.models) >= 1
    assert len(spec.endpoints) >= 1


def test_load_examples_notes_json() -> None:
    here = Path(__file__).parent.parent
    spec = load_spec(here / "examples" / "notes_api.json")
    assert spec.name == "notes_api"


def test_load_missing_file() -> None:
    with pytest.raises(FileNotFoundError):
        load_spec("/nonexistent/path/spec.yaml")


def test_load_invalid_yaml(tmp_path: Path) -> None:
    p = tmp_path / "bad.yaml"
    p.write_text("name: [unclosed", encoding="utf-8")
    with pytest.raises(ValueError):
        load_spec(p)


def test_load_missing_required_field(tmp_path: Path) -> None:
    """A spec without 'name' must raise ValueError (Pydantic validation)."""
    p = _write_json(tmp_path, {"version": "1.0.0"})
    with pytest.raises((ValueError, Exception)):  # pydantic ValidationError
        load_spec(p)
