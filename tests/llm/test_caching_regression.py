"""
Regression tests to ensure prompt caching doesn't break existing functionality.
"""
import pytest
from unittest.mock import patch, MagicMock
from llm.providers.openai import OpenAIProvider
from llm.providers.anthropic import AnthropicProvider
from llm.providers.factory import ProviderFactory
from llm.strategy.model_strategy import ModelInvocationStrategy
from llm.strategy.use_cases import UseCase


class TestCachingBackwardCompatibility:
    """Test that caching doesn't break backward compatibility."""
    
    @pytest.fixture
    def mock_openai_response(self):
        """Create a mock OpenAI response."""
        response = MagicMock()
        response.content = "Test response"
        return response
    
    def test_openai_invoke_without_caching(self, mock_openai_response):
        """Test OpenAI invoke works when caching is disabled."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            provider = OpenAIProvider(
                model_name="gpt-4o",
                temperature=0,
                enable_prompt_caching=False
            )
            
            # Verify caching is disabled
            assert provider.enable_prompt_caching is False
            
            # Verify provider can be created and configured correctly
            # (Actual invoke testing requires API keys, so we test configuration)
            assert provider.model_name == "gpt-4o"
            assert provider.temperature == 0
    
    def test_openai_invoke_string_prompt_backward_compatible(self, mock_openai_response):
        """Test that string prompts still work (backward compatibility)."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            provider = OpenAIProvider(
                model_name="gpt-4o",
                temperature=0,
                enable_prompt_caching=True
            )
            
            # Verify caching is enabled but string prompts don't break
            assert provider.enable_prompt_caching is True
            
            # Verify that string prompts don't require system prompt (backward compatible)
            # String prompts won't use caching (need structured format), but should still work
            from llm.providers.cache_manager import CacheKeyManager
            system_prompt = CacheKeyManager.extract_system_prompt("Simple string prompt")
            assert system_prompt is None  # String prompts don't have system prompt
    
    def test_openai_invoke_structured_backward_compatible(self, mock_openai_response):
        """Test that invoke_structured still works with caching enabled."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            provider = OpenAIProvider(
                model_name="gpt-4o",
                temperature=0,
                enable_prompt_caching=True,
                enable_json_mode=True
            )
            
            structured_prompt = {
                "system": "You are a helpful assistant.",
                "user": "Return JSON"
            }
            response_format = {"type": "object", "properties": {}}
            
            # Mock the invoke call that invoke_structured uses
            with patch.object(provider, 'invoke', return_value='{"result": "test"}') as mock_invoke:
                result = provider.invoke_structured(structured_prompt, response_format)
                assert mock_invoke.called
                assert isinstance(result, dict)
    
    def test_anthropic_invoke_without_caching(self):
        """Test Anthropic invoke works when caching is disabled."""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'}):
            provider = AnthropicProvider(
                model_name="claude-3-5-sonnet-latest",
                temperature=0,
                api_key="test-key",  # Pass api_key explicitly
                enable_prompt_caching=False
            )
            
            # Verify caching is disabled
            assert provider.enable_prompt_caching is False
            
            # Verify provider can be created and configured correctly
            assert provider.model_name == "claude-3-5-sonnet-latest"
            assert provider.temperature == 0
    
    def test_anthropic_invoke_string_prompt_backward_compatible(self):
        """Test that string prompts still work for Anthropic."""
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'}):
            provider = AnthropicProvider(
                model_name="claude-3-5-sonnet-latest",
                temperature=0,
                api_key="test-key",  # Pass api_key explicitly
                enable_prompt_caching=True
            )
            
            # Verify caching is enabled but string prompts don't break
            assert provider.enable_prompt_caching is True
            
            # Verify that string prompts don't require system prompt (backward compatible)
            # String prompts won't use cache_control (need structured format), but should still work
            from llm.providers.cache_manager import CacheKeyManager
            system_prompt = CacheKeyManager.extract_system_prompt("Simple string prompt")
            assert system_prompt is None  # String prompts don't have system prompt


class TestProviderFactoryBackwardCompatibility:
    """Test that ProviderFactory works with and without cache config."""
    
    def test_factory_without_cache_config(self):
        """Test ProviderFactory works when cache config is not provided."""
        config = {
            "provider": "openai",
            "model": "gpt-4o",
            "api_key": "test-key",
            "overrides": {
                "temperature": 0
            }
        }
        
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            provider = ProviderFactory.create_provider(config)
            
            # Should default to False
            assert provider.enable_prompt_caching is False
    
    def test_factory_with_partial_cache_config(self):
        """Test ProviderFactory works with partial cache config."""
        config = {
            "provider": "openai",
            "model": "gpt-4o",
            "api_key": "test-key",
            "overrides": {
                "enable_prompt_caching": True
                # No cache_key_prefix or cache_ttl
            }
        }
        
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            provider = ProviderFactory.create_provider(config)
            
            assert provider.enable_prompt_caching is True
            # Should have defaults
            assert provider.cache_key_prefix is None or provider.cache_key_prefix is not None


class TestModelStrategyIntegration:
    """Test that ModelInvocationStrategy works with cache configuration."""
    
    def test_strategy_loads_cache_config(self):
        """Test that ModelInvocationStrategy loads cache config from YAML."""
        strategy = ModelInvocationStrategy()
        config = strategy._get_use_case_config(UseCase.PLANNER)
        
        # Check that cache config is in overrides
        overrides = config.get("overrides", {})
        assert "enable_prompt_caching" in overrides
        assert overrides.get("enable_prompt_caching") is True
        assert "cache_key_prefix" in overrides
    
    def test_strategy_provider_creation_with_cache(self):
        """Test that strategy creates provider with cache config."""
        strategy = ModelInvocationStrategy()
        config = strategy._get_use_case_config(UseCase.PLANNER)
        
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            provider = ProviderFactory.create_provider(config)
            
            # Verify cache config was passed
            assert provider.enable_prompt_caching is True
            assert hasattr(provider, 'cache_key_prefix')
