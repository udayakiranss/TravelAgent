import logging
from typing import Dict, Any, Optional
from ..strategy.config_loader import ConfigLoader

logger = logging.getLogger(__name__)

class PromptRepository:
    """
    Repository for managing and retrieving prompts.
    Handles template substitution.
    """
    
    @staticmethod
    def get_structured_prompt(prompt_name: str, **kwargs) -> Dict[str, Optional[str]]:
        """
        Retrieve and format a prompt as structured format (system/user).
        
        Returns dict with 'system' and 'user' keys. System can be None if not provided.
        This enables optimal prompt caching by separating static instructions (system)
        from variable data (user).
        
        Args:
            prompt_name: The key in prompts.yaml
            **kwargs: Variables to substitute in the template
            
        Returns:
            Dict with 'system' (optional) and 'user' keys (both formatted)
        """
        prompts = ConfigLoader.load_prompts()
        
        if prompt_name not in prompts:
            raise ValueError(f"Prompt '{prompt_name}' not found in configuration")
        
        prompt_data = prompts[prompt_name]
        
        if isinstance(prompt_data, dict):
            system_prompt = prompt_data.get("system")
            user_prompt = prompt_data.get("user")
            
            # User prompt is required, system can be None (null in YAML)
            if not user_prompt:
                raise ValueError(
                    f"Prompt '{prompt_name}' must have a 'user' key "
                    "for structured format."
                )
            
            # Format both with kwargs (system may be None)
            try:
                result = {
                    "user": user_prompt.format(**kwargs)
                }
                if system_prompt:
                    result["system"] = system_prompt.format(**kwargs)
                else:
                    result["system"] = None
                return result
            except KeyError as e:
                logger.error(f"Missing variable for prompt '{prompt_name}': {e}")
                raise
            except Exception as e:
                logger.error(f"Failed to format prompt '{prompt_name}': {e}")
                raise
        else:
            raise ValueError(
                f"Prompt '{prompt_name}' is not structured (system/user). "
                "Use get_prompt() for string prompts."
            )
    
    @staticmethod
    def get_prompt(prompt_name: str, **kwargs) -> str:
        """
        Retrieve and format a prompt by name.
        
        Args:
            prompt_name: The key in prompts.yaml
            **kwargs: Variables to substitute in the template
            
        Returns:
            Formatted prompt string
        """
        try:
            structured = PromptRepository.get_structured_prompt(prompt_name, **kwargs)
            
            parts = []
            if structured.get("system"):
                parts.append(f"System: {structured['system']}")
            if structured.get("user"):
                parts.append(structured["user"])
                
            return "\n\n".join(parts)
            
        except Exception as e:
            logger.error(f"Failed to get prompt '{prompt_name}': {e}")
            raise
