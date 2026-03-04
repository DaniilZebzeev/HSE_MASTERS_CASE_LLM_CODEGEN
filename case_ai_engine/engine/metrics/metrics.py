"""Модель метрик запуска конвейера кодогенерации."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RunMetrics:
    """Метрики одного запуска pipeline.

    Attributes:
        run_id: уникальный идентификатор запуска.
        model: имя модели Ollama.
        spec_path: путь к файлу спецификации.
        success: True, если верификация прошла успешно.
        iterations: число выполненных repair-итераций (0 = успех с первой попытки).
        time_total_sec: суммарное время выполнения в секундах.
        fail_profile: число провалов каждого инструмента {"format", "lint", "tests"}.
        patch_volume_lines: суммарное число строк во всех применённых патчах.
        files_generated: число сгенерированных файлов.
        started_at: ISO-метка времени начала запуска (UTC).
    """

    run_id: str
    model: str
    spec_path: str
    success: bool
    iterations: int
    time_total_sec: float
    fail_profile: dict[str, int]
    patch_volume_lines: int
    files_generated: int
    started_at: str
