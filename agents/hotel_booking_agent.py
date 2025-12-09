# hotel_booking_agent.py
# Hotel booking agent with multiple tools
from typing import Dict, Any, Optional, TYPE_CHECKING
from langchain.tools import tool
from agents.base_agent import BaseAgent
from data.hotels import HOTELS
from utils.logger import get_logger

if TYPE_CHECKING:
    from api.context import TravelContext

logger = get_logger()


@tool
def search_hotels_tool(query: Dict[str, Any]) -> list:
    """Search hotels by city. Returns list of available hotels."""
    city = query.get('city', '').upper()
    results = [h for h in HOTELS if h['city'] == city]
    logger.info(f"Hotel search: {city} -> {len(results)} results")
    return results


@tool
def compare_hotels_tool(query: Dict[str, Any]) -> Dict[str, Any]:
    """Compare multiple hotels by IDs. Returns comparison with prices and details."""
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
    ) -> Optional[Dict[str, Any]]:
        """Search for hotels and return the best option based on context criteria."""
        all_hotels = self._call_tool('search_hotels', params)
        
        if not all_hotels or isinstance(all_hotels, dict) and "error" in all_hotels:
            return None
        
        return self._select_best(all_hotels, ctx.criteria)
    
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
