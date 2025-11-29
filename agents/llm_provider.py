# llm_provider.py
# Flexible LLM integration supporting multiple foundation models
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod
import json

try:
    from langchain.chat_models import init_chat_model
    from langchain_openai import ChatOpenAI
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

class LLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    @abstractmethod
    def invoke(self, prompt: str, **kwargs) -> str:
        """Invoke the LLM with a prompt and return the response"""
        pass
    
    @abstractmethod
    def invoke_structured(self, prompt: str, response_format: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Invoke the LLM with structured output format"""
        pass


class LangChainLLMProvider(LLMProvider):
    """LangChain-based LLM provider supporting multiple models"""
    
    def __init__(self, model_name: str = "gpt-4o", model_provider: str = "openai", 
                 temperature: float = 0, **kwargs):
        """
        Initialize LLM provider
        
        Args:
            model_name: Model identifier (e.g., 'gpt-4o', 'gpt-3.5-turbo', 'claude-3-opus')
            model_provider: Provider name (e.g., 'openai', 'anthropic', 'google')
            temperature: Sampling temperature
            **kwargs: Additional model-specific parameters
        """
        if not LANGCHAIN_AVAILABLE:
            raise ImportError("LangChain is required. Install with: pip install langchain langchain-openai")
        
        self.model_name = model_name
        self.model_provider = model_provider
        self.temperature = temperature
        
        try:
            # Try to initialize using init_chat_model (LangChain 1.1.0+)
            self.llm = init_chat_model(
                model_name,
                model_provider=model_provider,
                temperature=temperature,
                **kwargs
            )
        except Exception as e:
            # Fallback to direct ChatOpenAI for OpenAI models
            if model_provider == "openai":
                try:
                    self.llm = ChatOpenAI(
                        model=model_name,
                        temperature=temperature,
                        **kwargs
                    )
                except Exception:
                    raise RuntimeError(f"Failed to initialize LLM: {e}")
            else:
                raise RuntimeError(f"Failed to initialize LLM: {e}")
    
    def invoke(self, prompt: str, **kwargs) -> str:
        """Invoke the LLM with a prompt"""
        try:
            response = self.llm.invoke(prompt, **kwargs)
            if hasattr(response, 'content'):
                return response.content
            return str(response)
        except Exception as e:
            raise RuntimeError(f"LLM invocation failed: {e}")
    
    def invoke_structured(self, prompt: str, response_format: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Invoke LLM with structured output format"""
        # Add format instructions to prompt
        format_instructions = f"\n\nRespond in JSON format matching this schema: {json.dumps(response_format, indent=2)}"
        full_prompt = prompt + format_instructions
        
        response_text = self.invoke(full_prompt, **kwargs)
        
        # Try to parse JSON from response
        try:
            # Extract JSON from response (handle markdown code blocks)
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            
            return json.loads(response_text)
        except json.JSONDecodeError:
            # If JSON parsing fails, return raw response
            return {"raw_response": response_text}


def create_llm_provider(model_name: str = "gpt-4o", 
                       model_provider: str = "openai",
                       temperature: float = 0,
                       **kwargs) -> LLMProvider:
    """
    Factory function to create an LLM provider
    
    Args:
        model_name: Model identifier
        model_provider: Provider name (openai, anthropic, google, etc.)
        temperature: Sampling temperature
        **kwargs: Additional parameters
    
    Returns:
        LLMProvider instance
    """
    return LangChainLLMProvider(
        model_name=model_name,
        model_provider=model_provider,
        temperature=temperature,
        **kwargs
    )

