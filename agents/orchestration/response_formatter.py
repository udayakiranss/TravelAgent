# response_formatter.py
# LLM-powered formatter that converts JSON agent results to natural language
from typing import Dict, Any, Optional, Literal
import json
from agents.core.llm_provider import LLMProvider
from utils.logger import get_logger, log_method_entry_exit

logger = get_logger()

# Supported output formats when LLM is not available
OutputFormat = Literal["key_value", "structured", "json"]


class ResponseFormatter:
    """Formats agent results into natural language summaries using LLM"""
    
    def __init__(self, llm: Optional[LLMProvider] = None, output_format: OutputFormat = "key_value"):
        """
        Initialize the response formatter
        
        Args:
            llm: LLM provider for generating natural language (optional)
            output_format: Format to use when LLM is not available
                          - "key_value": Simple key: value pairs (default)
                          - "structured": Formatted text with sections
                          - "json": Raw JSON output
        """
        self.llm = llm
        self.output_format = output_format
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
            # Generate natural language summary
            summary = self.llm.invoke(prompt)
            logger.info("Successfully generated natural language summary")
            return summary.strip()
        except Exception as e:
            logger.error(f"Failed to generate natural language summary: {e}", exc_info=True)
            # Return a basic fallback summary
            return self._fallback_format(results, intent)
    
    def _build_prompt(self, results: Dict[str, Any], intent: Dict[str, Any]) -> str:
        """Build the LLM prompt for formatting results"""
        
        # Extract key information from intent
        origin = intent.get('from', 'Unknown')
        destination = intent.get('to', 'Unknown')
        date = intent.get('date', 'Unknown')
        needs = intent.get('needs', [])
        
        # Serialize results for the prompt
        results_json = json.dumps(results, indent=2, default=str)
        
        prompt = f"""You are a friendly travel assistant. Convert the following booking results into a warm, conversational summary for the traveler.

**Travel Request:**
- Origin: {origin}
- Destination: {destination}
- Travel Date: {date}
- Services Requested: {', '.join(needs) if needs else 'Not specified'}

**Booking Results (JSON):**
{results_json}

**Instructions:**
1. Create a friendly, well-formatted summary of the travel booking
2. Start with a welcoming header mentioning the destination
3. For each booking (flight, hotel, car, itinerary), provide key details in a readable format:
   - Flight: airline, departure/arrival times, duration, price
   - Hotel: name, location, price per night, rating if available
   - Car: vehicle type, rental company, daily rate
   - Itinerary: summary of all bookings and total cost
4. If any booking failed or has an error, mention it politely and suggest alternatives
5. End with the total estimated cost and a friendly closing message
6. Use natural dates (e.g., "April 1st" instead of "2026-04-01")
7. Format prices with currency symbols (e.g., "$350")
8. Keep the response concise but informative (around 150-250 words)
9. Do NOT use markdown formatting or special characters - use plain text with simple line breaks

Generate the natural language summary:"""

        logger.debug(f"Built prompt with {len(prompt)} characters")
        return prompt
    
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
