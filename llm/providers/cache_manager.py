"""
Cache Key Manager for Prompt Caching

Generates stable cache keys from system prompts to enable efficient
prompt caching across LLM providers (OpenAI, Anthropic).
"""
import hashlib
import logging
from typing import Dict, Optional, Union
from llm.strategy.use_cases import UseCase

logger = logging.getLogger(__name__)


class CacheKeyManager:
    """
    Manages cache key generation for prompt caching.
    
    Generates stable, deterministic cache keys from system prompts
    to maximize cache hit rates across similar requests.
    """
    
    @staticmethod
    def generate_cache_key(
        system_prompt: Optional[str] = None,
        use_case: Optional[Union[UseCase, str]] = None,
        prefix: Optional[str] = None,
        custom_key: Optional[str] = None
    ) -> str:
        """
        Generate a stable cache key for prompt caching.
        
        Priority order:
        1. custom_key (if provided) - highest priority
        2. prefix + system_prompt hash (if both provided)
        3. use_case + system_prompt hash (if both provided)
        4. system_prompt hash only (if provided)
        5. use_case only (if provided)
        6. prefix only (if provided)
        
        Args:
            system_prompt: The system prompt content to hash
            use_case: Use case enum or string identifier
            prefix: Optional prefix for the cache key
            custom_key: Custom cache key (takes highest priority)
            
        Returns:
            A stable cache key string suitable for prompt caching
            
        Examples:
            >>> CacheKeyManager.generate_cache_key(
            ...     system_prompt="You are a helpful assistant",
            ...     use_case=UseCase.PLANNER
            ... )
            'planner_a1b2c3d4...'
            
            >>> CacheKeyManager.generate_cache_key(
            ...     custom_key="planner_v1"
            ... )
            'planner_v1'
        """
        # If custom key provided, use it directly
        if custom_key:
            logger.debug(f"Using custom cache key: {custom_key}")
            return custom_key
        
        # Build key components
        components = []
        
        # Add prefix if provided
        if prefix:
            components.append(prefix)
        
        # Add use case if provided
        if use_case:
            use_case_str = use_case.value if isinstance(use_case, UseCase) else str(use_case)
            if not prefix:  # Only add use_case if no prefix (prefix might already include use case)
                components.append(use_case_str)
        
        # Add system prompt hash if provided
        if system_prompt:
            prompt_hash = CacheKeyManager._hash_content(system_prompt)
            components.append(prompt_hash)
        
        # Generate final key
        if components:
            cache_key = "_".join(components)
            logger.debug(f"Generated cache key: {cache_key}")
            return cache_key
        else:
            # Fallback: generate a default key
            logger.warning("No cache key components provided, using default")
            return "default_cache_key"
    
    @staticmethod
    def _hash_content(content: str) -> str:
        """
        Generate a short hash from content.
        
        Uses SHA256 and returns first 16 characters for readability.
        
        Args:
            content: Content to hash
            
        Returns:
            Short hash string (16 characters)
        """
        hash_obj = hashlib.sha256(content.encode('utf-8'))
        return hash_obj.hexdigest()[:16]
    
    @staticmethod
    def extract_system_prompt(prompt: Union[str, Dict[str, str]]) -> Optional[str]:
        """
        Extract system prompt from various prompt formats.
        
        Args:
            prompt: Either a string prompt or dict with 'system'/'user' keys
            
        Returns:
            System prompt string if available, None otherwise
        """
        if isinstance(prompt, dict):
            return prompt.get("system")
        return None
    
    @staticmethod
    def should_use_caching(
        system_prompt: Optional[str] = None,
        enable_prompt_caching: bool = False
    ) -> bool:
        """
        Determine if caching should be used for a prompt.
        
        Args:
            system_prompt: System prompt content
            enable_prompt_caching: Feature flag for prompt caching
            
        Returns:
            True if caching should be enabled
        """
        if not enable_prompt_caching:
            return False
        
        # Only cache if we have a system prompt (static content)
        # User prompts (variable content) should not be cached
        if system_prompt and len(system_prompt.strip()) > 0:
            return True
        
        return False
