"""Оркестратор: координирует планирование, генерацию и верификацию."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import yaml

from engine.llm.ollama_client import OllamaClient
from engine.metrics.metrics import RunMetrics
from engine.metrics.report import write_report_json, write_report_md
from engine.planner import build_plan
from engine.project.diff import apply_diff_to_project
from engine.project.writer import ProjectWriter
from engine.prompts.builder import PromptBuilder
from engine.spec.loader import load_spec
from engine.verify.parsers import parse_pytest, parse_ruff
from engine.verify.runner import VerifyResult, verify_project

logger = logging.getLogger(__name__)


def _failing_files(results: list[VerifyResult]) -> list[str]:
    """Извлечь пути проблемных файлов из результатов верификации."""
    files: set[str] = set()
    for r in results:
        if r.ok:
            continue
        if r.tool == "ruff":
            for err in parse_ruff(r.stdout + "\n" + r.stderr):
                fp = err.split(":")[0]
                if fp:
                    files.add(fp)
        elif r.tool == "pytest":
            for test_id in parse_pytest(r.stdout):
                fp = test_id.split("::")[0]
                if fp:
                    files.add(fp)
        elif r.tool == "black":
            for line in (r.stdout + r.stderr).splitlines():
                if "would reformat" in line:
                    parts = line.split()
                    if parts:
                        files.add(parts[-1])
    return sorted(files)


def run_pipeline(
    spec_path: str | Path,
    model: str,
    output_dir: str | Path = "outputs",
    max_iters: int = 3,
) -> str:
    """Запустить полный конвейер кодогенерации.

    Args:
        spec_path: путь к файлу спецификации YAML/JSON.
        model: имя модели Ollama.
        output_dir: корневой каталог для результатов.
        max_iters: максимум итераций repair-loop.

    Returns:
        run_id — уникальный идентификатор запуска (имя подкаталога).
    """
    spec_path = Path(spec_path)
    output_dir = Path(output_dir)

    t_start = time.monotonic()
    started_at = datetime.now(UTC).isoformat()

    # 1. Загрузка и валидация спецификации
    logger.info("Загрузка спецификации: %s", spec_path)
    spec = load_spec(spec_path)

    # 2. Детерминированный план генерации
    steps = build_plan(spec)
    logger.info("План: %d шагов для сервиса '%s'", len(steps), spec.service.name)

    # 3. Создание run-каталога
    run_id = uuid.uuid4().hex[:12]
    run_dir = output_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Run dir: %s", run_dir)

    # Полная спецификация как фрагмент для промптов
    spec_snippet = yaml.dump(
        spec.model_dump(), allow_unicode=True, default_flow_style=False
    )

    builder = PromptBuilder()
    writer = ProjectWriter(run_dir)

    # Метрики (накапливаются в процессе)
    fail_profile: dict[str, int] = {"format": 0, "lint": 0, "tests": 0}
    repair_iters: int = 0
    patch_lines: int = 0
    files_generated: int = 0
    success: bool = False

    # 4. Генерация файлов по плану
    with OllamaClient(model=model) as client:
        for step in steps:
            prompt = builder.render_generate_file(
                file_path=step.file_path,
                purpose=step.purpose,
                spec_snippet=spec_snippet,
            )
            logger.info("Генерация: %s", step.file_path)
            content = client.generate(prompt)
            writer.write(step.file_path, content)
            files_generated += 1

        # 5. Верификация + repair-loop
        for iteration in range(max_iters):
            results = verify_project(run_dir)
            all_ok = all(r.ok for r in results)

            if all_ok:
                success = True
                logger.info("Верификация успешна (итерация %d)", iteration)
                break

            # Обновляем профиль ошибок
            for r in results:
                if not r.ok:
                    if r.tool == "black":
                        fail_profile["format"] += 1
                    elif r.tool == "ruff":
                        fail_profile["lint"] += 1
                    elif r.tool == "pytest":
                        fail_profile["tests"] += 1

            if iteration == max_iters - 1:
                logger.warning(
                    "Исчерпан лимит repair-итераций (%d). Завершаем с ошибками.",
                    max_iters,
                )
                break

            # Формируем repair-контекст
            logs = "\n".join(
                f"[{r.tool}]\n{r.stdout}{r.stderr}" for r in results if not r.ok
            )
            fail_files = _failing_files(results)
            snippets = {
                fp: (run_dir / fp).read_text(encoding="utf-8")
                for fp in fail_files
                if (run_dir / fp).exists()
            }
            logger.info(
                "Repair-итерация %d: файлов с ошибками %d",
                iteration + 1,
                len(fail_files),
            )

            repair_prompt = builder.render_repair_diff(
                logs=logs,
                failing_files=fail_files,
                snippets=snippets,
            )
            diff_text = client.generate(repair_prompt)

            # Считаем объём патча (+строки, исключая заголовок +++)
            patch_lines += sum(
                1
                for ln in diff_text.splitlines()
                if ln.startswith("+") and not ln.startswith("+++")
            )
            apply_diff_to_project(diff_text, run_dir)
            repair_iters += 1

    # 6. Запись отчётов
    metrics = RunMetrics(
        run_id=run_id,
        model=model,
        spec_path=str(spec_path),
        success=success,
        iterations=repair_iters,
        time_total_sec=round(time.monotonic() - t_start, 3),
        fail_profile=fail_profile,
        patch_volume_lines=patch_lines,
        files_generated=files_generated,
        started_at=started_at,
    )
    write_report_json(run_dir, metrics)
    write_report_md(run_dir, metrics)

    return run_id
