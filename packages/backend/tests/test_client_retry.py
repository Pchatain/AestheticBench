"""Unit tests for client retry logic."""

import httpx
import pytest
from unittest.mock import MagicMock, patch

from aesthetic_bench.client import OpenRouterClient
from aesthetic_bench.config import Config


@pytest.fixture
def config():
    """Create a test config."""
    return Config(
        api_key="test-key",
        max_retries=5,
        initial_backoff=0.01,  # Fast for tests
        max_backoff=0.1,
    )


@pytest.fixture
def client(config):
    """Create a test client."""
    client = OpenRouterClient(config)
    yield client
    client.close()


class TestChatCompletionRetry:
    def test_successful_request(self, client):
        """chat_completion should return response on success."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello!"}}]
        }
        mock_response.raise_for_status = MagicMock()
        
        with patch.object(client._client, "post", return_value=mock_response):
            result = client.chat_completion("Hi", model="test-model")
        
        assert result == "Hello!"


class TestBatchRetryOnConnectionError:
    def test_retries_on_connection_error(self, client):
        """batch_chat_completions should retry on connection errors."""
        call_count = 0
        
        def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.ConnectError("Connection failed")
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "Success!"}}]
            }
            mock_response.raise_for_status = MagicMock()
            return mock_response
        
        with patch.object(client._client, "post", side_effect=mock_post):
            results = client.batch_chat_completions(
                ["test message"],
                model="test-model",
                max_workers=0,  # Sequential for predictable testing
            )
        
        assert len(results) == 1
        assert results[0][2] == "Success!"
        assert call_count == 3  # 2 failures + 1 success

    def test_fails_after_max_retries(self, client):
        """batch_chat_completions should fail after max retries on connection errors."""
        def mock_post(*args, **kwargs):
            raise httpx.ConnectError("Connection failed")
        
        with patch.object(client._client, "post", side_effect=mock_post):
            results = client.batch_chat_completions(
                ["test message"],
                model="test-model",
                max_workers=0,
            )
        
        assert len(results) == 1
        assert results[0][2] is None  # Failed

    def test_retries_on_timeout(self, client):
        """batch_chat_completions should retry on timeout."""
        call_count = 0
        
        def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.TimeoutException("Timeout")
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "After timeout"}}]
            }
            mock_response.raise_for_status = MagicMock()
            return mock_response
        
        with patch.object(client._client, "post", side_effect=mock_post):
            results = client.batch_chat_completions(
                ["test message"],
                model="test-model",
                max_workers=0,
            )
        
        assert len(results) == 1
        assert results[0][2] == "After timeout"

    def test_retries_on_rate_limit(self, client):
        """batch_chat_completions should retry on 429 rate limit."""
        call_count = 0
        
        def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                response = MagicMock()
                response.status_code = 429
                response.headers = {"Retry-After": "0.01"}
                raise httpx.HTTPStatusError(
                    "Rate limited",
                    request=MagicMock(),
                    response=response
                )
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "After rate limit"}}]
            }
            mock_response.raise_for_status = MagicMock()
            return mock_response
        
        with patch.object(client._client, "post", side_effect=mock_post):
            results = client.batch_chat_completions(
                ["test message"],
                model="test-model",
                max_workers=0,
            )
        
        assert len(results) == 1
        assert results[0][2] == "After rate limit"
