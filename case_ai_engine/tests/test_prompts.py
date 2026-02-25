"""Тесты PromptBuilder и Jinja2-шаблонов промптов."""

from __future__ import annotations

import pytest

from engine.prompts.builder import PromptBuilder


class TestPromptBuilder:
    """Тесты класса PromptBuilder."""

    @pytest.fixture(autouse=True)
    def builder(self) -> None:
        """Инициализация PromptBuilder."""
        self.builder = PromptBuilder()

    # --- render_generate_file ---

    def test_generate_не_пустой(self) -> None:
        """render_generate_file возвращает непустую строку."""
        result = self.builder.render_generate_file(
            file_path="app/main.py",
            purpose="Точка входа FastAPI",
            spec_snippet="service: hello_api",
        )
        assert len(result) > 0

    def test_generate_содержит_file_path(self) -> None:
        """Промпт генерации содержит имя файла."""
        result = self.builder.render_generate_file(
            file_path="app/schemas/item.py",
            purpose="Схемы для Item",
            spec_snippet="entity: Item",
        )
        assert "app/schemas/item.py" in result

    def test_generate_содержит_purpose(self) -> None:
        """Промпт генерации содержит поле purpose."""
        purpose = "CRUD-роутер для сущности Item"
        result = self.builder.render_generate_file(
            file_path="app/routers/item.py",
            purpose=purpose,
            spec_snippet="",
        )
        assert purpose in result

    def test_generate_содержит_spec_snippet(self) -> None:
        """Промпт генерации содержит фрагмент спецификации."""
        snippet = "name: hello_api\nstack: python-fastapi"
        result = self.builder.render_generate_file(
            file_path="app/main.py",
            purpose="test",
            spec_snippet=snippet,
        )
        assert snippet in result

    def test_generate_содержит_return_only(self) -> None:
        """Промпт генерации содержит инструкцию Return ONLY."""
        result = self.builder.render_generate_file(
            file_path="app/main.py",
            purpose="test",
            spec_snippet="",
        )
        assert "Return ONLY" in result

    def test_generate_без_conventions(self) -> None:
        """render_generate_file работает без project_conventions."""
        result = self.builder.render_generate_file(
            file_path="app/main.py",
            purpose="test",
            spec_snippet="",
        )
        assert isinstance(result, str)

    def test_generate_с_conventions(self) -> None:
        """Промпт включает project_conventions, если передан."""
        conventions = "Используй async def для всех роутеров"
        result = self.builder.render_generate_file(
            file_path="app/main.py",
            purpose="test",
            spec_snippet="",
            project_conventions=conventions,
        )
        assert conventions in result

    # --- render_repair_diff ---

    def test_repair_не_пустой(self) -> None:
        """render_repair_diff возвращает непустую строку."""
        result = self.builder.render_repair_diff(
            logs="E501 line too long",
            failing_files=["app/main.py"],
            snippets={"app/main.py": "x = 1"},
        )
        assert len(result) > 0

    def test_repair_содержит_failing_file(self) -> None:
        """Промпт repair содержит имя проблемного файла."""
        result = self.builder.render_repair_diff(
            logs="error",
            failing_files=["app/routers/item.py"],
            snippets={"app/routers/item.py": "pass"},
        )
        assert "app/routers/item.py" in result

    def test_repair_содержит_логи(self) -> None:
        """Промпт repair содержит переданные логи ошибок."""
        logs = "AssertionError: expected 200, got 422"
        result = self.builder.render_repair_diff(
            logs=logs,
            failing_files=[],
            snippets={},
        )
        assert logs in result

    def test_repair_содержит_сниппет(self) -> None:
        """Промпт repair содержит содержимое переданного сниппета."""
        snippet = "def hello(): pass"
        result = self.builder.render_repair_diff(
            logs="error",
            failing_files=["app/main.py"],
            snippets={"app/main.py": snippet},
        )
        assert snippet in result

    def test_repair_содержит_return_only(self) -> None:
        """Промпт repair содержит инструкцию Return ONLY unified diff."""
        result = self.builder.render_repair_diff(
            logs="",
            failing_files=[],
            snippets={},
        )
        assert "Return ONLY" in result

    def test_repair_пустые_входы(self) -> None:
        """render_repair_diff работает с пустыми failing_files и snippets."""
        result = self.builder.render_repair_diff(
            logs="",
            failing_files=[],
            snippets={},
        )
        assert isinstance(result, str)

    def test_repair_с_constraints(self) -> None:
        """Промпт repair включает constraints, если передан."""
        constraint = "Не менять сигнатуры публичных функций"
        result = self.builder.render_repair_diff(
            logs="error",
            failing_files=[],
            snippets={},
            constraints=constraint,
        )
        assert constraint in result
