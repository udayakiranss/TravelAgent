# llm_provider.py
# Legacy bridge to new llm module
from typing import Optional, Dict, Any, List
import logging
from llm.providers.base import LLMProvider
from llm.providers.factory import ProviderFactory

logger = logging.getLogger(__name__)

# Re-export LLMProvider for compatibility
__all__ = ["LLMProvider", "create_llm_provider", "extract_token_usage", "LangChainLLMProvider"]

def extract_token_usage(response) -> Optional[Dict[str, int]]:
    """Extract token usage from an LLM response if available."""
    try:
        # LangChain stores usage in response_metadata for most providers
        if hasattr(response, 'response_metadata'):
            metadata = response.response_metadata
            
            # OpenAI format
            if 'token_usage' in metadata:
                usage = metadata['token_usage']
                return {
                    'input': usage.get('prompt_tokens', 0),
                    'output': usage.get('completion_tokens', 0),
                    'total': usage.get('total_tokens', 0),
                }
            
            # Alternative format (some providers)
            if 'usage' in metadata:
                usage = metadata['usage']
                return {
                    'input': usage.get('input_tokens', usage.get('prompt_tokens', 0)),
                    'output': usage.get('output_tokens', usage.get('completion_tokens', 0)),
                    'total': usage.get('total_tokens', 0),
                }
        
        # Anthropic/other providers may use usage_metadata
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            usage = response.usage_metadata
            return {
                'input': getattr(usage, 'input_tokens', 0),
                'output': getattr(usage, 'output_tokens', 0),
                'total': getattr(usage, 'total_tokens', 0),
            }
        
        return None
    except Exception:
        return None

# Dummy class for compatibility if explicitly imported
class LangChainLLMProvider(LLMProvider):
    pass

def create_llm_provider(model_name: str = "gpt-4o", 
                       model_provider: str = "openai",
                       temperature: float = 0,
                       **kwargs) -> LLMProvider:
    """
    Factory function to create an LLM provider (Delegates to new ProviderFactory)
    """
    config = {
        "provider": model_provider,
        "model": model_name,
        "overrides": {
            "temperature": temperature,
            **kwargs
        }
    }
    # Note: We rely on env vars being picked up by the provider internals 
    # if api_key is not explicitly passed in config.
    
    return ProviderFactory.create_provider(config)
