# llm_provider.py
# Flexible LLM integration supporting multiple foundation models
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod
import json
from utils.logger import get_logger, log_method_entry_exit

logger = get_logger()

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
    
    @log_method_entry_exit(level="DEBUG")
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
        logger.debug(f"Initializing LLM provider: {model_name} ({model_provider})")
        
        if not LANGCHAIN_AVAILABLE:
            logger.error("LangChain is not available")
            raise ImportError("LangChain is required. Install with: pip install langchain langchain-openai")
        
        self.model_name = model_name
        self.model_provider = model_provider
        self.temperature = temperature
        
        try:
            # Try to initialize using init_chat_model (LangChain 1.1.0+)
            logger.debug(f"Attempting to initialize using init_chat_model")
            self.llm = init_chat_model(
                model_name,
                model_provider=model_provider,
                temperature=temperature,
                **kwargs
            )
            logger.info(f"Successfully initialized LLM: {model_name} ({model_provider})")
        except Exception as e:
            logger.warning(f"init_chat_model failed: {e}, trying fallback")
            # Fallback to direct ChatOpenAI for OpenAI models
            if model_provider == "openai":
                try:
                    logger.debug("Attempting fallback to ChatOpenAI")
                    self.llm = ChatOpenAI(
                        model=model_name,
                        temperature=temperature,
                        **kwargs
                    )
                    logger.info(f"Successfully initialized LLM using fallback: {model_name}")
                except Exception as fallback_error:
                    logger.error(f"Fallback initialization also failed: {fallback_error}")
                    raise RuntimeError(f"Failed to initialize LLM: {e}")
            else:
                logger.error(f"Failed to initialize LLM for provider {model_provider}: {e}")
                raise RuntimeError(f"Failed to initialize LLM: {e}")
    
    @log_method_entry_exit(level="DEBUG")
    def invoke(self, prompt: str, **kwargs) -> str:
        """Invoke the LLM with a prompt"""
        logger.debug(f"Invoking LLM with prompt length: {len(prompt)} characters")
        logger.debug(f"LLM Request (prompt):\n{prompt}")
        if kwargs:
            logger.debug(f"LLM Request (kwargs): {kwargs}")
        try:
            response = self.llm.invoke(prompt, **kwargs)
            if hasattr(response, 'content'):
                result = response.content
                logger.debug(f"LLM invocation successful, response length: {len(result)} characters")
                logger.debug(f"LLM Response:\n{result}")
                return result
            result = str(response)
            logger.debug(f"LLM invocation successful, response length: {len(result)} characters")
            logger.debug(f"LLM Response:\n{result}")
            return result
        except Exception as e:
            logger.error(f"LLM invocation failed: {e}", exc_info=True)
            raise RuntimeError(f"LLM invocation failed: {e}")
    
    @log_method_entry_exit(level="DEBUG")
    def invoke_structured(self, prompt: str, response_format: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Invoke LLM with structured output format"""
        logger.debug(f"Invoking LLM with structured output format, schema keys: {list(response_format.keys())}")
        
        # Add format instructions to prompt
        format_instructions = f"\n\nRespond in JSON format matching this schema: {json.dumps(response_format, indent=2)}"
        full_prompt = prompt + format_instructions
        logger.debug(f"LLM Structured Request (full prompt with format instructions):\n{full_prompt}")
        if kwargs:
            logger.debug(f"LLM Structured Request (kwargs): {kwargs}")
        
        response_text = self.invoke(full_prompt, **kwargs)
        logger.debug(f"LLM Structured Response (raw):\n{response_text}")
        
        # Try to parse JSON from response
        try:
            # Extract JSON from response (handle markdown code blocks)
            if "```json" in response_text:
                logger.debug("Extracting JSON from markdown code block (```json)")
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                logger.debug("Extracting JSON from markdown code block (```)")
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            
            parsed_response = json.loads(response_text)
            # Handle both dict and list responses
            if isinstance(parsed_response, dict):
                logger.debug(f"Successfully parsed structured response with keys: {list(parsed_response.keys())}")
            elif isinstance(parsed_response, list):
                logger.debug(f"Successfully parsed structured response as list with {len(parsed_response)} items")
            else:
                logger.debug(f"Successfully parsed structured response: {type(parsed_response)}")
            return parsed_response
        except json.JSONDecodeError as e:
            # If JSON parsing fails, return raw response
            logger.warning(f"Failed to parse JSON from response: {e}, returning raw response")
            return {"raw_response": response_text}


@log_method_entry_exit(level="DEBUG")
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
    logger.debug(f"Creating LLM provider: {model_name} ({model_provider})")
    provider = LangChainLLMProvider(
        model_name=model_name,
        model_provider=model_provider,
        temperature=temperature,
        **kwargs
    )
    logger.info(f"LLM provider created successfully: {model_name} ({model_provider})")
    return provider

