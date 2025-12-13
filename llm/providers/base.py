from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    def __init__(self, model_name: str, temperature: float = 0, **kwargs):
        self.model_name = model_name
        self.temperature = temperature
        self.config = kwargs
        
    @abstractmethod
    def invoke(self, prompt: str, **kwargs) -> str:
        """Invoke the LLM with a prompt and return the response content."""
        pass
    
    @abstractmethod
    def invoke_structured(self, prompt: str, response_format: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Invoke the LLM with structured output format (JSON)."""
        pass
    
    @abstractmethod
    def bind_tools(self, tools: list):
        """Bind tools to the LLM (returns a runnable)."""
        pass
