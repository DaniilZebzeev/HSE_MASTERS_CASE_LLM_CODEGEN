"""Точка входа CLI для CASE AI Engine."""

from __future__ import annotations

import logging

import typer

app = typer.Typer(help="CASE AI Engine — генерация FastAPI-проектов из спецификации.")

logger = logging.getLogger(__name__)


@app.command()
def generate(
    spec: str = typer.Argument(..., help="Путь к файлу спецификации (YAML/JSON)."),
    output: str = typer.Option("outputs/", help="Каталог для вывода результатов."),
    model: str = typer.Option("codellama", help="Имя модели Ollama."),
) -> None:
    """Сгенерировать FastAPI-проект из файла спецификации."""
    logging.basicConfig(level=logging.INFO)
    logger.info("Запуск генерации: spec=%s output=%s model=%s", spec, output, model)
    typer.echo(f"Генерирую проект из {spec!r} с моделью {model!r}...")


if __name__ == "__main__":
    app()
