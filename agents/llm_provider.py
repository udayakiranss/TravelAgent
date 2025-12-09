# llm_provider.py
# Flexible LLM integration supporting multiple foundation models
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod
import json
import time
from utils.logger import get_logger, _format_duration

logger = get_logger()

# Max characters to log for LLM content (prompts/responses)
_LOG_CONTENT_MAX_CHARS = 100


def _truncate_for_log(text: str, max_chars: int = _LOG_CONTENT_MAX_CHARS) -> str:
    """Truncate text for logging, showing first N chars with indicator."""
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}... [truncated, total {len(text)} chars]"

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
            logger.error("LangChain is not available")
            raise ImportError("LangChain is required. Install with: pip install langchain langchain-openai")
        
        self.model_name = model_name
        self.model_provider = model_provider
        self.temperature = temperature
        
        try:
            self.llm = init_chat_model(
                model_name,
                model_provider=model_provider,
                temperature=temperature,
                **kwargs
            )
            logger.info(f"LLM initialized: {model_name} ({model_provider})")
        except Exception as e:
            logger.warning(f"init_chat_model failed: {e}, trying fallback")
            if model_provider == "openai":
                try:
                    self.llm = ChatOpenAI(
                        model=model_name,
                        temperature=temperature,
                        **kwargs
                    )
                    logger.info(f"LLM initialized via fallback: {model_name}")
                except Exception as fallback_error:
                    logger.error(f"LLM initialization failed: {fallback_error}")
                    raise RuntimeError(f"Failed to initialize LLM: {e}")
            else:
                logger.error(f"LLM initialization failed for {model_provider}: {e}")
                raise RuntimeError(f"Failed to initialize LLM: {e}")
    
    def invoke(self, prompt: str, **kwargs) -> str:
        """Invoke the LLM with a prompt"""
        logger.debug(f"LLM invoke: prompt={len(prompt)} chars, preview={_truncate_for_log(prompt)}")
        
        start_time = time.perf_counter()
        try:
            response = self.llm.invoke(prompt, **kwargs)
            result = response.content if hasattr(response, 'content') else str(response)
            
            # Calculate timing
            duration_ms = (time.perf_counter() - start_time) * 1000
            duration_str = _format_duration(duration_ms)
            
            # Extract token usage from response metadata (if available)
            token_info = self._extract_token_usage(response)
            
            # Log response with timing and tokens
            if token_info:
                logger.info(f"⏱ LLM call: {duration_str} | tokens: {token_info['input']} in, {token_info['output']} out, {token_info['total']} total")
            else:
                logger.info(f"⏱ LLM call: {duration_str} | {len(prompt)} chars -> {len(result)} chars")
            
            return result
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            duration_str = _format_duration(duration_ms)
            logger.error(f"⏱ LLM call failed after {duration_str}: {e}")
            raise RuntimeError(f"LLM invocation failed: {e}")
    
    def _extract_token_usage(self, response) -> Optional[Dict[str, int]]:
        """Extract token usage from LLM response metadata."""
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
    
    def invoke_structured(self, prompt: str, response_format: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Invoke LLM with structured output format"""
        # Add format instructions to prompt
        format_instructions = f"\n\nRespond in JSON format matching this schema: {json.dumps(response_format, indent=2)}"
        full_prompt = prompt + format_instructions
        
        logger.debug(f"LLM structured invoke: schema_keys={list(response_format.keys())}, prompt={len(full_prompt)} chars")
        
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
            
            parsed_response = json.loads(response_text)
            
            # Log parse result summary
            if isinstance(parsed_response, dict):
                logger.debug(f"LLM structured response parsed: dict with keys={list(parsed_response.keys())}")
            elif isinstance(parsed_response, list):
                logger.debug(f"LLM structured response parsed: list with {len(parsed_response)} items")
            
            return parsed_response
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON from LLM response: {e}")
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

