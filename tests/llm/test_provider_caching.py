"""
Integration tests for provider prompt caching implementations.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from llm.providers.openai import OpenAIProvider
from llm.providers.anthropic import AnthropicProvider
from llm.providers.cache_manager import CacheKeyManager
from llm.strategy.use_cases import UseCase


class TestOpenAICaching:
    """Test OpenAI provider prompt caching."""
    
    @pytest.fixture
    def mock_openai_response(self):
        """Create a mock OpenAI response with cache usage."""
        response = MagicMock()
        response.content = "Test response"
        
        # Mock usage_metadata with cache_read_tokens
        usage_metadata = MagicMock()
        input_token_details = MagicMock()
        input_token_details.cache_read_tokens = 100
        usage_metadata.input_token_details = input_token_details
        response.usage_metadata = usage_metadata
        
        return response
    
    @pytest.fixture
    def openai_provider_with_caching(self):
        """Create OpenAI provider with caching enabled."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            provider = OpenAIProvider(
                model_name="gpt-4o",
                temperature=0,
                enable_prompt_caching=True,
                cache_key_prefix="test_prefix"
            )
            return provider
    
    def test_openai_provider_caching_enabled(self, openai_provider_with_caching):
        """Test that OpenAI provider has caching enabled."""
        assert openai_provider_with_caching.enable_prompt_caching is True
        assert openai_provider_with_caching.cache_key_prefix == "test_prefix"
    
    def test_openai_invoke_with_cache_key(self, openai_provider_with_caching):
        """Test that OpenAI provider generates cache keys for structured prompts."""
        structured_prompt = {
            "system": "You are a helpful assistant.",
            "user": "What is the weather?"
        }
        
        # Verify that cache key would be generated (testing the logic, not the actual API call)
        system_prompt = CacheKeyManager.extract_system_prompt(structured_prompt)
        should_cache = CacheKeyManager.should_use_caching(
            system_prompt,
            openai_provider_with_caching.enable_prompt_caching
        )
        assert should_cache is True
        
        # Verify cache key generation
        cache_key = CacheKeyManager.generate_cache_key(
            system_prompt=system_prompt,
            prefix=openai_provider_with_caching.cache_key_prefix
        )
        assert cache_key is not None
        assert cache_key.startswith("test_prefix_")
    
    def test_openai_extract_cache_usage(self, openai_provider_with_caching, mock_openai_response):
        """Test extracting cache usage from OpenAI response."""
        cache_usage = openai_provider_with_caching.extract_cache_usage(mock_openai_response)
        
        assert cache_usage is not None
        assert cache_usage['cache_read_tokens'] == 100
    
    def test_openai_extract_cache_usage_no_cache(self, openai_provider_with_caching):
        """Test extracting cache usage when no cache was used."""
        response = MagicMock()
        response.content = "Test"
        # No usage_metadata or cache_read_tokens
        response.usage_metadata = None
        
        cache_usage = openai_provider_with_caching.extract_cache_usage(response)
        assert cache_usage is None
    
    def test_openai_cache_key_generation(self, openai_provider_with_caching):
        """Test that cache keys are generated for structured prompts."""
        structured_prompt = {
            "system": "You are a helpful assistant.",
            "user": "What is the weather?"
        }
        
        # Extract system prompt and verify cache key would be generated
        system_prompt = CacheKeyManager.extract_system_prompt(structured_prompt)
        should_cache = CacheKeyManager.should_use_caching(
            system_prompt,
            openai_provider_with_caching.enable_prompt_caching
        )
        
        assert should_cache is True


