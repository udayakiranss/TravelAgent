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
                 temperature: float = 0, enable_json_mode: bool = True, 
                 enable_prompt_caching: bool = True, **kwargs):
        """
        Initialize LLM provider
        
        Args:
            model_name: Model identifier (e.g., 'gpt-4o', 'gpt-3.5-turbo', 'claude-3-opus')
            model_provider: Provider name (e.g., 'openai', 'anthropic', 'google')
            temperature: Sampling temperature
            enable_json_mode: Enable OpenAI JSON mode for structured outputs (default: True)
            enable_prompt_caching: Enable OpenAI prompt caching (default: True)
            **kwargs: Additional model-specific parameters
        """
        if not LANGCHAIN_AVAILABLE:
            logger.error("LangChain is not available")
            raise ImportError("LangChain is required. Install with: pip install langchain langchain-openai")
        
        self.model_name = model_name
        self.model_provider = model_provider
        self.temperature = temperature
        self.enable_json_mode = enable_json_mode and model_provider == "openai"
        self.enable_prompt_caching = enable_prompt_caching and model_provider == "openai"
        
        # Store original kwargs BEFORE modifying them (for later use when creating temporary LLM instances)
        self._init_kwargs = dict(kwargs)
        
        # Prepare model_kwargs for OpenAI-specific optimizations
        model_kwargs = kwargs.pop('model_kwargs', {}) or {}
        
        if self.enable_json_mode:
            # Enable OpenAI JSON mode - eliminates JSON formatting instructions from prompt
            # Note: response_format goes in model_kwargs for ChatOpenAI
            model_kwargs['response_format'] = {"type": "json_object"}
            logger.debug("OpenAI JSON mode enabled")
        
        # Note: cache_control is not supported in model_kwargs for current LangChain version
        # We'll implement prompt caching in Phase 2 using message-based approach
        if self.enable_prompt_caching:
            logger.debug("OpenAI prompt caching enabled (will use message-based caching in Phase 2)")
        
        # For OpenAI provider, use ChatOpenAI directly to ensure model_kwargs work
        if model_provider == "openai":
            try:
                # Try with model_kwargs first (for JSON mode)
                if model_kwargs:
                    self.llm = ChatOpenAI(
                        model=model_name,
                        temperature=temperature,
                        model_kwargs=model_kwargs,
                        **kwargs
                    )
                    logger.info(f"LLM initialized: {model_name} ({model_provider}) with optimizations")
                else:
                    # No model_kwargs, use standard initialization
                    self.llm = ChatOpenAI(
                        model=model_name,
                        temperature=temperature,
                        **kwargs
                    )
                    logger.info(f"LLM initialized: {model_name} ({model_provider})")
            except Exception as e:
                logger.warning(f"ChatOpenAI initialization failed: {e}, trying init_chat_model")
                try:
                    # Fallback to init_chat_model (may not support all model_kwargs)
                    self.llm = init_chat_model(
                        model_name,
                        model_provider=model_provider,
                        temperature=temperature,
                        **kwargs
                    )
                    logger.info(f"LLM initialized via init_chat_model: {model_name} ({model_provider})")
                    # If init_chat_model doesn't support response_format, disable JSON mode
                    if self.enable_json_mode:
                        logger.warning("JSON mode may not be available with init_chat_model, disabling")
                        self.enable_json_mode = False
                except Exception as init_error:
                    logger.error(f"LLM initialization failed: {init_error}")
                    raise RuntimeError(f"Failed to initialize LLM: {e}")
        else:
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
    
    def invoke(self, prompt: str, disable_json_mode: bool = False, **kwargs) -> str:
        """
        Invoke the LLM with a prompt
        
        Args:
            prompt: The prompt to send
            disable_json_mode: If True, temporarily disable JSON mode for this call (for plain text responses)
            **kwargs: Additional invocation parameters
        """
        logger.debug(f"LLM invoke: prompt={len(prompt)} chars, preview={_truncate_for_log(prompt)}, disable_json_mode={disable_json_mode}")
        
        start_time = time.perf_counter()
        try:
            # If JSON mode is enabled but we want plain text, create a temporary LLM without JSON mode
            if disable_json_mode and self.enable_json_mode and self.model_provider == "openai":
                try:
                    # Create a temporary ChatOpenAI instance without JSON mode for plain text responses
                    from langchain_openai import ChatOpenAI
                    
                    # Get original model_kwargs if available, but remove response_format
                    model_kwargs_without_json = {}
                    if hasattr(self.llm, 'model_kwargs'):
                        try:
                            model_kwargs = getattr(self.llm, 'model_kwargs', None)
                            if model_kwargs is not None and isinstance(model_kwargs, dict):
                                model_kwargs_without_json = dict(model_kwargs)
                                # Remove response_format to disable JSON mode
                                model_kwargs_without_json.pop('response_format', None)
                        except (AttributeError, TypeError) as e:
                            logger.debug(f"Could not extract model_kwargs: {e}")
                    
                    # Create temporary LLM without JSON mode
                    # Use stored init_kwargs but override model_kwargs to remove JSON mode
                    temp_llm_kwargs = {
                        "model": self.model_name,
                        "temperature": self.temperature,
                    }
                    # Add any other initialization kwargs (like API keys, etc.)
                    # But exclude model_kwargs since we'll set it separately
                    for key, value in self._init_kwargs.items():
                        if key != 'model_kwargs':
                            temp_llm_kwargs[key] = value
                    
                    # Set model_kwargs without response_format
                    if model_kwargs_without_json:
                        temp_llm_kwargs["model_kwargs"] = model_kwargs_without_json
                    elif 'model_kwargs' in self._init_kwargs:
                        # If init_kwargs had model_kwargs, copy it and remove response_format
                        init_model_kwargs = self._init_kwargs.get('model_kwargs')
                        if isinstance(init_model_kwargs, dict):
                            temp_model_kwargs = dict(init_model_kwargs)
                            temp_model_kwargs.pop('response_format', None)
                            if temp_model_kwargs:  # Only add if not empty
                                temp_llm_kwargs["model_kwargs"] = temp_model_kwargs
                    
                    temp_llm = ChatOpenAI(**temp_llm_kwargs)
                    logger.debug("Created temporary LLM instance without JSON mode for plain text response")
                    response = temp_llm.invoke(prompt, **kwargs)
                except Exception as e:
                    logger.warning(f"Failed to create temporary LLM without JSON mode: {e}. Using original LLM.", exc_info=True)
                    response = self.llm.invoke(prompt, **kwargs)
            else:
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
        return extract_token_usage(response)
    
    def invoke_structured(
        self, 
        prompt: str, 
        response_format: Dict[str, Any], 
        prompt_cache_key: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Invoke LLM with structured output format.
        
        Phase 1 Optimization: Uses OpenAI JSON mode when available, eliminating
        JSON formatting instructions from the prompt.
        
        Args:
            prompt: The prompt to send to the LLM
            response_format: JSON schema for structured output (used for validation)
            prompt_cache_key: Optional cache key for prompt caching (OpenAI only)
            **kwargs: Additional invocation parameters
        """
        # Phase 1: If JSON mode is enabled, we don't need to append schema to prompt
        if self.enable_json_mode:
            # With JSON mode, OpenAI handles JSON formatting automatically
            # We only need to ensure the prompt mentions JSON is expected (minimal)
            # No need to append full schema - saves ~100-200 tokens
            full_prompt = prompt
            logger.debug(f"LLM structured invoke (JSON mode): schema_keys={list(response_format.keys())}, prompt={len(full_prompt)} chars")
        else:
            # Fallback for non-OpenAI providers: append schema instructions
            format_instructions = f"\n\nRespond in JSON format matching this schema: {json.dumps(response_format, indent=2)}"
            full_prompt = prompt + format_instructions
            logger.debug(f"LLM structured invoke (fallback): schema_keys={list(response_format.keys())}, prompt={len(full_prompt)} chars")
        
        # Note: Prompt caching will be implemented in Phase 2 using message-based approach
        # For now, just use standard invoke
        response_text = self.invoke(full_prompt, **kwargs)
        
        # Try to parse JSON from response
        try:
            # With JSON mode, response should already be valid JSON (no markdown)
            # But we still handle markdown code blocks for compatibility
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

