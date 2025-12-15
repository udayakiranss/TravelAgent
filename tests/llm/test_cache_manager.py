"""
Unit tests for CacheKeyManager.
"""
import pytest
from llm.providers.cache_manager import CacheKeyManager
from llm.strategy.use_cases import UseCase


class TestCacheKeyManager:
    """Test cache key generation and management."""
    
    def test_generate_cache_key_custom(self):
        """Test custom cache key takes highest priority."""
        key = CacheKeyManager.generate_cache_key(custom_key="my_custom_key")
        assert key == "my_custom_key"
    
    def test_generate_cache_key_with_prefix_and_prompt(self):
        """Test cache key generation with prefix and system prompt."""
        system_prompt = "You are a helpful assistant."
        prefix = "planner_v1"
        
        key = CacheKeyManager.generate_cache_key(
            system_prompt=system_prompt,
            prefix=prefix
        )
        
        assert key.startswith("planner_v1_")
        assert len(key) > len("planner_v1_")
        # Should include hash of system prompt
    
    def test_generate_cache_key_with_use_case_and_prompt(self):
        """Test cache key generation with use case and system prompt."""
        system_prompt = "You are a helpful assistant."
        
        key = CacheKeyManager.generate_cache_key(
            system_prompt=system_prompt,
            use_case=UseCase.PLANNER
        )
        
        assert key.startswith("planner_")
        assert len(key) > len("planner_")
    
    def test_generate_cache_key_same_prompt_same_key(self):
        """Test that same prompt generates same cache key."""
        system_prompt = "You are a helpful assistant."
        prefix = "test"
        
        key1 = CacheKeyManager.generate_cache_key(
            system_prompt=system_prompt,
            prefix=prefix
        )
        key2 = CacheKeyManager.generate_cache_key(
            system_prompt=system_prompt,
            prefix=prefix
        )
        
        assert key1 == key2, "Same prompt should generate same cache key"
    
    def test_generate_cache_key_different_prompts_different_keys(self):
        """Test that different prompts generate different cache keys."""
        prefix = "test"
        
        key1 = CacheKeyManager.generate_cache_key(
            system_prompt="You are a helpful assistant.",
            prefix=prefix
        )
        key2 = CacheKeyManager.generate_cache_key(
            system_prompt="You are a travel agent.",
            prefix=prefix
        )
        
        assert key1 != key2, "Different prompts should generate different cache keys"
    
    def test_generate_cache_key_prefix_only(self):
        """Test cache key generation with only prefix."""
        key = CacheKeyManager.generate_cache_key(prefix="test_prefix")
        assert key == "test_prefix"
    
    def test_generate_cache_key_use_case_only(self):
        """Test cache key generation with only use case."""
        key = CacheKeyManager.generate_cache_key(use_case=UseCase.PLANNER)
        assert key == "planner"
    
    def test_generate_cache_key_system_prompt_only(self):
        """Test cache key generation with only system prompt."""
        system_prompt = "You are a helpful assistant."
        key = CacheKeyManager.generate_cache_key(system_prompt=system_prompt)
        
        # Should be just the hash
        assert len(key) > 0
        assert key != system_prompt
    
    def test_generate_cache_key_no_params(self):
        """Test cache key generation with no parameters (fallback)."""
        key = CacheKeyManager.generate_cache_key()
        assert key == "default_cache_key"
    
    def test_extract_system_prompt_from_dict(self):
        """Test extracting system prompt from structured prompt dict."""
        prompt = {
            "system": "You are a helpful assistant.",
            "user": "What is the weather?"
        }
        
        system_prompt = CacheKeyManager.extract_system_prompt(prompt)
        assert system_prompt == "You are a helpful assistant."
    
    def test_extract_system_prompt_from_string(self):
        """Test extracting system prompt from string (should return None)."""
        prompt = "You are a helpful assistant."
        system_prompt = CacheKeyManager.extract_system_prompt(prompt)
        assert system_prompt is None
    
    def test_extract_system_prompt_no_system_key(self):
        """Test extracting system prompt from dict without system key."""
        prompt = {
            "user": "What is the weather?"
        }
        
        system_prompt = CacheKeyManager.extract_system_prompt(prompt)
        assert system_prompt is None
    
    def test_should_use_caching_enabled_with_prompt(self):
        """Test should_use_caching returns True when enabled and prompt exists."""
        result = CacheKeyManager.should_use_caching(
            system_prompt="You are a helpful assistant.",
            enable_prompt_caching=True
        )
        assert result is True
    
    def test_should_use_caching_disabled(self):
        """Test should_use_caching returns False when disabled."""
        result = CacheKeyManager.should_use_caching(
            system_prompt="You are a helpful assistant.",
            enable_prompt_caching=False
        )
        assert result is False
    
    def test_should_use_caching_no_prompt(self):
        """Test should_use_caching returns False when no system prompt."""
        result = CacheKeyManager.should_use_caching(
            system_prompt=None,
            enable_prompt_caching=True
        )
        assert result is False
    
    def test_should_use_caching_empty_prompt(self):
        """Test should_use_caching returns False for empty prompt."""
        result = CacheKeyManager.should_use_caching(
            system_prompt="   ",
            enable_prompt_caching=True
        )
        assert result is False
    
    def test_hash_content_deterministic(self):
        """Test that hash_content produces deterministic results."""
        content = "Test content"
        hash1 = CacheKeyManager._hash_content(content)
        hash2 = CacheKeyManager._hash_content(content)
        
        assert hash1 == hash2
        assert len(hash1) == 16  # Should be 16 characters
