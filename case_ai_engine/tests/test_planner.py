"""Тесты детерминированного планировщика."""

from __future__ import annotations

from pathlib import Path

from engine.planner import PlanStep, build_plan
from engine.spec.loader import load_spec
from engine.spec.validator import validate_spec

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


class TestBuildPlan:
    """Тесты функции build_plan."""

    def _load_min(self):  # type: ignore[return]
        return load_spec(EXAMPLES_DIR / "spec_min.yaml")

    def test_возвращает_список_шагов(self) -> None:
        """build_plan возвращает непустой список PlanStep."""
        plan = build_plan(self._load_min())
        assert len(plan) > 0
        assert all(isinstance(s, PlanStep) for s in plan)

    def test_порядок_по_приоритету(self) -> None:
        """Шаги упорядочены по возрастанию приоритета."""
        plan = build_plan(self._load_min())
        priorities = [s.priority for s in plan]
        assert priorities == sorted(priorities)

    def test_содержит_pyproject(self) -> None:
        """План включает pyproject.toml."""
        paths = {s.file_path for s in build_plan(self._load_min())}
        assert "pyproject.toml" in paths

    def test_содержит_main(self) -> None:
        """План включает app/main.py."""
        paths = {s.file_path for s in build_plan(self._load_min())}
        assert "app/main.py" in paths

    def test_схема_для_каждой_сущности(self) -> None:
        """План включает app/schemas/<entity>.py для каждой сущности."""
        spec = self._load_min()
        paths = {s.file_path for s in build_plan(spec)}
        for entity in spec.entities:
            assert f"app/schemas/{entity.name.lower()}.py" in paths

    def test_роутер_для_каждой_сущности(self) -> None:
        """План включает app/routers/<entity>.py для каждой сущности."""
        spec = self._load_min()
        paths = {s.file_path for s in build_plan(spec)}
        for entity in spec.entities:
            assert f"app/routers/{entity.name.lower()}.py" in paths

    def test_содержит_smoke_тест(self) -> None:
        """План включает tests/test_smoke.py."""
        paths = {s.file_path for s in build_plan(self._load_min())}
        assert "tests/test_smoke.py" in paths

    def test_crud_тесты_при_tests_true(self) -> None:
        """При generation.tests=True план включает CRUD-тесты."""
        spec = self._load_min()
        assert spec.generation.tests is True
        paths = {s.file_path for s in build_plan(spec)}
        for entity in spec.entities:
            assert f"tests/test_{entity.name.lower()}_crud.py" in paths

    def test_без_crud_тестов_при_tests_false(self) -> None:
        """При generation.tests=False CRUD-тесты не включаются."""
        spec = self._load_min()
        spec.generation.tests = False
        paths = {s.file_path for s in build_plan(spec)}
        assert not any("crud" in p for p in paths)

    def test_зависимости_заданы(self) -> None:
        """Каждый шаг кроме pyproject.toml имеет зависимости."""
        plan = build_plan(self._load_min())
        for step in plan:
            if step.file_path == "pyproject.toml":
                assert step.depends_on == []
            else:
                assert len(step.depends_on) > 0

    def test_spec_без_сущностей(self) -> None:
        """build_plan работает для спецификации без сущностей."""
        spec = validate_spec({"service": {"name": "empty"}})
        paths = {s.file_path for s in build_plan(spec)}
        assert "pyproject.toml" in paths
        assert "app/main.py" in paths
        assert "tests/test_smoke.py" in paths

    def test_конкретные_пути_spec_min(self) -> None:
        """Для spec_min.yaml план содержит ожидаемые конкретные пути."""
        expected = {
            "pyproject.toml",
            "app/main.py",
            "app/schemas/item.py",
            "app/routers/item.py",
            "tests/test_smoke.py",
            "tests/test_item_crud.py",
        }
        paths = {s.file_path for s in build_plan(self._load_min())}
        assert expected.issubset(paths)
