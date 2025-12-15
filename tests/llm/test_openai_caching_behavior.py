
import pytest
import os
from unittest.mock import MagicMock, patch
from llm.providers.openai import OpenAIProvider
from langchain_core.messages import AIMessage

class TestOpenAICachingBehavior:
    
    @pytest.fixture
    def openai_provider(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key"}):
            return OpenAIProvider(
                model_name="gpt-4o",
                temperature=0,
                enable_prompt_caching=True
            )

    def test_extract_cache_usage_from_usage_metadata(self, openai_provider):
        """Test extraction from usage_metadata (standard OpenAI format)."""
        # Mock response with usage_metadata
        mock_response = MagicMock(spec=AIMessage)
        mock_response.content = "Test response"
        mock_response.usage_metadata = MagicMock()
        mock_response.usage_metadata.input_token_details = MagicMock()
        mock_response.usage_metadata.input_token_details.cache_read_tokens = 150
        
        usage = openai_provider.extract_cache_usage(mock_response)
        
        assert usage is not None
        assert usage["cache_read_tokens"] == 150

    def test_extract_cache_usage_from_response_metadata(self, openai_provider):
        """Test extraction from response_metadata (LangChain sometimes maps it here)."""
        # Mock response with response_metadata
        mock_response = MagicMock(spec=AIMessage)
        mock_response.content = "Test response"
        # Ensure usage_metadata is missing/empty to force fallback
        del mock_response.usage_metadata 
        
        mock_response.response_metadata = {
            "token_usage": {
                "cache_read_tokens": 75
            }
        }
        
        usage = openai_provider.extract_cache_usage(mock_response)
        
        assert usage is not None
        assert usage["cache_read_tokens"] == 75

    def test_extract_cache_usage_no_cache(self, openai_provider):
        """Test extraction when no cache usage is present."""
        mock_response = MagicMock(spec=AIMessage)
        mock_response.content = "Test response"
        mock_response.usage_metadata = MagicMock()
        # No input_token_details or it's None
        mock_response.usage_metadata.input_token_details = None
        mock_response.response_metadata = {}
        
        usage = openai_provider.extract_cache_usage(mock_response)
        
        assert usage is None

    def test_invoke_structured_cleans_up_invalid_keys(self, openai_provider):
        """
        Verify that invoke_structured does NOT raise TypeError about 'prompt_cache_key'
        after our fix.
        """
        prompt = {
            "system": "System instructions",
            "user": "User query"
        }
        response_format = {"type": "object", "properties": {"foo": {"type": "string"}}}
        
        # Mock the internal llm.invoke to return valid JSON
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(content='{"foo": "bar"}')
        openai_provider.llm = mock_llm
        
        # This should NOT fail with TypeError (unexpected keyword argument 'prompt_cache_key')
        # passing a cache_key to verify it's safely ignored/handled
        result = openai_provider.invoke_structured(
            prompt,
            response_format,
            cache_key="test-key-should-be-ignored-by-llm" 
        )
        
        assert result == {"foo": "bar"}
        
        # Verify mock was called WITHOUT prompt_cache_key specific to OpenAI
        call_args = mock_llm.invoke.call_args
        assert "prompt_cache_key" not in call_args.kwargs

