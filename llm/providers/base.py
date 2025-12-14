from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Union, Type
from pydantic import BaseModel

class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    def __init__(self, model_name: str, temperature: float = 0, **kwargs):
        self.model_name = model_name
        self.temperature = temperature
        self.config = kwargs
        
    @abstractmethod
    def invoke(self, prompt: Union[str, Dict[str, str]], **kwargs) -> str:
        """
        Invoke the LLM with a prompt and return the response content.
        
        Args:
            prompt: Either a string prompt or dict with 'system' and 'user' keys.
                    When dict provided, uses structured messages for optimal prompt caching.
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
        """
        pass
    
    @abstractmethod
    def bind_tools(self, tools: list):
        """Bind tools to the LLM (returns a runnable)."""
        pass
