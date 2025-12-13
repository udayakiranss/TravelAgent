import json
import logging
from typing import Dict, Any, Optional, List
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from .base import LLMProvider
from utils.logger import Timer

logger = logging.getLogger(__name__)

class OpenAIProvider(LLMProvider):
    """OpenAI Provider implementation using LangChain."""
    
    def __init__(self, model_name: str, temperature: float = 0, api_key: Optional[str] = None, **kwargs):
        super().__init__(model_name, temperature, **kwargs)
        
        # Extract provider-specific settings
        self.enable_json_mode = kwargs.get("enable_json_mode", False)
        self.enable_prompt_caching = kwargs.get("enable_prompt_caching", False)
        
        model_kwargs = {}
        if self.enable_json_mode:
            model_kwargs["response_format"] = {"type": "json_object"}
            
        self.llm = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            api_key=api_key,
            model_kwargs=model_kwargs
        )
        
    def invoke(self, prompt: str, **kwargs) -> str:
        """Invoke LLM with text output."""
        try:
            # Skip timing if called internally (e.g., from invoke_structured)
            skip_timing = kwargs.pop("_skip_timing", False)
            
            def _do_invoke():
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
                
            return response.content if hasattr(response, 'content') else str(response)
        except Exception as e:
            logger.error(f"OpenAI invoke failed: {e}")
            raise

    def invoke_structured(self, prompt: str, response_format: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Invoke LLM with expected JSON output."""
        try:
            with Timer(f"LLM structured call ({self.model_name})", level="INFO") as timer:
                # If JSON mode is enabled, we expect valid JSON.
                # If not, we append schema instructions (fallback).
                full_prompt = prompt
                if not self.enable_json_mode:
                    full_prompt += f"\n\nRespond in JSON format matching: {json.dumps(response_format, indent=2)}"
                
                # Skip timing in nested invoke call to avoid double timing
                response_text = self.invoke(full_prompt, _skip_timing=True, **kwargs)
                parsed = self._parse_json(response_text)
            return parsed
        except Exception as e:
            logger.warning(f"OpenAI structured invoke failed: {e}")
            raise

    def bind_tools(self, tools: list):
        """Bind tools to the LLM."""
        return self.llm.bind_tools(tools)
        
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
