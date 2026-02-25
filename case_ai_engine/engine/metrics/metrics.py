"""Сбор метрик конвейера кодогенерации."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class GenerationMetrics:
    """Метрики одной попытки генерации файла."""

    file_path: str
    model: str
    iterations: int = 0  # Число итераций repair-loop
    llm_calls: int = 0  # Суммарное число обращений к LLM
    total_tokens: int = 0  # Суммарное число токенов (если доступно)
    elapsed_seconds: float = 0.0
    passed: bool = False
    errors: list[str] = field(default_factory=list)


class MetricsCollector:
    """Собирает и хранит метрики всего запуска конвейера."""

    def __init__(self) -> None:
        self._records: list[GenerationMetrics] = []
        self._start: float = time.monotonic()

    def record(self, metrics: GenerationMetrics) -> None:
        """Добавить запись метрик."""
        self._records.append(metrics)

    def all(self) -> list[GenerationMetrics]:
        """Вернуть все записи метрик."""
        return list(self._records)

    def elapsed(self) -> float:
        """Вернуть суммарное прошедшее время в секундах."""
        return time.monotonic() - self._start
