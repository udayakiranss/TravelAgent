# hotel_booking_agent.py
# Hotel booking agent with multiple tools
from typing import Dict, Any, Optional, TYPE_CHECKING
from langchain.tools import tool
from agents.core.base_agent import BaseAgent
from data.hotels import HOTELS
from utils.logger import get_logger

if TYPE_CHECKING:
    from api.context import TravelContext

logger = get_logger()


@tool
def search_hotels_tool(query: Dict[str, Any]) -> list:
    """Search hotels by city. Returns list of available hotels."""
    # Unwrap if params are nested under 'query' key (from LangChain tool invocation)
    if 'query' in query and isinstance(query['query'], dict):
        query = query['query']
    
    logger.debug(f"Hotel search tool called with query: {query}")
    
    city = query.get('city', '')
    if not city:
        logger.warning(f"Hotel search missing required param: city")
        return []
    
    # Normalize city name to airport code format used in HOTELS data
    city = _normalize_city_code(city)
    
    results = [h for h in HOTELS if h['city'] == city]
    logger.info(f"Hotel search: {city} -> {len(results)} results")
    return results


def _normalize_city_code(city: str) -> str:
    """Normalize city name to airport code format used in HOTELS data.
    
    Maps city names to airport codes:
    - London, LONDON -> LON
    - New York, NYC, New York City -> NYC
    - San Francisco, SFO, SF -> SFO
    - Dubai, DXB -> DXB
    - Delhi, DEL -> DEL
    - Mumbai, BOM -> BOM
    """
    city = city.strip().upper()
    
    # City name mappings
    city_mappings = {
        'LONDON': 'LON',
        'NEW YORK': 'NYC',
        'NEW YORK CITY': 'NYC',
        'SAN FRANCISCO': 'SFO',
        'SF': 'SFO',
        'DUBAI': 'DXB',
        'DELHI': 'DEL',
        'MUMBAI': 'BOM',
        'BANGALORE': 'BLR',
        'BENGALURU': 'BLR',
        'CHENNAI': 'MAA',
        'HYDERABAD': 'HYD',
        'KOLKATA': 'CCU',
        'PARIS': 'PAR',
        'TOKYO': 'TYO',
        'SYDNEY': 'SYD',
    }
    
    # Check if it's already a code (3 letters) or if we have a mapping
    if len(city) == 3 and city.isalpha():
        # Already a code, return as-is
        return city
    elif city in city_mappings:
        return city_mappings[city]
    else:
        # Try to extract first 3 letters as code, or return uppercase as-is
        return city[:3] if len(city) >= 3 else city


@tool
def compare_hotels_tool(query: Dict[str, Any]) -> Dict[str, Any]:
    """Compare multiple hotels by IDs. Returns comparison with prices and details."""
    # Unwrap if params are nested under 'query' key (from LangChain tool invocation)
    if 'query' in query and isinstance(query['query'], dict):
        query = query['query']
    
    hotel_ids = query.get('hotel_ids', [])
    
    if not hotel_ids:
        return {"error": "No hotel IDs provided"}
    
    hotels = [h for h in HOTELS if h['id'] in hotel_ids]
    
    if not hotels:
        return {"error": "No hotels found for given IDs"}
    
    comparison = {
        "hotels": hotels,
        "cheapest": min(hotels, key=lambda x: x['price']),
        "most_expensive": max(hotels, key=lambda x: x['price']),
        "price_range": {
            "min": min(h['price'] for h in hotels),
            "max": max(h['price'] for h in hotels)
        }
    }
    
    logger.info(f"Compared {len(hotels)} hotels: ${comparison['price_range']['min']}-${comparison['price_range']['max']}")
    return comparison


@tool
def book_hotel_tool(query: Dict[str, Any]) -> Dict[str, Any]:
    """Book a hotel by ID. Returns booking confirmation."""
    # Unwrap if params are nested under 'query' key (from LangChain tool invocation)
    if 'query' in query and isinstance(query['query'], dict):
        query = query['query']
    
    hotel_id = query.get('hotel_id')
    guest_name = query.get('guest_name', 'Guest')
    check_in = query.get('check_in', '')
    check_out = query.get('check_out', '')
    
    if not hotel_id:
        return {"error": "Hotel ID is required"}
    
    hotel = next((h for h in HOTELS if h['id'] == hotel_id), None)
    
    if not hotel:
        return {"error": f"Hotel {hotel_id} not found"}
    
    booking = {
        "status": "confirmed",
        "booking_id": f"HTL-{hotel_id}-{guest_name[:3].upper()}",
        "hotel": hotel,
        "guest": guest_name,
        "check_in": check_in,
        "check_out": check_out,
        "total_price": hotel['price']
    }
    
    logger.info(f"Hotel booked: {booking['booking_id']} for ${hotel['price']}")
    return booking


class HotelBookingAgent(BaseAgent):
    """Agent specialized in hotel booking operations"""
    
    def __init__(self, llm=None):
        super().__init__(llm=llm, name="HotelBookingAgent")
    
    def _initialize_tools(self) -> Dict[str, Any]:
        """Initialize hotel booking tools"""
        return {
            'search_hotels': search_hotels_tool,
            'compare_hotels': compare_hotels_tool,
            'book_hotel': book_hotel_tool,
        }
    
    def search_with_selection(
        self, 
        params: Dict[str, Any], 
        ctx: "TravelContext"
    ) -> Dict[str, Any]:
        """Search for hotels and return the best option based on context criteria."""
        try:
            all_hotels = self._call_tool('search_hotels', params)
        except Exception as e:
            logger.error(f"Hotel search failed: {e}")
            return {"reservation": None, "options": [], "error": str(e)}
        
        # Handle error case (dict with error key)
        if isinstance(all_hotels, dict) and "error" in all_hotels:
            return {"reservation": None, "options": [], "error": all_hotels["error"]}
        
        # Ensure all_hotels is a list
        if not isinstance(all_hotels, list):
            logger.warning(f"Hotel search returned non-list result: {type(all_hotels)}")
            all_hotels = []
        
        if not all_hotels:
            logger.warning(f"No hotels found for params: {params}")
            return {"reservation": None, "options": []}
        
        selected = self._select_best(all_hotels, ctx.criteria)
        return {
            "reservation": selected,
            "options": all_hotels
        }
    
    def execute(self, task: str, params: Dict[str, Any], ctx: Optional["TravelContext"] = None) -> Any:
        """Execute hotel booking task"""
        if task == 'search_hotels' and ctx is not None:
            return self.search_with_selection(params, ctx)
        
        if task in self.tools:
            return self._call_tool(task, params)
        
        if self.llm:
            return self._llm_route_task(task, params)
        
        logger.warning(f"Unknown task '{task}' for {self.name}")
        return {"error": f"Unknown task '{task}' for {self.name}"}
    
    def _llm_route_task(self, task: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Use LLM to route ambiguous tasks to appropriate tools"""
        available_tools = ", ".join(self.get_available_tools())
        prompt = f"""You are a Hotel Booking Agent. Based on the task and parameters, determine which tool to use.

Available tools: {available_tools}
Task: {task}
Parameters: {params}

Respond with only the tool name to use."""
        
        tool_name = self.llm.invoke(prompt).strip()
        logger.debug(f"LLM routed task '{task}' -> tool '{tool_name}'")
        
        if tool_name in self.tools:
            return self._call_tool(tool_name, params)
        
        logger.warning(f"LLM suggested unknown tool '{tool_name}'")
        return {"error": f"LLM suggested unknown tool '{tool_name}'"}