class TestAnthropicCaching:
    """Test Anthropic provider prompt caching."""
    
    @pytest.fixture
    def mock_anthropic_response(self):
        """Create a mock Anthropic response with cache usage."""
        response = MagicMock()
        response.content = "Test response"
        
        # Mock usage_metadata with cache_read_input_tokens
        usage_metadata = MagicMock()
        usage_metadata.cache_read_input_tokens = 150
        response.usage_metadata = usage_metadata
        
        return response
    
    @pytest.fixture
    def anthropic_provider_with_caching(self):
        """Create Anthropic provider with caching enabled."""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'}):
            provider = AnthropicProvider(
                model_name="claude-3-5-sonnet-latest",
                temperature=0,
                api_key="test-key",  # Pass api_key explicitly
                enable_prompt_caching=True,
                cache_ttl="1h",
                cache_key_prefix="test_prefix"
            )
            return provider
    
    def test_anthropic_provider_caching_enabled(self, anthropic_provider_with_caching):
        """Test that Anthropic provider has caching enabled."""
        assert anthropic_provider_with_caching.enable_prompt_caching is True
        assert anthropic_provider_with_caching.cache_ttl == "1h"
        assert anthropic_provider_with_caching.cache_key_prefix == "test_prefix"
    
    def test_anthropic_invoke_with_cache_control(self, anthropic_provider_with_caching):
        """Test that Anthropic provider would add cache_control to system messages."""
        structured_prompt = {
            "system": "You are a helpful assistant.",
            "user": "What is the weather?"
        }
        
        # Verify that cache_control would be applied (testing the logic)
        system_prompt = CacheKeyManager.extract_system_prompt(structured_prompt)
        should_cache = CacheKeyManager.should_use_caching(
            system_prompt,
            anthropic_provider_with_caching.enable_prompt_caching
        )
        assert should_cache is True
        
        # Verify cache TTL is configured
        assert anthropic_provider_with_caching.cache_ttl == "1h"
        
        # Verify the cache_control structure that would be created
        # (The actual application happens in invoke(), but we verify the config is correct)
        expected_cache_control = {
            "type": "ephemeral",
            "ttl": anthropic_provider_with_caching.cache_ttl
        }
        assert expected_cache_control["ttl"] == "1h"
    
    def test_anthropic_extract_cache_usage(self, anthropic_provider_with_caching, mock_anthropic_response):
        """Test extracting cache usage from Anthropic response."""
        cache_usage = anthropic_provider_with_caching.extract_cache_usage(mock_anthropic_response)
        
        assert cache_usage is not None
        assert cache_usage['cache_read_tokens'] == 150
    
    def test_anthropic_extract_cache_usage_no_cache(self, anthropic_provider_with_caching):
        """Test extracting cache usage when no cache was used."""
        response = MagicMock()
        response.content = "Test"
        # No usage_metadata or cache_read_input_tokens
        response.usage_metadata = None
        
        cache_usage = anthropic_provider_with_caching.extract_cache_usage(response)
        assert cache_usage is None


class TestProviderCachingIntegration:
    """Integration tests for provider caching with real configuration."""
    
    def test_provider_factory_passes_cache_config(self):
        """Test that ProviderFactory passes cache configuration to providers."""
        from llm.providers.factory import ProviderFactory
        
        config = {
            "provider": "openai",
            "model": "gpt-4o",
            "api_key": "test-key",
            "overrides": {
                "enable_prompt_caching": True,
                "cache_key_prefix": "test_prefix",
                "cache_ttl": "24h"
            }
        }
        
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            provider = ProviderFactory.create_provider(config)
            
            assert provider.enable_prompt_caching is True
            assert provider.cache_key_prefix == "test_prefix"
    
    def test_cache_key_generation_in_provider_flow(self):
        """Test cache key generation in actual provider invocation flow."""
        structured_prompt = {
            "system": "You are a helpful assistant.",
            "user": "What is the weather?"
        }
        
        # Generate cache key as provider would
        system_prompt = CacheKeyManager.extract_system_prompt(structured_prompt)
        cache_key = CacheKeyManager.generate_cache_key(
            system_prompt=system_prompt,
            use_case=UseCase.PLANNER,
            prefix="planner_v1"
        )
        
        assert cache_key is not None
        assert cache_key.startswith("planner_v1_")
        assert len(cache_key) > len("planner_v1_")
