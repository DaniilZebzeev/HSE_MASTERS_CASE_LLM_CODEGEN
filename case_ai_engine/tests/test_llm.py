"""Тесты OllamaClient (без реального Ollama — всё мокировано)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from engine.llm.ollama_client import DEFAULT_NUM_PREDICT, OllamaClient


def _make_response(text: str) -> MagicMock:
    """Сформировать мок httpx.Response с полем response."""
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.json.return_value = {"response": text}
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


class TestOllamaClient:
    """Unit-тесты OllamaClient."""

    @pytest.fixture(autouse=True)
    def setup_client(self) -> None:
        """Инициализировать OllamaClient для каждого теста."""
        self.client = OllamaClient(model="test-model")

    # --- generate успешный случай ---

    def test_generate_возвращает_строку(self) -> None:
        """generate() возвращает текст из поля response."""
        with patch.object(
            self.client._client, "post", return_value=_make_response("hello")
        ):
            result = self.client.generate("test prompt")
        assert result == "hello"

    def test_generate_передаёт_правильный_url(self) -> None:
        """generate() обращается к /api/generate."""
        mock_post = MagicMock(return_value=_make_response("ok"))
        with patch.object(self.client._client, "post", mock_post):
            self.client.generate("test")
        args, _ = mock_post.call_args
        assert args[0] == "http://localhost:11434/api/generate"

    def test_generate_payload_содержит_model(self) -> None:
        """Payload содержит имя модели."""
        mock_post = MagicMock(return_value=_make_response("ok"))
        with patch.object(self.client._client, "post", mock_post):
            self.client.generate("test")
        _, kwargs = mock_post.call_args
        assert kwargs["json"]["model"] == "test-model"

    def test_generate_stream_false(self) -> None:
        """Payload содержит stream=False (не стриминг)."""
        mock_post = MagicMock(return_value=_make_response("ok"))
        with patch.object(self.client._client, "post", mock_post):
            self.client.generate("test")
        _, kwargs = mock_post.call_args
        assert kwargs["json"]["stream"] is False

    def test_generate_temperature_0_по_умолчанию(self) -> None:
        """По умолчанию temperature=0 для детерминированного вывода."""
        mock_post = MagicMock(return_value=_make_response("ok"))
        with patch.object(self.client._client, "post", mock_post):
            self.client.generate("test")
        _, kwargs = mock_post.call_args
        assert kwargs["json"]["options"]["temperature"] == 0.0

    def test_generate_num_predict_по_умолчанию(self) -> None:
        """По умолчанию num_predict равен DEFAULT_NUM_PREDICT."""
        mock_post = MagicMock(return_value=_make_response("ok"))
        with patch.object(self.client._client, "post", mock_post):
            self.client.generate("test")
        _, kwargs = mock_post.call_args
        assert kwargs["json"]["options"]["num_predict"] == DEFAULT_NUM_PREDICT

    def test_generate_пустой_response_возвращает_пустую_строку(self) -> None:
        """Если ответ не содержит 'response', вернуть пустую строку."""
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.json.return_value = {}
        mock_resp.raise_for_status = MagicMock()
        with patch.object(self.client._client, "post", return_value=mock_resp):
            result = self.client.generate("test")
        assert result == ""

    # --- обработка ошибок ---

    def test_connect_error_даёт_понятное_сообщение(self) -> None:
        """ConnectError преобразуется в ConnectionError с подсказкой."""
        with patch.object(
            self.client._client,
            "post",
            side_effect=httpx.ConnectError("refused"),
        ):
            with pytest.raises(ConnectionError, match="ollama serve"):
                self.client.generate("test")

    def test_timeout_error_преобразуется(self) -> None:
        """TimeoutException преобразуется в TimeoutError."""
        with patch.object(
            self.client._client,
            "post",
            side_effect=httpx.TimeoutException("timed out"),
        ):
            with pytest.raises(TimeoutError):
                self.client.generate("test")

    def test_http_error_преобразуется_в_runtime_error(self) -> None:
        """HTTP 5xx преобразуется в RuntimeError со статусом."""
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        http_error = httpx.HTTPStatusError(
            "500 Internal Server Error",
            request=MagicMock(),
            response=mock_resp,
        )
        mock_resp.raise_for_status.side_effect = http_error
        with patch.object(self.client._client, "post", return_value=mock_resp):
            with pytest.raises(RuntimeError, match="500"):
                self.client.generate("test")

    # --- context manager ---

    def test_context_manager_работает(self) -> None:
        """OllamaClient работает как контекстный менеджер."""
        with OllamaClient(model="test-model") as client:
            assert client.model == "test-model"
