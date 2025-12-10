"""
User Preferences Tool for LLM Tool Calling.

This tool enables the model to load full user preferences on-demand,
following a tiered loading pattern:
- Summary (~50 tokens) is always included in prompts
- Full details (~500 tokens) are loaded via this tool when needed

The tool reads from filesystem cache for minimal latency during LLM execution.
"""
from typing import Dict, Any
from pathlib import Path
import json

from langchain.tools import tool

from utils.logger import get_logger

logger = get_logger()

# Cache directory path
CACHE_DIR = Path(__file__).parent.parent / "data" / "user_preferences"


@tool
def load_full_preferences(traveler_id: str) -> Dict[str, Any]:
    """Load complete user preferences for personalized travel recommendations.
    
    Call this tool when you need detailed information such as:
    - Specific dietary restrictions or food allergies
    - Loyalty program numbers and membership tiers
    - Past booking patterns and preferred destinations
    - Accessibility requirements and special needs
    - Preferred airlines, hotel chains, or car rental companies
    
    For basic preferences (seat type, budget range, hotel star rating), 
    use the summary already provided in the context - no need to call this tool.
    
    Args:
        traveler_id: The unique identifier for the traveler (e.g., "user_123")
    
    Returns:
        Complete preferences dictionary including:
        - flight_preferences: seat type, cabin class, airline preferences
        - hotel_preferences: rating, room type, amenities, chains
        - car_preferences: car type, features, companies
        - budget_range: min/max budget and currency
        - dietary_restrictions: list of dietary needs
        - accessibility_needs: list of accessibility requirements
        - loyalty_programs: list of program memberships with tiers
        - past_bookings_summary: aggregated booking history stats
    """
    logger.info(f"Tool call: load_full_preferences(traveler_id={traveler_id})")
    
    cache_path = CACHE_DIR / f"{traveler_id}.json"
    
    if cache_path.exists():
        with open(cache_path) as f:
            preferences = json.load(f)
        logger.debug(f"Preferences loaded from cache: {cache_path}")
        return preferences
    
    # If not in cache, return empty preferences with message
    logger.warning(f"No preferences found for traveler_id={traveler_id}")
    return {
        "traveler_id": traveler_id,
        "error": "No preferences found for this traveler",
        "flight_preferences": None,
        "hotel_preferences": None,
        "car_preferences": None,
        "budget_range": None,
        "dietary_restrictions": None,
        "accessibility_needs": None,
        "loyalty_programs": None,
        "past_bookings_summary": None,
    }


# Export for easy importing
__all__ = ["load_full_preferences"]
