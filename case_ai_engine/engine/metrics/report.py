"""Запись отчётов: report.json и report.md."""

from __future__ import annotations

import dataclasses
import json
import logging
from pathlib import Path

from engine.metrics.metrics import RunMetrics

logger = logging.getLogger(__name__)


def write_report_json(run_dir: Path, data: RunMetrics) -> Path:
    """Записать метрики в run_dir/report.json.

    Args:
        run_dir: каталог запуска.
        data: метрики запуска.

    Returns:
        Путь к созданному файлу.
    """
    path = run_dir / "report.json"
    path.write_text(
        json.dumps(dataclasses.asdict(data), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("report.json записан: %s", path)
    return path


def write_report_md(run_dir: Path, data: RunMetrics) -> Path:
    """Записать читаемый отчёт в run_dir/report.md.

    Args:
        run_dir: каталог запуска.
        data: метрики запуска.

    Returns:
        Путь к созданному файлу.
    """
    status = "✅ PASS" if data.success else "❌ FAIL"
    fp = data.fail_profile

    lines = [
        f"# Отчёт генерации — {data.run_id}",
        "",
        f"**Запуск:** {data.started_at}  ",
        f"**Модель:** {data.model}  ",
        f"**Спецификация:** {data.spec_path}",
        "",
        "## Результат",
        "",
        "| Параметр              | Значение |",
        "|-----------------------|----------|",
        f"| Статус                | {status} |",
        f"| Время (сек)           | {data.time_total_sec:.1f} |",
        f"| Repair-итераций       | {data.iterations} |",
        f"| Файлов сгенерировано  | {data.files_generated} |",
        f"| Строк в патчах        | {data.patch_volume_lines} |",
        "",
        "## Профиль ошибок",
        "",
        "| Инструмент             | Провалов |",
        "|------------------------|----------|",
        f"| Форматирование (black) | {fp.get('format', 0)} |",
        f"| Линтер (ruff)          | {fp.get('lint', 0)} |",
        f"| Тесты (pytest)         | {fp.get('tests', 0)} |",
        "",
    ]

    path = run_dir / "report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("report.md записан: %s", path)
    return path
