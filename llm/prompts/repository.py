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
        prompts = ConfigLoader.load_prompts()
        
        if prompt_name not in prompts:
            raise ValueError(f"Prompt '{prompt_name}' not found in configuration")
            
        prompt_data = prompts[prompt_name]
        
        # Handle simple string prompts or structured (system/user)
        # For this version, we flatten to a single string if it's structured,
        # or just return the user part if system is null.
        # Design doc implied returning a single string for 'invoke'.
        # If we need system prompt separation, we might need a richer return type later.
        # For now, let's assume we return the 'user' part or concatenate.
        
        template = ""
        if isinstance(prompt_data, str):
            template = prompt_data
        elif isinstance(prompt_data, dict):
            # If system prompt is present, we might prepend it or handle it differently.
            # Current agents mostly use a single prompt string or build it manually.
            # Let's concatenate for now: System + \n\n + User
            parts = []
            if prompt_data.get("system"):
                parts.append(f"System: {prompt_data['system']}")
            if prompt_data.get("user"):
                parts.append(prompt_data["user"])
            template = "\n\n".join(parts)
        else:
            raise ValueError(f"Invalid prompt format for '{prompt_name}'")
            
        try:
            return template.format(**kwargs)
        except KeyError as e:
            logger.error(f"Missing variable for prompt '{prompt_name}': {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to format prompt '{prompt_name}': {e}")
            raise
