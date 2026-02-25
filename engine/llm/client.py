"""Async client for the local Ollama HTTP API.

Ollama must be running locally (default: http://localhost:11434).
No cloud API keys are required.

Usage example::

    async with OllamaClient() as client:
        text = await client.generate("llama3", "Say hello.")
        print(text)
"""

from __future__ import annotations

import httpx

_DEFAULT_BASE_URL = "http://localhost:11434"
_DEFAULT_TIMEOUT = 120.0  # seconds — LLMs can be slow


class OllamaError(RuntimeError):
    """Raised when the Ollama API returns an unexpected response."""


class OllamaClient:
    """Thin async wrapper around the Ollama ``/api/generate`` endpoint.

    Parameters
    ----------
    base_url:
        Base URL of the Ollama server.  Defaults to ``http://localhost:11434``.
    timeout:
        HTTP request timeout in seconds.
    """

    def __init__(
        self,
        base_url: str = _DEFAULT_BASE_URL,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> OllamaClient:
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
        )
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate(
        self,
        model: str,
        prompt: str,
        system: str = "",
        temperature: float = 0.2,
    ) -> str:
        """Generate text from *prompt* using the local *model*.

        Parameters
        ----------
        model:
            Name of the Ollama model (e.g. ``"llama3"``, ``"codellama"``).
        prompt:
            User prompt string.
        system:
            Optional system prompt.
        temperature:
            Sampling temperature (lower → more deterministic).

        Returns
        -------
        str
            The generated text (stripped of leading/trailing whitespace).

        Raises
        ------
        OllamaError
            On non-200 responses or JSON decode errors.
        """
        if self._client is None:
            raise OllamaError("OllamaClient must be used as an async context manager.")

        payload: dict = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if system:
            payload["system"] = system

        try:
            response = await self._client.post("/api/generate", json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise OllamaError(
                f"Ollama returned HTTP {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            raise OllamaError(
                f"Could not reach Ollama at {self._base_url}: {exc}"
            ) from exc

        try:
            data = response.json()
        except Exception as exc:
            raise OllamaError(f"Invalid JSON from Ollama: {exc}") from exc

        if "response" not in data:
            raise OllamaError(f"Unexpected Ollama response shape: {data}")

        return data["response"].strip()

    async def list_models(self) -> list[str]:
        """Return a list of model names available in the local Ollama instance."""
        if self._client is None:
            raise OllamaError("OllamaClient must be used as an async context manager.")
        try:
            response = await self._client.get("/api/tags")
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise OllamaError(f"Failed to list Ollama models: {exc}") from exc
        return [m["name"] for m in data.get("models", [])]
