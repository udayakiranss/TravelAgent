import os
import pytest
from unittest.mock import patch, MagicMock
from llm import ModelInvocationStrategy, UseCase
from llm.providers.base import LLMProvider
from llm.strategy.config_loader import ConfigLoader

# Mock environment variables
@pytest.fixture
def mock_env():
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "test-key", 
        "ANTHROPIC_API_KEY": "test-anthropic",
        "GOOGLE_API_KEY": "test-google"
    }):
        yield

def test_config_loader(mock_env):
    # This might fail if files don't exist, but we created them.
    # We should mock load to avoid dependency on filesystem if possible, 
    # but integration test is better here as we want to verify YAMLs.
    
    config = ConfigLoader.load_model_strategy()
    assert "use_cases" in config
    assert "planner" in config["use_cases"]
    
    # Check env var resolution
    # Depends on if we loaded it fresh. ConfigLoader caches.
    # We might need to clear cache for test.
    ConfigLoader._config_cache = None
    config = ConfigLoader.load_model_strategy()
    
    # Check if api_key was populated (indirectly check provider settings)
    providers = config["providers"]
    assert providers["openai"]["provider_specific_settings"]["api_key"] == "test-key"

def test_strategy_get_llm(mock_env):
    start = ModelInvocationStrategy()
    # Force reload config
    ConfigLoader._config_cache = None
    
    llm = start.get_llm_for_use_case(UseCase.PLANNER)
    assert isinstance(llm, LLMProvider)
    # Check if it's OpenAI (default for planner)
    assert llm.model_name == "gpt-4o"
    
def test_strategy_get_prompt():
    start = ModelInvocationStrategy()
    prompt = start.get_prompt_for_use_case(UseCase.PLANNER, query="test", preference_summary="none")
    assert "Planner:" in prompt
    assert "Query: test" in prompt

def test_fallback_provider(mock_env):
    # This requires mocking config to force a provider that doesn't exist or similar?
    # Or just verifying we can get the fallback LLM explicitly if we added logic for it.
    # Current implementation doesn't auto-fallback on error yet (it was designed but Logic in ModelStrategy just picks primary).
    pass
