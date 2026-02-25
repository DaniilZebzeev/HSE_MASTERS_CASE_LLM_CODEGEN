"""Тесты загрузки и валидации DSL-спецификации."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.spec.loader import load_spec
from engine.spec.models import Spec
from engine.spec.validator import validate_spec

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


class TestLoadSpec:
    """Тесты функции load_spec."""

    def test_загрузка_yaml(self) -> None:
        """load_spec успешно читает examples/spec_min.yaml."""
        spec = load_spec(EXAMPLES_DIR / "spec_min.yaml")
        assert isinstance(spec, Spec)
        assert spec.service.name == "hello_api"

    def test_загрузка_json(self, tmp_path: Path) -> None:
        """load_spec успешно читает JSON-файл."""
        data = {"service": {"name": "json_svc"}}
        json_file = tmp_path / "spec.json"
        json_file.write_text(json.dumps(data), encoding="utf-8")
        spec = load_spec(json_file)
        assert spec.service.name == "json_svc"

    def test_неверное_расширение(self, tmp_path: Path) -> None:
        """load_spec выбрасывает ValueError для неизвестного расширения."""
        bad = tmp_path / "spec.toml"
        bad.write_text("[service]", encoding="utf-8")
        with pytest.raises(ValueError, match="Неподдерживаемый формат"):
            load_spec(bad)

    def test_путь_как_строка(self) -> None:
        """load_spec принимает путь в виде строки."""
        spec = load_spec(str(EXAMPLES_DIR / "spec_min.yaml"))
        assert spec.service.name == "hello_api"


class TestValidateSpec:
    """Тесты функции validate_spec."""

    def test_нормализация_method(self) -> None:
        """validate_spec нормализует method в верхний регистр."""
        raw = {
            "service": {"name": "svc"},
            "endpoints": [{"name": "ep1", "method": "get", "path": "/"}],
        }
        spec = validate_spec(raw)
        assert spec.endpoints[0].method == "GET"

    def test_дублирование_сущностей(self) -> None:
        """validate_spec выбрасывает ValueError при дубликате имён сущностей."""
        raw = {
            "service": {"name": "svc"},
            "entities": [
                {"name": "Item", "fields": []},
                {"name": "Item", "fields": []},
            ],
        }
        with pytest.raises(ValueError, match="уникальны"):
            validate_spec(raw)

    def test_дублирование_эндпоинтов(self) -> None:
        """validate_spec выбрасывает ValueError при дубликате имён эндпоинтов."""
        raw = {
            "service": {"name": "svc"},
            "endpoints": [
                {"name": "ep", "method": "GET", "path": "/a"},
                {"name": "ep", "method": "POST", "path": "/b"},
            ],
        }
        with pytest.raises(ValueError, match="уникальны"):
            validate_spec(raw)

    def test_несуществующая_entity_в_request(self) -> None:
        """validate_spec выбрасывает ValueError, если request.entity не существует."""
        raw = {
            "service": {"name": "svc"},
            "entities": [],
            "endpoints": [
                {
                    "name": "create",
                    "method": "POST",
                    "path": "/items",
                    "request": {"entity": "Missing"},
                }
            ],
        }
        with pytest.raises(ValueError, match="не найдена"):
            validate_spec(raw)

    def test_валидная_спецификация(self) -> None:
        """validate_spec корректно обрабатывает полную валидную спецификацию."""
        raw = {
            "service": {
                "name": "svc",
                "description": "test",
                "stack": "python-fastapi",
            },
            "entities": [
                {
                    "name": "Item",
                    "fields": [{"name": "id", "type": "int", "required": True}],
                }
            ],
            "endpoints": [
                {
                    "name": "create_item",
                    "method": "post",
                    "path": "/items",
                    "request": {"entity": "Item"},
                    "responses": [{"status_code": 201, "entity": "Item"}],
                }
            ],
            "generation": {
                "tests": True,
                "style": {"formatter": "black", "linter": "ruff"},
                "repair_loop": {"max_iters": 3},
            },
        }
        spec = validate_spec(raw)
        assert spec.service.name == "svc"
        assert spec.endpoints[0].method == "POST"
        assert spec.entities[0].name == "Item"

    def test_значения_по_умолчанию(self) -> None:
        """Spec содержит корректные значения по умолчанию."""
        raw = {"service": {"name": "min"}}
        spec = validate_spec(raw)
        assert spec.service.stack == "python-fastapi"
        assert spec.generation.tests is True
        assert spec.generation.repair_loop.max_iters == 3
        assert spec.generation.style.formatter == "black"
