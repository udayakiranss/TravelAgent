from typing import Dict, Any, Optional
import logging
from .base import LLMProvider
from .openai import OpenAIProvider
from .anthropic import AnthropicProvider

logger = logging.getLogger(__name__)

class ProviderFactory:
    """Factory for creating LLM providers."""
    
    @staticmethod
    def create_provider(provider_config: Dict[str, Any], overrides: Optional[Dict[str, Any]] = None) -> LLMProvider:
        """
        Create a provider instance based on config.
        
        Args:
            provider_config: Resolved configuration for the use case (merged provider defaults + overrides).
            overrides: Optional runtime overrides (deprecated, prefer config merging before calling).
            
        Returns:
            LLMProvider instance
        """
        provider_name = provider_config.get("provider", "openai")
        model_name = provider_config.get("model")
        api_key = provider_config.get("api_key")
        
        # Merge overrides into config if provided
        config = dict(provider_config)
        if overrides:
            config.update(overrides)
            
        # Extract common params
        temperature = config.get("overrides", {}).get("temperature", 0)
        
        # Extract provider specific settings
        # In our flat resolved config, these might be at top level or under 'overrides'
        # depending on how resolver works. Assuming 'resolver' merges everything into flat dict 
        # effectively or we pass the specific section.
        # Let's assume the 'provider_config' passed here is the Use Case config which contains:
        # provider: ...
        # model: ...
        # overrides: { ... }
        # api_key: ... (injected by loader)
        
        # We need to flatten 'overrides' for the provider constructor
        kwargs = config.get("overrides", {}).copy()
        
        # Remove explicitly passed args from kwargs to avoid duplicates
        if "temperature" in kwargs:
            kwargs.pop("temperature")
        
        if provider_name == "openai":
            return OpenAIProvider(
                model_name=model_name,
                temperature=temperature,
                api_key=api_key,
                **kwargs
            )
        elif provider_name == "anthropic":
            return AnthropicProvider(
                model_name=model_name,
                temperature=temperature,
                api_key=api_key,
                **kwargs
            )
        else:
            raise ValueError(f"Unsupported provider: {provider_name}")
