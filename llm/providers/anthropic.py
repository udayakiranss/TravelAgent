import logging
from typing import Dict, Any, Optional, List, Union, Type
from pydantic import BaseModel
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage
from .base import LLMProvider
from .factory import ProviderFactory
from utils.logger import Timer

logger = logging.getLogger(__name__)

class AnthropicProvider(LLMProvider):
    """Anthropic Provider implementation using LangChain."""
    
    def __init__(self, model_name: str, temperature: float = 0, api_key: Optional[str] = None, **kwargs):
        super().__init__(model_name, temperature, **kwargs)
        
        self.enable_json_mode = kwargs.get("enable_json_mode", False)

        
        # Anthropic doesn't have a direct "json_object" flag like OpenAI in the same way, 
        # but LangChain handles it or we rely on prompt engineering.
        # Recent Claude models support prefill or tool use for JSON.
        
        self.llm = ChatAnthropic(
            model=model_name,
            temperature=temperature,
            api_key=api_key
        )
        
    def invoke(self, prompt: Union[str, Dict[str, str]], **kwargs) -> str:
        """
        Invoke LLM with text output.
        
        Automatically handles structured prompts (system/user) for optimal prompt caching.
        Falls back to single message for backward compatibility.
        
        Args:
            prompt: String or dict with 'system'/'user' keys
            **kwargs: Additional arguments:
                - cache_key: Optional cache key for prompt caching (not used for Anthropic)
                - use_case: Optional use case identifier for cache key generation
                - cache_key_prefix: Optional prefix for cache key generation
        """
        try:
            # Skip timing if called internally (e.g., from invoke_structured)
            skip_timing = kwargs.pop("_skip_timing", False)
            
            def _do_invoke():
                # Handle structured prompt (dict with system/user) for optimal caching
                if isinstance(prompt, dict):
                    messages = []
                    
                    # Add system message with cache_control if caching is enabled
                    if prompt.get("system"):
                        system_content = prompt["system"]
                        
                        # Regular system message without caching
                        messages.append(SystemMessage(content=system_content))
                    
                    # Add user message (variable data - not cached)
                    if prompt.get("user"):
                        messages.append(HumanMessage(content=prompt["user"]))
                    
                    if not messages:
                        raise ValueError("Structured prompt must have 'system' or 'user'")
                    
                    return self.llm.invoke(messages)
                
                # Handle string prompt (backward compatible)
                # Note: String prompts can't use cache_control (need structured format)
                else:
                    return self.llm.invoke(prompt)
            
            if skip_timing:
                response = _do_invoke()
            else:
                with Timer(f"LLM call ({self.model_name})", level="INFO") as timer:
                    response = _do_invoke()
            

            
            return response.content if hasattr(response, 'content') else str(response)
        except Exception as e:
            logger.error(f"Anthropic invoke failed: {e}")
            raise

    def invoke_structured(
        self, 
        prompt: Union[str, Dict[str, str]], 
        response_format: Union[Dict[str, Any], Type[BaseModel]], 
        **kwargs
    ) -> Dict[str, Any]:
        """
        Invoke LLM with structured output.
        
        Supports both Pydantic models and dict schemas (backward compatible).
        Note: Anthropic may not support with_structured_output, so falls back to prompt engineering.
        """
        try:
            with Timer(f"LLM structured call ({self.model_name})", level="INFO") as timer:
                # Check if Pydantic model provided
                if isinstance(response_format, type) and issubclass(response_format, BaseModel):
                    # Try with_structured_output if available, otherwise fallback
                    try:
                        structured_llm = self.llm.with_structured_output(response_format)
                        
                        # Handle structured prompts
                        if isinstance(prompt, dict):
                            messages = []
                            # Apply cache_control to system message if caching enabled
                            if prompt.get("system"):
                                system_content = prompt["system"]
                                messages.append(SystemMessage(content=system_content))
                            if prompt.get("user"):
                                messages.append(HumanMessage(content=prompt["user"]))
                            response = structured_llm.invoke(messages)
                        else:
                            # String prompts can't use cache_control
                            response = structured_llm.invoke(prompt)
                        
                        return response.model_dump()
                    except (AttributeError, NotImplementedError):
                        # with_structured_output not available, fallback to prompt engineering
                        logger.debug("with_structured_output not available for Anthropic, using prompt engineering")
                        return self._invoke_structured_json_mode(prompt, response_format, **kwargs)
                else:
                    # Dict schema - use prompt engineering
                    return self._invoke_structured_json_mode(prompt, response_format, **kwargs)
        except Exception as e:
            logger.warning(f"Anthropic structured invoke failed: {e}")
            raise
    
    def _invoke_structured_json_mode(
        self, 
        prompt: Union[str, Dict[str, str]], 
        response_format: Dict[str, Any], 
        **kwargs
    ) -> Dict[str, Any]:
        """Invoke with dict schema using prompt engineering (backward compatible)."""
        import json
        
        # Handle structured prompts
        if isinstance(prompt, dict):
            user_content = prompt.get("user", "")
            full_prompt = {
                "system": prompt.get("system", ""),
                "user": user_content + f"\n\nRespond in JSON format matching: {json.dumps(response_format, indent=2)}"
            }
        else:
            full_prompt = prompt + f"\n\nRespond in JSON format matching: {json.dumps(response_format, indent=2)}"
        
        # Skip timing in nested invoke call to avoid double timing
        response_text = self.invoke(full_prompt, _skip_timing=True, **kwargs)
        parsed = self._parse_json(response_text)
        return parsed

    def bind_tools(self, tools: list):
        """Bind tools to the LLM."""
        return self.llm.bind_tools(tools)
    
        
# Register the provider
ProviderFactory.register_provider("anthropic", AnthropicProvider)
