import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class ConfigLoader:
    """
    Loads and validates LLM configuration from YAML files.
    Handles environment variable resolution for secrets.
    """
    
    _config_cache: Optional[Dict[str, Any]] = None
    _prompts_cache: Optional[Dict[str, Any]] = None
    
    @classmethod
    def get_base_path(cls) -> Path:
        """Get the base path for config files."""
        # Assumes this file is in llm/strategy/
        return Path(__file__).parent.parent / "config"

    @classmethod
    def load_model_strategy(cls) -> Dict[str, Any]:
        """
        Load the model_strategy.yaml file.
        Returns the raw dict configuration.
        """
        if cls._config_cache is not None:
            return cls._config_cache
            
        config_path = cls.get_base_path() / "model_strategy.yaml"
        if not config_path.exists():
            raise FileNotFoundError(f"Model strategy config not found at {config_path}")
            
        try:
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)
                
            cls._validate_config_structure(config)
            cls._resolve_env_vars(config)
            
            cls._config_cache = config
            return config
        except Exception as e:
            logger.error(f"Failed to load model strategy: {e}")
            raise

    @classmethod
    def load_prompts(cls) -> Dict[str, str]:
        """
        Load the prompts.yaml file.
        Returns a dict of prompt_name -> prompt_template.
        """
        if cls._prompts_cache is not None:
            return cls._prompts_cache
            
        prompts_path = cls.get_base_path() / "prompts.yaml"
        if not prompts_path.exists():
            raise FileNotFoundError(f"Prompts config not found at {prompts_path}")
            
        try:
            with open(prompts_path, "r") as f:
                data = yaml.safe_load(f)
                
            if "prompts" not in data:
                raise ValueError("prompts.yaml must contain a 'prompts' root key")
                
            # Flatten prompt structure if needed or valid as is
            # The structure in prompts.yaml is: key -> {system: ..., user: ...} or just string?
            # Design doc examples showed: key -> {system: ..., user: ...}
            # We return the whole dict under 'prompts'
            
            cls._prompts_cache = data["prompts"]
            return cls._prompts_cache
        except Exception as e:
            logger.error(f"Failed to load prompts: {e}")
            raise

    @classmethod
    def _validate_config_structure(cls, config: Dict[str, Any]):
        """Validate top-level structure of model strategy."""
        required_sections = ["use_cases", "providers", "defaults"]
        for section in required_sections:
            if section not in config:
                raise ValueError(f"Model strategy missing required section: {section}")

    @classmethod
    def _resolve_env_vars(cls, config: Dict[str, Any]):
        """
        Recursively find `api_key_env` keys and inject `api_key` from os.environ.
        IN-PLACE modification.
        """
        if isinstance(config, dict):
            # If we find api_key_env, try to resolve it
            if "api_key_env" in config:
                env_var_name = config["api_key_env"]
                api_key = os.environ.get(env_var_name)
                
                if not api_key:
                    # We accept that keys might be missing if that provider isn't used.
                    # Warning is sufficient.
                    logger.debug(f"Environment variable {env_var_name} not found. Provider may fail if used.")
                else:
                    config["api_key"] = api_key
            
            # Recurse
            for key, value in config.items():
                cls._resolve_env_vars(value)
                
        elif isinstance(config, list):
            for item in config:
                cls._resolve_env_vars(item)
