from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Union, Type
from pydantic import BaseModel
import logging
import json

logger = logging.getLogger(__name__)

class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    def __init__(self, model_name: str, temperature: float = 0, **kwargs):
        self.model_name = model_name
        self.temperature = temperature
        self.config = kwargs
        self.config = kwargs
        
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
    


    def _parse_json(self, text: str) -> Dict[str, Any]:
        """Safe JSON parsing with markdown stripping."""
        try:
            clean_text = text.strip()
            if "```json" in clean_text:
                clean_text = clean_text.split("```json")[1].split("```")[0]
            elif "```" in clean_text:
                clean_text = clean_text.split("```")[1].split("```")[0]
            
            return json.loads(clean_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            raise
