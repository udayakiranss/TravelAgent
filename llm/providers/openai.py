import json
import logging
from typing import Dict, Any, Optional, List, Union, Type
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from .base import LLMProvider
from .cache_manager import CacheKeyManager
from llm.strategy.use_cases import UseCase
from utils.logger import Timer

logger = logging.getLogger(__name__)

class OpenAIProvider(LLMProvider):
    """OpenAI Provider implementation using LangChain."""
    
    def __init__(self, model_name: str, temperature: float = 0, api_key: Optional[str] = None, **kwargs):
        super().__init__(model_name, temperature, **kwargs)
        
        # Extract provider-specific settings
        self.enable_json_mode = kwargs.get("enable_json_mode", False)
        # Cache configuration
        self.cache_ttl = kwargs.get("cache_ttl", "24h")  # Not used for OpenAI but kept for consistency
        self.cache_key_prefix = kwargs.get("cache_key_prefix", None)
        
        model_kwargs = {}
        if self.enable_json_mode:
            model_kwargs["response_format"] = {"type": "json_object"}
            
        self.llm = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            api_key=api_key,
            model_kwargs=model_kwargs
        )
        
    def invoke(self, prompt: Union[str, Dict[str, str]], **kwargs) -> str:
        """
        Invoke LLM with text output.
        
        Automatically handles structured prompts (system/user) for optimal prompt caching.
        Falls back to single message for backward compatibility.
        
        Args:
            prompt: String or dict with 'system'/'user' keys
            **kwargs: Additional arguments:
                - cache_key: Optional cache key for prompt caching
                - use_case: Optional use case identifier for cache key generation
                - cache_key_prefix: Optional prefix for cache key generation
        """
        try:
            # Skip timing if called internally (e.g., from invoke_structured)
            skip_timing = kwargs.pop("_skip_timing", False)
            
            # Extract cache-related kwargs
            cache_key = kwargs.pop("cache_key", None)
            use_case = kwargs.pop("use_case", None)
            cache_key_prefix = kwargs.pop("cache_key_prefix", self.cache_key_prefix)
            
            # Generate cache key if caching is enabled
            prompt_cache_key = None
            if self.enable_prompt_caching:
                system_prompt = CacheKeyManager.extract_system_prompt(prompt)
                if CacheKeyManager.should_use_caching(system_prompt, self.enable_prompt_caching):
                    prompt_cache_key = cache_key or CacheKeyManager.generate_cache_key(
                        system_prompt=system_prompt,
                        use_case=use_case,
                        prefix=cache_key_prefix
                    )
                    logger.debug(f"Using prompt cache key: {prompt_cache_key}")
            
            def _do_invoke():
                # Handle structured prompt (dict with system/user) for optimal caching
                if isinstance(prompt, dict):
                    messages = []
                    
                    # Add system message (static instructions - gets cached)
                    if prompt.get("system"):
                        messages.append(SystemMessage(content=prompt["system"]))
                    
                    # Add user message (variable data - not cached)
                    if prompt.get("user"):
                        messages.append(HumanMessage(content=prompt["user"]))
                    
                    if not messages:
                        raise ValueError("Structured prompt must have 'system' or 'user'")
                    
                    # Handle disable_json_mode override
                    if kwargs.get("disable_json_mode") and self.enable_json_mode:
                        temp_llm = ChatOpenAI(
                            model=self.model_name,
                            temperature=self.temperature,
                            api_key=self.llm.openai_api_key,
                            model_kwargs={} # No response_format
                        )
                        return temp_llm.invoke(messages)
                    else:
                        return self.llm.invoke(messages)
                
                # Handle string prompt (backward compatible)
                else:
                    # Handle disable_json_mode override
                    if kwargs.get("disable_json_mode") and self.enable_json_mode:
                        # Create temporary LLM without JSON mode
                        temp_llm = ChatOpenAI(
                            model=self.model_name,
                            temperature=self.temperature,
                            api_key=self.llm.openai_api_key,
                            model_kwargs={} # No response_format
                        )
                        return temp_llm.invoke(prompt)
                    else:
                        return self.llm.invoke(prompt)
            
            if skip_timing:
                response = _do_invoke()
            else:
                with Timer(f"LLM call ({self.model_name})", level="INFO") as timer:
                    response = _do_invoke()
            
            # Log cache usage if available
            cache_usage = self.extract_cache_usage(response)
            if cache_usage and cache_usage.get("cache_read_tokens", 0) > 0:
                logger.info(f"Cache hit: {cache_usage['cache_read_tokens']} tokens read from cache")
                
            return response.content if hasattr(response, 'content') else str(response)
        except Exception as e:
            logger.error(f"OpenAI invoke failed: {e}")
            raise

    def invoke_structured(
        self, 
        prompt: Union[str, Dict[str, str]], 
        response_format: Union[Dict[str, Any], Type[BaseModel]], 
        **kwargs
    ) -> Dict[str, Any]:
        """
        Invoke LLM with structured output.
        
        Supports both Pydantic models (via with_structured_output) and dict schemas
        (backward compatible JSON mode). Automatically handles structured prompts
        (system/user) for optimal prompt caching.
        
        Args:
            prompt: String or dict with 'system'/'user' keys
            response_format: Pydantic BaseModel class or dict JSON schema
        """
        try:
            with Timer(f"LLM structured call ({self.model_name})", level="INFO") as timer:
                # Check if Pydantic model provided
                if isinstance(response_format, type) and issubclass(response_format, BaseModel):
                    # Use with_structured_output for Pydantic models (new approach)
                    logger.debug(f"Using Pydantic model path: {response_format.__name__}")
                    return self._invoke_with_pydantic(prompt, response_format, **kwargs)
                else:
                    # Use JSON mode for dict schemas (backward compatible)
                    logger.debug(f"Using JSON mode path (dict schema)")
                    return self._invoke_structured_json_mode(prompt, response_format, **kwargs)
        except Exception as e:
            logger.warning(f"OpenAI structured invoke failed: {e}")
            raise
    
    def _invoke_with_pydantic(
        self, 
        prompt: Union[str, Dict[str, str]], 
        pydantic_model: Type[BaseModel], 
        **kwargs
    ) -> Dict[str, Any]:
        """
        Invoke LLM with Pydantic model using with_structured_output().
        
        This provides automatic validation and type safety.
        """
        logger.debug(f"Creating structured LLM with Pydantic model: {pydantic_model.__name__}")
        
        # Create structured LLM with Pydantic model
        structured_llm = self.llm.with_structured_output(pydantic_model)
        
        # Handle structured prompts (dict with system/user)
        if isinstance(prompt, dict):
            messages = []
            
            # Add system message
            if prompt.get("system"):
                messages.append(SystemMessage(content=prompt["system"]))
            
            # Add user message (ensure "json" word for OpenAI requirement)
            if prompt.get("user"):
                user_content = prompt["user"]
                # Check if "json" exists (required by OpenAI for response_format json_object)
                if "json" not in user_content.lower() and "json" not in prompt.get("system", "").lower():
                    user_content += "\n\nReturn a JSON object."
                messages.append(HumanMessage(content=user_content))
            
            if not messages:
                raise ValueError("Structured prompt must have 'system' or 'user'")
            
            response = structured_llm.invoke(messages)
        else:
            # Handle string prompt
            # Ensure "json" word exists for OpenAI requirement
            if "json" not in prompt.lower():
                prompt = prompt + "\n\nReturn a JSON object."
            response = structured_llm.invoke(prompt)
        
        # Convert Pydantic model instance to dict
        if isinstance(response, BaseModel):
            return response.model_dump()
        else:
            # If it's already a dict (from manual parsing), return as-is
            return response
    
    def _invoke_structured_json_mode(
        self, 
        prompt: Union[str, Dict[str, str]], 
        response_format: Dict[str, Any], 
        **kwargs
    ) -> Dict[str, Any]:
        """
        Invoke LLM with dict schema using JSON mode (backward compatible).
        
        This maintains compatibility with planner and deterministic planner.
        """
        # OpenAI API requirement: When using response_format json_object, 
        # the word "json" must appear in the messages
        json_instruction = "Return a JSON object"
        
        # Handle both string and dict prompts
        if isinstance(prompt, dict):
            # For structured prompts, add JSON instruction to user message
            # Check if "json" already exists in system or user prompt
            system_text = prompt.get("system", "").lower()
            user_text = prompt.get("user", "").lower()
            
            if "json" not in system_text and "json" not in user_text:
                # Add JSON instruction to user message
                prompt = {
                    "system": prompt.get("system", ""),
                    "user": prompt.get("user", "") + f"\n\n{json_instruction}."
                }
        else:
            # For string prompts, check if "json" exists
            if "json" not in prompt.lower():
                prompt = prompt + f"\n\n{json_instruction}."
            # If JSON mode not enabled, also add schema
            if not self.enable_json_mode:
                prompt += f"\n\nRespond in JSON format matching: {json.dumps(response_format, indent=2)}"
        
        # Skip timing in nested invoke call to avoid double timing
        response_text = self.invoke(
            prompt, 
            _skip_timing=True, 
            **kwargs
        )
        parsed = self._parse_json(response_text)
        return parsed

    def bind_tools(self, tools: list):
        """Bind tools to the LLM."""
        return self.llm.bind_tools(tools)
    
    def extract_cache_usage(self, response: Any) -> Optional[Dict[str, int]]:
        """
        Extract cache usage information from OpenAI response.
        
        Args:
            response: The OpenAI response object
            
        Returns:
            Dict with cache usage info, or None if not available.
            Format: {
                'cache_read_tokens': int,  # Tokens read from cache
            }
        """
        try:
            # OpenAI stores cache usage in usage_metadata.input_token_details.cache_read
            if hasattr(response, 'usage_metadata'):
                usage_metadata = response.usage_metadata
                if hasattr(usage_metadata, 'input_token_details'):
                    token_details = usage_metadata.input_token_details
                    if hasattr(token_details, 'cache_read_tokens'):
                        cache_read = token_details.cache_read_tokens
                        if cache_read and cache_read > 0:
                            return {
                                'cache_read_tokens': cache_read
                            }
            
            # Alternative: Check response_metadata
            if hasattr(response, 'response_metadata'):
                metadata = response.response_metadata
                # Check for cache usage in various possible locations
                if 'token_usage' in metadata:
                    token_usage = metadata['token_usage']
                    if 'cache_read_tokens' in token_usage:
                        return {
                            'cache_read_tokens': token_usage['cache_read_tokens']
                        }
            
            return None
        except Exception as e:
            logger.debug(f"Could not extract cache usage: {e}")
            return None
        
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
