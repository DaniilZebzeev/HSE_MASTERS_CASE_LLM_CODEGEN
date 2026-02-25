"""CLI for the DSL → FastAPI code generator.

Usage examples::

    # Generate a FastAPI project from a YAML spec
    codegen generate examples/todo_api.yaml --model llama3 --output outputs/todo_api

    # Verify an already-generated project
    codegen verify outputs/todo_api

    # List available Ollama models
    codegen models
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _run_generation(
    spec_path: Path,
    model: str,
    output_dir: Path,
    max_repairs: int,
    ollama_url: str,
) -> int:
    """Core async generation logic.  Returns exit code (0 = success)."""
    from engine.llm.client import OllamaClient
    from engine.metrics.collector import RunMetrics, TaskMetrics
    from engine.planner.planner import plan
    from engine.project.writer import write_project
    from engine.prompts.templates import SYSTEM_PROMPT
    from engine.spec.loader import load_spec
    from engine.verify.runner import repair_loop, verify

    # --- Load spec ----------------------------------------------------------
    try:
        spec = load_spec(spec_path)
    except (FileNotFoundError, ValueError) as exc:
        console.print(f"[bold red]Error loading spec:[/] {exc}")
        return 1

    console.print(
        Panel(
            f"[bold]Project:[/] {spec.name} v{spec.version}\n"
            f"[bold]Models:[/] {len(spec.models)}  "
            f"[bold]Endpoints:[/] {len(spec.endpoints)}\n"
            f"[bold]LLM model:[/] {model}  "
            f"[bold]Output:[/] {output_dir}",
            title="[cyan]codegen[/]",
            expand=False,
        )
    )

    # --- Plan ---------------------------------------------------------------
    tasks = plan(spec)
    metrics = RunMetrics(spec_name=spec.name, model=model)
    generated: dict[str, str] = {}

    async with OllamaClient(base_url=ollama_url) as client:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            for gen_task in tasks:
                pid = progress.add_task(
                    f"Generating [cyan]{gen_task.output_path}[/]…", total=None
                )
                prompt = gen_task.prompt_builder()  # type: ignore[operator]
                t0 = time.perf_counter()
                try:
                    source = await client.generate(
                        model=model,
                        prompt=prompt,
                        system=SYSTEM_PROMPT,
                    )
                except Exception as exc:  # noqa: BLE001
                    console.print(
                        f"[red]LLM error for {gen_task.output_path}:[/] {exc}"
                    )
                    progress.remove_task(pid)
                    return 1

                latency = time.perf_counter() - t0
                generated[gen_task.output_path] = source
                task_m = TaskMetrics(
                    task_kind=gen_task.kind.value,
                    output_path=gen_task.output_path,
                    prompt_tokens_approx=len(prompt) // 4,
                    response_tokens_approx=len(source) // 4,
                    llm_latency_s=round(latency, 3),
                )
                progress.remove_task(pid)
                console.print(f"  [green]✓[/] {gen_task.output_path} ({latency:.1f}s)")

                metrics.record_task(task_m)

        # --- Write project --------------------------------------------------
        project_root = write_project(spec, generated, output_dir)
        console.print(f"\nProject written to [bold]{project_root}[/]")

        # --- Verify + repair-loop -------------------------------------------
        console.print("\n[bold]Running verification…[/]")
        if max_repairs > 0:
            generated, result = await repair_loop(
                project_root, generated, client, model, max_iterations=max_repairs
            )
        else:
            result = verify(project_root)

    # --- Report metrics -----------------------------------------------------
    metrics.finish()
    for task_m in metrics.tasks:
        task_m.final_passed = result.passed

    metrics_path = output_dir / "metrics.json"
    metrics.save(metrics_path)

    if result.passed:
        console.print("\n[bold green]✓ All checks passed![/]")
    else:
        console.print("\n[bold red]✗ Verification failed.[/]")
        console.print(result.diagnostics)

    console.print(f"\n{metrics.summary()}")
    console.print(f"Metrics saved to [bold]{metrics_path}[/]")
    return 0 if result.passed else 1


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------


@click.group()
def main() -> None:
    """DSL → FastAPI code generator powered by a local Ollama LLM."""


@main.command()
@click.argument("spec", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--model", "-m", default="llama3", show_default=True, help="Ollama model name."
)
@click.option(
    "--output",
    "-o",
    default=None,
    type=click.Path(path_type=Path),
    help="Output directory (default: outputs/<spec-stem>).",
)
@click.option(
    "--max-repairs",
    default=3,
    show_default=True,
    help="Maximum repair-loop iterations (0 to disable).",
)
@click.option(
    "--ollama-url",
    default="http://localhost:11434",
    show_default=True,
    envvar="OLLAMA_URL",
    help="Base URL of the Ollama server.",
)
def generate(
    spec: Path,
    model: str,
    output: Path | None,
    max_repairs: int,
    ollama_url: str,
) -> None:
    """Generate a FastAPI project from a DSL SPEC file."""
    if output is None:
        output = Path("outputs") / spec.stem
    exit_code = asyncio.run(
        _run_generation(spec, model, output, max_repairs, ollama_url)
    )
    raise SystemExit(exit_code)


@main.command()
@click.argument(
    "project_dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
def verify(project_dir: Path) -> None:
    """Run black / ruff / pytest against an already-generated PROJECT_DIR."""
    from engine.verify.runner import verify as _verify

    result = _verify(project_dir)
    for r in result.results:
        icon = "[green]✓[/]" if r.passed else "[red]✗[/]"
        console.print(f"  {icon} {r.tool}")
        if not r.passed:
            console.print(r.output)

    raise SystemExit(0 if result.passed else 1)


@main.command()
@click.option(
    "--ollama-url",
    default="http://localhost:11434",
    show_default=True,
    envvar="OLLAMA_URL",
)
def models(ollama_url: str) -> None:
    """List Ollama models available locally."""

    async def _list() -> None:
        from engine.llm.client import OllamaClient, OllamaError

        async with OllamaClient(base_url=ollama_url) as client:
            try:
                names = await client.list_models()
            except OllamaError as exc:
                console.print(f"[red]Error:[/] {exc}")
                raise SystemExit(1) from exc
        if not names:
            console.print("[yellow]No models found.[/]")
        else:
            for name in names:
                console.print(f"  • {name}")

    asyncio.run(_list())
