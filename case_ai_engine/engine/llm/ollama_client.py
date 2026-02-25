"""HTTP-клиент Ollama для локального инференса LLM."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Адрес Ollama по умолчанию
DEFAULT_BASE_URL = "http://localhost:11434"


class OllamaClient:
    """Тонкая обёртка над REST API Ollama."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(timeout=timeout)

    def generate(self, model: str, prompt: str, **kwargs: Any) -> str:
        """Отправить запрос на генерацию и вернуть текст ответа."""
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            **kwargs,
        }
        url = f"{self.base_url}/api/generate"
        logger.debug("POST %s model=%s prompt_len=%d", url, model, len(prompt))
        response = self._client.post(url, json=payload)
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        return str(data.get("response", ""))

    def close(self) -> None:
        """Закрыть HTTP-клиент."""
        self._client.close()

    def __enter__(self) -> OllamaClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
