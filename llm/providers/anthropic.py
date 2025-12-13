import logging
from typing import Dict, Any, Optional, List
from langchain_anthropic import ChatAnthropic
from .base import LLMProvider
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
        
    def invoke(self, prompt: str, **kwargs) -> str:
        """Invoke LLM with text output."""
        try:
            # Skip timing if called internally (e.g., from invoke_structured)
            skip_timing = kwargs.pop("_skip_timing", False)
            
            if skip_timing:
                response = self.llm.invoke(prompt)
            else:
                with Timer(f"LLM call ({self.model_name})", level="INFO") as timer:
                    response = self.llm.invoke(prompt)
            return response.content if hasattr(response, 'content') else str(response)
        except Exception as e:
            logger.error(f"Anthropic invoke failed: {e}")
            raise

    def invoke_structured(self, prompt: str, response_format: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Invoke LLM with expected JSON output."""
        try:
            with Timer(f"LLM structured call ({self.model_name})", level="INFO") as timer:
                # Fallback to prompt engineering for JSON unless using tools
                import json
                full_prompt = prompt + f"\n\nRespond in JSON format matching: {json.dumps(response_format, indent=2)}"
                
                # Skip timing in nested invoke call to avoid double timing
                response_text = self.invoke(full_prompt, _skip_timing=True, **kwargs)
                parsed = self._parse_json(response_text)
            return parsed
        except Exception as e:
            logger.warning(f"Anthropic structured invoke failed: {e}")
            raise

    def bind_tools(self, tools: list):
        """Bind tools to the LLM."""
        return self.llm.bind_tools(tools)

    def _parse_json(self, text: str) -> Dict[str, Any]:
        """Safe JSON parsing."""
        import json
        try:
            clean_text = text.strip()
            if "```json" in clean_text:
                clean_text = clean_text.split("```json")[1].split("```")[0]
            elif "```" in clean_text:
                clean_text = clean_text.split("```")[1].split("```")[0]
            
            return json.loads(clean_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from Anthropic: {e}")
            raise
