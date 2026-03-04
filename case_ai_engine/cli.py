"""Точка входа CLI для CASE AI Engine."""

from __future__ import annotations

import logging
from pathlib import Path

import typer
from rich.console import Console

from engine.orchestrator import run_pipeline

app = typer.Typer(help="CASE AI Engine — генерация FastAPI-проектов из спецификации.")
console = Console()
logger = logging.getLogger(__name__)


@app.command()
def generate(
    spec: str = typer.Argument(..., help="Путь к файлу спецификации (YAML/JSON)."),
    model: str = typer.Option(
        "codellama:7b-instruct", "--model", "-m", help="Имя модели Ollama."
    ),
    output: str = typer.Option(
        "outputs", "--output", "-o", help="Корневой каталог для результатов."
    ),
    max_iters: int = typer.Option(3, "--max-iters", help="Максимум repair-итераций."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Подробный лог."),
) -> None:
    """Сгенерировать FastAPI-проект из файла спецификации."""
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO)
    console.print(f"[bold]Спецификация:[/bold] {spec}")
    console.print(f"[bold]Модель:[/bold]       {model}")
    console.print(f"[bold]Вывод:[/bold]        {output}")

    try:
        run_id = run_pipeline(
            spec_path=spec,
            model=model,
            output_dir=output,
            max_iters=max_iters,
        )
        out_path = Path(output) / run_id
        console.print(f"\n[green]Готово![/green] Результат: [bold]{out_path}[/bold]")
        typer.echo(str(out_path))
    except Exception as exc:
        console.print(f"[red]Ошибка:[/red] {exc}")
        raise typer.Exit(code=1) from exc


if __name__ == "__main__":
    app()
