"""HTTP-клиент Ollama для локального инференса LLM.

Быстрый старт::

    ollama pull codellama:7b-instruct   # скачать модель
    ollama serve                         # запустить сервер (порт 11434)
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://localhost:11434"
# Разумный лимит токенов ответа (~4 кБ кода)
DEFAULT_NUM_PREDICT = 1024


class OllamaClient:
    """Тонкая обёртка над REST API Ollama (/api/generate).

    Пример использования::

        with OllamaClient(model="codellama:7b-instruct") as client:
            text = client.generate("Write a hello world in Python")
    """

    def __init__(
        self,
        model: str,
        base_url: str = DEFAULT_BASE_URL,
        temperature: float = 0.0,
        num_predict: int = DEFAULT_NUM_PREDICT,
        timeout: float = 120.0,
    ) -> None:
        """Инициализировать клиент.

        Args:
            model: имя модели Ollama, например "codellama:7b-instruct".
            base_url: базовый URL сервера Ollama.
            temperature: температура (0 = детерминированно).
            num_predict: максимум генерируемых токенов.
            timeout: таймаут HTTP-запроса в секундах.
        """
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.num_predict = num_predict
        self._client = httpx.Client(timeout=timeout)

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Отправить промпт и вернуть текстовый ответ модели.

        Args:
            prompt: строка промпта.
            **kwargs: дополнительные параметры Ollama API.

        Returns:
            Текст ответа модели.

        Raises:
            ConnectionError: Ollama недоступен.
            TimeoutError: сервер не ответил в отведённое время.
            RuntimeError: сервер вернул HTTP-ошибку.
        """
        url = f"{self.base_url}/api/generate"
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.num_predict,
            },
            **kwargs,
        }
        logger.debug("POST %s model=%s prompt_len=%d", url, self.model, len(prompt))
        try:
            response = self._client.post(url, json=payload)
        except httpx.ConnectError as exc:
            raise ConnectionError(
                f"Ollama недоступен по адресу {self.base_url}. "
                "Убедитесь, что сервер запущен: ollama serve"
            ) from exc
        except httpx.TimeoutException as exc:
            raise TimeoutError(
                "Ollama не ответил за отведённое время. "
                "Увеличьте timeout или уменьшите num_predict."
            ) from exc
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Ollama вернул ошибку {exc.response.status_code}: "
                f"{exc.response.text}"
            ) from exc
        data: dict[str, Any] = response.json()
        return str(data.get("response", ""))

    def close(self) -> None:
        """Закрыть HTTP-клиент."""
        self._client.close()

    def __enter__(self) -> OllamaClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
