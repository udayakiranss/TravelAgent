# response_formatter.py
# LLM-powered formatter that converts JSON agent results to natural language
from typing import Dict, Any, Optional, Literal, Union
import json
from pydantic import BaseModel, Field
from agents.core.llm_provider import LLMProvider
from utils.logger import get_logger, log_method_entry_exit
from llm.strategy.model_strategy import ModelInvocationStrategy
from llm.strategy.use_cases import UseCase

logger = get_logger()

# Supported output formats when LLM is not available
OutputFormat = Literal["key_value", "structured", "json"]


class SummarySchema(BaseModel):
    """
    Pydantic schema for structured summary output.
    
    Used with with_structured_output() for type-safe validation and automatic parsing.
    """
    header: str = Field(description="Welcoming header mentioning destination (1-2 sentences)")
    flight: str = Field(description="Flight summary (airline, times, duration, price)")
    hotel: str = Field(description="Hotel summary (name, location, price, rating)")
    car: str = Field(description="Car summary or 'No car booked'")
    total_cost: float = Field(description="Total cost as numeric value")
    closing: str = Field(description="Friendly closing message (1-2 sentences)")


class ResponseFormatter:
    """Formats agent results into natural language summaries using LLM"""
    
    def __init__(self, llm: Optional[LLMProvider] = None, output_format: OutputFormat = "key_value", 
                 model_strategy: Optional[ModelInvocationStrategy] = None):
        """
        Initialize the response formatter
        
        Args:
            llm: LLM provider for generating natural language (optional)
            output_format: Format to use when LLM is not available
                          - "key_value": Simple key: value pairs (default)
                          - "structured": Formatted text with sections
                          - "json": Raw JSON output
            model_strategy: Optional ModelInvocationStrategy to get prompt from prompts.yaml
        """
        self.llm = llm
        self.output_format = output_format
        self.model_strategy = model_strategy
        logger.debug(f"ResponseFormatter initialized with format: {output_format}")
    
    @log_method_entry_exit(level="INFO")
    def format_results(self, results: Dict[str, Any], intent: Dict[str, Any]) -> str:
        """
        Convert agent results dictionary to a natural language summary
        
        Args:
            results: Dictionary of results from all agents (keyed by "AgentName.task")
            intent: Original user intent with travel details (from, to, date, needs)
        
        Returns:
            Natural language summary of the travel booking
        """
        logger.info("Formatting results")
        logger.debug(f"Results keys: {list(results.keys())}")
        logger.debug(f"Intent: {intent}")
        
        # If no LLM available, use fallback format
        if self.llm is None:
            logger.info(f"No LLM available, using {self.output_format} format")
            return self._fallback_format(results, intent)
        
        # Build the prompt for the LLM
        prompt = self._build_prompt(results, intent)
        
        try:
            # Phase 2: Use JSON mode + template rendering for faster generation
            # Check if LLM has JSON mode enabled (via model_strategy config)
            # If enabled, use invoke_structured to get JSON, then render with template
            # If not enabled, fallback to prose generation
            
            # Try structured output approach first (faster - uses with_structured_output)
            try:
                # Generate structured JSON summary using Pydantic model
                # This uses with_structured_output() for automatic validation
                json_data = self.llm.invoke_structured(
                    prompt,
                    response_format=SummarySchema  # Pydantic model, not dict
                )
                logger.debug(f"Generated JSON summary fields: {list(json_data.keys())}")
                
                # Render JSON into natural language using template
                summary = self._render_template(json_data)
                logger.info("Successfully generated natural language summary from JSON template")
                return summary.strip()
            except (ValueError, KeyError, TypeError) as json_error:
                # Structured output not available or failed, fallback to prose generation
                logger.debug(f"Structured output not available or failed: {json_error}, falling back to prose generation")
                summary = self.llm.invoke(prompt, disable_json_mode=True)
                logger.info("Successfully generated natural language summary (prose)")
                return summary.strip()
        except Exception as e:
            logger.error(f"Failed to generate natural language summary: {e}", exc_info=True)
            # Return a basic fallback summary
            return self._fallback_format(results, intent)
    
    def _build_prompt(self, results: Dict[str, Any], intent: Dict[str, Any]) -> Union[str, Dict[str, str]]:
        """
        Build the LLM prompt for formatting results - returns structured format if available.
        
        Returns structured format (dict with system/user) for optimal prompt caching,
        falls back to string format for backward compatibility.
        """
        
        # Extract key information from intent
        origin = intent.get('from', 'Unknown')
        destination = intent.get('to', 'Unknown')
        date = intent.get('date', 'Unknown')
        needs = intent.get('needs', [])
        services = ', '.join(needs) if needs else 'Not specified'
        
        # Serialize results for the prompt
        results_json = json.dumps(results, indent=2, default=str)
        
        # Prompt must come from prompts.yaml via model_strategy
        if not self.model_strategy:
            raise ValueError(
                "model_strategy is required. Prompt must come from prompts.yaml. "
                "Ensure ResponseFormatter is initialized with model_strategy."
            )
        
        try:
            # Try to get structured prompt (system/user) for optimal caching
            try:
                prompt = self.model_strategy.get_structured_prompt_for_use_case(
                    UseCase.SUMMARY_GENERATION,
                    origin=origin,
                    destination=destination,
                    date=date,
                    services=services,
                    results_json=results_json
                )
                logger.debug(
                    f"Retrieved structured prompt from prompts.yaml "
                    f"(system: {len(prompt.get('system', ''))} chars, "
                    f"user: {len(prompt.get('user', ''))} chars)"
                )
                return prompt
            except (ValueError, KeyError):
                # Fallback to regular prompt if structured not available
                logger.debug("Structured prompt not available, using regular prompt")
                prompt = self.model_strategy.get_prompt_for_use_case(
                    UseCase.SUMMARY_GENERATION,
                    origin=origin,
                    destination=destination,
                    date=date,
                    services=services,
                    results_json=results_json
                )
                logger.debug(f"Retrieved prompt from prompts.yaml ({len(prompt)} characters)")
                return prompt
        except Exception as e:
            logger.error(f"Failed to get prompt from prompts.yaml: {e}")
            raise ValueError(f"Cannot proceed without prompt from prompts.yaml: {e}") from e
    
    def _fallback_format(self, results: Dict[str, Any], intent: Dict[str, Any]) -> str:
        """Fallback formatter when LLM is unavailable - uses configured output_format"""
        logger.info(f"Using fallback formatter with format: {self.output_format}")
        
        if self.output_format == "json":
            return self._format_json(results, intent)
        elif self.output_format == "structured":
            return self._format_structured(results, intent)
        else:  # Default: key_value
            return self._format_key_value(results, intent)
    
    def _format_key_value(self, results: Dict[str, Any], intent: Dict[str, Any]) -> str:
        """Format results as simple key-value pairs"""
        lines = []
        
        # Intent details
        lines.append(f"Origin: {intent.get('from', 'Unknown')}")
        lines.append(f"Destination: {intent.get('to', 'Unknown')}")
        lines.append(f"Date: {intent.get('date', 'Unknown')}")
        lines.append(f"Services: {', '.join(intent.get('needs', []))}")
        lines.append("")
        
        total_cost = 0
        
        for key, value in results.items():
            lines.append(f"--- {key} ---")
            
            if isinstance(value, dict):
                if 'error' in value:
                    lines.append(f"Error: {value['error']}")
                else:
                    for k, v in value.items():
                        if k in ['total_price', 'price', 'total_cost']:
                            if isinstance(v, (int, float)):
                                total_cost = max(total_cost, v)  # Use highest (itinerary total)
                        # Flatten nested dicts for key-value display
                        if isinstance(v, dict):
                            for nested_k, nested_v in v.items():
                                if not isinstance(nested_v, (dict, list)):
                                    lines.append(f"{k}.{nested_k}: {nested_v}")
                        elif isinstance(v, list):
                            lines.append(f"{k}: [{len(v)} items]")
                        else:
                            lines.append(f"{k}: {v}")
            elif isinstance(value, list):
                lines.append(f"Results: {len(value)} items found")
                for i, item in enumerate(value[:3], 1):
                    if isinstance(item, dict):
                        summary = item.get('name', item.get('airline', item.get('id', f'Item {i}')))
                        price = item.get('price', '')
                        lines.append(f"  Option {i}: {summary}" + (f" (${price})" if price else ""))
            else:
                lines.append(f"Result: {value}")
            lines.append("")
        
        if total_cost > 0:
            lines.append(f"Total Cost: ${total_cost}")
        
        return "\n".join(lines)
    
    def _format_structured(self, results: Dict[str, Any], intent: Dict[str, Any]) -> str:
        """Format results as structured text with sections"""
        lines = []
        lines.append("=" * 50)
        lines.append("TRAVEL BOOKING SUMMARY")
        lines.append("=" * 50)
        
        origin = intent.get('from', 'Unknown')
        destination = intent.get('to', 'Unknown')
        date = intent.get('date', 'Unknown')
        
        lines.append(f"\nTrip: {origin} to {destination}")
        lines.append(f"Date: {date}")
        lines.append("")
        
        total_cost = 0
        
        for key, value in results.items():
            agent_task = key.replace(".", " - ")
            lines.append(f"{agent_task}:")
            
            if isinstance(value, dict):
                if 'error' in value:
                    lines.append(f"  Error: {value['error']}")
                else:
                    for k, v in value.items():
                        if k in ['total_price', 'price', 'total_cost']:
                            if isinstance(v, (int, float)):
                                total_cost = max(total_cost, v)
                        if not isinstance(v, (dict, list)):
                            lines.append(f"  {k}: {v}")
            elif isinstance(value, list):
                for i, item in enumerate(value[:3], 1):
                    if isinstance(item, dict):
                        name = item.get('name', item.get('airline', f'Option {i}'))
                        price = item.get('price', 'N/A')
                        lines.append(f"  {i}. {name} - ${price}")
            else:
                lines.append(f"  {value}")
            lines.append("")
        
        if total_cost > 0:
            lines.append(f"Estimated Total: ${total_cost}")
        
        lines.append("=" * 50)
        
        return "\n".join(lines)
    
    def _render_template(self, json_data: Dict[str, Any]) -> str:
        """
        Render JSON summary fields into natural language using template.
        
        This method converts structured JSON fields (from LLM) into a formatted
        natural language summary. This is much faster than having the LLM generate
        full prose (Phase 2 optimization).
        
        Args:
            json_data: Dictionary with header, flight, hotel, car, total_cost, closing
            
        Returns:
            Formatted natural language summary
        """
        header = json_data.get("header", "")
        flight = json_data.get("flight", "Flight information unavailable")
        hotel = json_data.get("hotel", "Hotel information unavailable")
        car = json_data.get("car", "No car booked")
        total_cost = json_data.get("total_cost", 0)
        closing = json_data.get("closing", "")
        
        # Format total cost with currency
        if isinstance(total_cost, (int, float)) and total_cost > 0:
            cost_str = f"${total_cost:.2f}"
        else:
            cost_str = str(total_cost) if total_cost else "N/A"
        
        # Build summary with template
        summary_parts = []
        
        if header:
            summary_parts.append(header)
            summary_parts.append("")  # Blank line
        
        if flight:
            summary_parts.append(f"Flight: {flight}")
        
        if hotel:
            summary_parts.append(f"Hotel: {hotel}")
        
        if car:
            summary_parts.append(f"Car: {car}")
        
        if total_cost and isinstance(total_cost, (int, float)) and total_cost > 0:
            summary_parts.append("")  # Blank line
            summary_parts.append(f"Total Estimated Cost: {cost_str}")
        
        if closing:
            summary_parts.append("")  # Blank line
            summary_parts.append(closing)
        
        return "\n".join(summary_parts)
    
    def _format_json(self, results: Dict[str, Any], intent: Dict[str, Any]) -> str:
        """Format results as JSON"""
        output = {
            "intent": intent,
            "results": results
        }
        return json.dumps(output, indent=2, default=str)


def format_travel_results(results: Dict[str, Any], intent: Dict[str, Any], 
                          llm: Optional[LLMProvider] = None,
                          output_format: OutputFormat = "key_value") -> str:
    """
    Convenience function to format travel results
    
    Args:
        results: Dictionary of agent results
        intent: Original user intent
        llm: Optional LLM provider (if None, uses fallback formatting)
        output_format: Format to use when LLM is not available
                      - "key_value": Simple key: value pairs (default)
                      - "structured": Formatted text with sections
                      - "json": Raw JSON output
    
    Returns:
        Formatted string summary
    """
    formatter = ResponseFormatter(llm=llm, output_format=output_format)
    return formatter.format_results(results, intent)
