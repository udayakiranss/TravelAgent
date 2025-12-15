from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Union, Type
from pydantic import BaseModel

class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    def __init__(self, model_name: str, temperature: float = 0, **kwargs):
        self.model_name = model_name
        self.temperature = temperature
        self.config = kwargs
        self.enable_prompt_caching = kwargs.get("enable_prompt_caching", False)
        
    @abstractmethod
    def invoke(self, prompt: Union[str, Dict[str, str]], **kwargs) -> str:
        """
        Invoke the LLM with a prompt and return the response content.
        
        Args:
            prompt: Either a string prompt or dict with 'system' and 'user' keys.
                    When dict provided, uses structured messages for optimal prompt caching.
            **kwargs: Additional arguments including:
                - cache_key: Optional cache key for prompt caching
                - use_case: Optional use case identifier for cache key generation
                - cache_key_prefix: Optional prefix for cache key generation
        """
        pass
    
    @abstractmethod
    def invoke_structured(
        self, 
        prompt: Union[str, Dict[str, str]], 
        response_format: Union[Dict[str, Any], Type[BaseModel]], 
        **kwargs
    ) -> Dict[str, Any]:
        """
        Invoke the LLM with structured output format (JSON).
        
        Supports both Pydantic models (via with_structured_output) and dict schemas
        (backward compatible JSON mode).
        
        Args:
            prompt: Either a string prompt or dict with 'system' and 'user' keys.
                    When dict provided, uses structured messages for optimal prompt caching.
            response_format: Either a JSON schema dict or a Pydantic BaseModel class.
                            Pydantic models use with_structured_output() for type-safe validation.
                            Dict schemas use JSON mode for backward compatibility.
            **kwargs: Additional arguments including:
                - cache_key: Optional cache key for prompt caching
                - use_case: Optional use case identifier for cache key generation
                - cache_key_prefix: Optional prefix for cache key generation
        """
        pass
    
    @abstractmethod
    def bind_tools(self, tools: list):
        """Bind tools to the LLM (returns a runnable)."""
        pass
    
    def extract_cache_usage(self, response: Any) -> Optional[Dict[str, int]]:
        """
        Extract cache usage information from LLM response.
        
        This is a helper method that can be overridden by provider implementations
        to extract provider-specific cache usage metadata.
        
        Args:
            response: The LLM response object
            
        Returns:
            Dict with cache usage info, or None if not available.
            Format: {
                'cache_read_tokens': int,  # Tokens read from cache
                'cache_write_tokens': int,  # Tokens written to cache (if available)
            }
        """
        # Default implementation - providers should override
        return None
