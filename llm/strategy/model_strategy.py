import logging
from typing import Dict, Any, Optional
from .use_cases import UseCase
from .config_loader import ConfigLoader
from ..providers.factory import ProviderFactory
from ..providers.base import LLMProvider
from ..prompts.repository import PromptRepository

logger = logging.getLogger(__name__)

class ModelInvocationStrategy:
    """
    Central strategy for invoking LLMs based on use cases.
    """
    
    def __init__(self):
        # We load config once to fail fast if invalid
        self.config = ConfigLoader.load_model_strategy()
    
    def get_llm_for_use_case(self, use_case: UseCase) -> LLMProvider:
        """
        Get a configured LLM provider for the specified use case.
        
        Args:
            use_case: The use case enum value
            
        Returns:
            Configured LLMProvider instance
        """
        use_case_config = self._get_use_case_config(use_case)
        return ProviderFactory.create_provider(use_case_config)
    
    def get_structured_prompt_for_use_case(self, use_case: UseCase, **kwargs) -> Dict[str, str]:
        """
        Get the formatted prompt as structured format (system/user) for a use case.
        
        This enables optimal prompt caching by separating static instructions (system)
        from variable data (user).
        
        Args:
            use_case: The use case enum value
            **kwargs: Template variables
            
        Returns:
            Dict with 'system' and 'user' keys (both formatted)
        """
        use_case_config = self._get_use_case_config(use_case)
        prompt_name = use_case_config.get("prompt")
        
        if not prompt_name:
            raise ValueError(f"No prompt defined for use case '{use_case.value}'")
        
        return PromptRepository.get_structured_prompt(prompt_name, **kwargs)
    
    def get_prompt_for_use_case(self, use_case: UseCase, **kwargs) -> str:
        """
        Get the formatted prompt for a use case.
        
        Args:
            use_case: The use case enum value
            **kwargs: Template variables
            
        Returns:
            Formatted prompt string
        """
        use_case_config = self._get_use_case_config(use_case)
        prompt_name = use_case_config.get("prompt")
        
        if not prompt_name:
            raise ValueError(f"No prompt defined for use case '{use_case.value}'")
            
        return PromptRepository.get_prompt(prompt_name, **kwargs)
        
    def _get_use_case_config(self, use_case: UseCase) -> Dict[str, Any]:
        """
        Resolve configuration for a use case.
        Merges:
        1. Provider defaults
        2. Global defaults (TODO: implement if needed, currently skipping)
        3. Use case overrides
        """
        use_cases = self.config.get("use_cases", {})
        if use_case.value not in use_cases:
            raise ValueError(f"Use case '{use_case.value}' not defined in configuration")
            
        uc_config = use_cases[use_case.value]
        
        provider_name = uc_config.get("provider")
        model_name = uc_config.get("model")
        
        # Get provider config to check for default api keys, etc.
        providers_config = self.config.get("providers", {})
        provider_details = providers_config.get(provider_name, {})
        
        # Resolve API Key: 
        # 1. From Use Case override (unlikely)
        # 2. From Provider specific settings (common)
        api_key = provider_details.get("provider_specific_settings", {}).get("api_key")
        
        # Prepare resolved config
        resolved = {
            "provider": provider_name,
            "model": model_name,
            "prompt": uc_config.get("prompt"),
            "api_key": api_key,
            "overrides": uc_config.get("overrides", {})
        }
        
        return resolved
