"""Unit tests for Gemini API client."""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
import time
from babel.transform.gemini_client import GeminiClient, RateLimitError


class TestGeminiClientConfiguration:
    """Tests for API client configuration."""
    
    def test_missing_api_key_raises_value_error(self):
        """Test that missing API key raises ValueError."""
        # Clear environment variable
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                GeminiClient()
            
            assert "GEMINI_API_KEY" in str(exc_info.value)
            assert "not set" in str(exc_info.value)
    
    def test_api_key_from_environment(self):
        """Test that API key is loaded from environment variable."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key-123"}):
            with patch("babel.transform.gemini_client.genai") as mock_genai:
                mock_client = Mock()
                mock_genai.Client.return_value = mock_client
                
                client = GeminiClient()
                
                assert client.api_key == "test-key-123"
                mock_genai.Client.assert_called_once_with(api_key="test-key-123")
    
    def test_api_key_from_parameter(self):
        """Test that API key can be passed as parameter."""
        with patch("babel.transform.gemini_client.genai") as mock_genai:
            mock_client = Mock()
            mock_genai.Client.return_value = mock_client
            
            client = GeminiClient(api_key="param-key-456")
            
            assert client.api_key == "param-key-456"
            mock_genai.Client.assert_called_once_with(api_key="param-key-456")
    
    def test_model_initialized_with_gemini_2_5_flash(self):
        """Test that model name is set to 'gemini-2.5-flash'."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            with patch("babel.transform.gemini_client.genai") as mock_genai:
                mock_client = Mock()
                mock_genai.Client.return_value = mock_client
                
                client = GeminiClient()
                
                assert client.model_name == "gemini-2.5-flash"
    
    def test_native_json_mode_configured(self):
        """Test that native JSON mode is configured in generate_content."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            with patch("babel.transform.gemini_client.genai") as mock_genai:
                with patch("babel.transform.gemini_client.types") as mock_types:
                    # Setup mock client
                    mock_client = Mock()
                    mock_response = Mock()
                    mock_response.text = '{"test": "response"}'
                    mock_client.models.generate_content.return_value = mock_response
                    mock_genai.Client.return_value = mock_client
                    
                    # Setup GenerateContentConfig mock
                    mock_config = Mock()
                    mock_types.GenerateContentConfig.return_value = mock_config
                    
                    client = GeminiClient()
                    result = client.generate_content("test prompt")
                    
                    # Verify GenerateContentConfig was created with JSON mime type
                    mock_types.GenerateContentConfig.assert_called_once_with(
                        response_mime_type="application/json"
                    )
                    
                    # Verify generate_content was called with model, contents, and config
                    mock_client.models.generate_content.assert_called_once_with(
                        model="gemini-2.5-flash",
                        contents="test prompt",
                        config=mock_config
                    )
                    
                    assert result == '{"test": "response"}'


class TestGeminiClientRateLimitRetry:
    """Tests for rate limit retry logic."""
    
    def test_rate_limit_error_429_triggers_retry(self):
        """Test that 429 errors trigger retry with exponential backoff."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            with patch("babel.transform.gemini_client.genai") as mock_genai:
                with patch("babel.transform.gemini_client.types"):
                    mock_client = Mock()
                    mock_genai.Client.return_value = mock_client
                    
                    # Simulate 429 error then success
                    call_count = 0
                    def side_effect(*args, **kwargs):
                        nonlocal call_count
                        call_count += 1
                        if call_count < 3:
                            raise Exception("429 rate limit exceeded")
                        mock_response = Mock()
                        mock_response.text = '{"success": true}'
                        return mock_response
                    
                    mock_client.models.generate_content.side_effect = side_effect
                    
                    client = GeminiClient()
                    start_time = time.time()
                    result = client.generate_content("test prompt")
                    elapsed = time.time() - start_time
                    
                    # Should have retried and eventually succeeded
                    assert call_count == 3
                    assert result == '{"success": true}'
                    # Should have waited (1s + 2s = 3s minimum)
                    assert elapsed >= 3.0
    
    def test_rate_limit_keyword_triggers_retry(self):
        """Test that 'rate limit' keyword triggers retry."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            with patch("babel.transform.gemini_client.genai") as mock_genai:
                with patch("babel.transform.gemini_client.types"):
                    mock_client = Mock()
                    mock_genai.Client.return_value = mock_client
                    
                    # Simulate rate limit error then success
                    call_count = 0
                    def side_effect(*args, **kwargs):
                        nonlocal call_count
                        call_count += 1
                        if call_count < 2:
                            raise Exception("API rate limit exceeded")
                        mock_response = Mock()
                        mock_response.text = '{"success": true}'
                        return mock_response
                    
                    mock_client.models.generate_content.side_effect = side_effect
                    
                    client = GeminiClient()
                    result = client.generate_content("test prompt")
                    
                    assert call_count == 2
                    assert result == '{"success": true}'
    
    def test_quota_keyword_triggers_retry(self):
        """Test that 'quota' keyword triggers retry."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            with patch("babel.transform.gemini_client.genai") as mock_genai:
                with patch("babel.transform.gemini_client.types"):
                    mock_client = Mock()
                    mock_genai.Client.return_value = mock_client
                    
                    # Simulate quota error then success
                    call_count = 0
                    def side_effect(*args, **kwargs):
                        nonlocal call_count
                        call_count += 1
                        if call_count < 2:
                            raise Exception("Quota exceeded for requests")
                        mock_response = Mock()
                        mock_response.text = '{"success": true}'
                        return mock_response
                    
                    mock_client.models.generate_content.side_effect = side_effect
                    
                    client = GeminiClient()
                    result = client.generate_content("test prompt")
                    
                    assert call_count == 2
                    assert result == '{"success": true}'
    
    def test_max_5_retry_attempts(self):
        """Test that max 5 retry attempts are made."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            with patch("babel.transform.gemini_client.genai") as mock_genai:
                with patch("babel.transform.gemini_client.types"):
                    mock_client = Mock()
                    mock_genai.Client.return_value = mock_client
                    
                    # Always fail with rate limit
                    def side_effect(*args, **kwargs):
                        raise Exception("429 rate limit exceeded")
                    
                    mock_client.models.generate_content.side_effect = side_effect
                    
                    client = GeminiClient()
                    
                    with pytest.raises(RateLimitError) as exc_info:
                        client.generate_content("test prompt")
                    
                    # Should have tried 5 times (initial + 4 retries)
                    assert mock_client.models.generate_content.call_count == 5
                    assert "rate limit exceeded" in str(exc_info.value)
    
    def test_exponential_backoff_timing(self):
        """Test exponential backoff timing (1s, 2s, 4s, 8s, 10s max)."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            with patch("babel.transform.gemini_client.genai") as mock_genai:
                with patch("babel.transform.gemini_client.types"):
                    mock_client = Mock()
                    mock_genai.Client.return_value = mock_client
                    
                    call_times = []
                    
                    def side_effect(*args, **kwargs):
                        call_times.append(time.time())
                        raise Exception("429 rate limit exceeded")
                    
                    mock_client.models.generate_content.side_effect = side_effect
                    
                    client = GeminiClient()
                    
                    try:
                        client.generate_content("test prompt")
                    except RateLimitError:
                        pass
                    
                    # Calculate delays between attempts
                    delays = [call_times[i+1] - call_times[i] for i in range(len(call_times)-1)]
                    
                    # Verify exponential backoff pattern (with some tolerance)
                    # Expected: ~1s, ~2s, ~4s, ~8s (capped at 10s)
                    assert len(delays) == 4  # 5 attempts = 4 delays
                    assert 0.9 <= delays[0] <= 1.5  # ~1s
                    assert 1.8 <= delays[1] <= 2.5  # ~2s
                    assert 3.5 <= delays[2] <= 5.0  # ~4s
                    assert 7.0 <= delays[3] <= 11.0  # ~8s (or capped at 10s)
    
    def test_non_rate_limit_error_not_retried(self):
        """Test that non-rate-limit errors are not retried."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            with patch("babel.transform.gemini_client.genai") as mock_genai:
                with patch("babel.transform.gemini_client.types"):
                    mock_client = Mock()
                    mock_genai.Client.return_value = mock_client
                    
                    # Simulate non-rate-limit error
                    mock_client.models.generate_content.side_effect = Exception("Invalid API key")
                    
                    client = GeminiClient()
                    
                    with pytest.raises(Exception) as exc_info:
                        client.generate_content("test prompt")
                    
                    # Should only try once (no retries for non-rate-limit errors)
                    assert mock_client.models.generate_content.call_count == 1
                    assert "Invalid API key" in str(exc_info.value)
    
    def test_empty_response_raises_value_error(self):
        """Test that empty response raises ValueError."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            with patch("babel.transform.gemini_client.genai") as mock_genai:
                with patch("babel.transform.gemini_client.types"):
                    mock_client = Mock()
                    mock_genai.Client.return_value = mock_client
                    
                    # Simulate empty response
                    mock_response = Mock()
                    mock_response.text = ""
                    mock_client.models.generate_content.return_value = mock_response
                    
                    client = GeminiClient()
                    
                    with pytest.raises(ValueError) as exc_info:
                        client.generate_content("test prompt")
                    
                    assert "Empty response" in str(exc_info.value)
