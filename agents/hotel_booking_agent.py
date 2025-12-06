# hotel_booking_agent.py
# Hotel booking agent with multiple tools
from typing import Dict, Any
from langchain.tools import tool
from agents.base_agent import BaseAgent
from data.hotels import HOTELS
from utils.logger import get_logger, log_method_entry_exit

logger = get_logger()


@tool
def search_hotels_tool(query: Dict[str, Any]) -> list:
    """Search hotels by city. Returns list of available hotels."""
    city = query.get('city', '').upper()
    
    logger.debug(f"Searching hotels in city: {city}")
    
    results = [h for h in HOTELS if h['city'] == city]
    
    logger.info(f"Found {len(results)} hotels in {city}")
    return results


@tool
def compare_hotels_tool(query: Dict[str, Any]) -> Dict[str, Any]:
    """Compare multiple hotels by IDs. Returns comparison with prices and details."""
    hotel_ids = query.get('hotel_ids', [])
    
    logger.debug(f"Comparing hotels with IDs: {hotel_ids}")
    
    if not hotel_ids:
        logger.warning("No hotel IDs provided for comparison")
        return {"error": "No hotel IDs provided"}
    
    hotels = [h for h in HOTELS if h['id'] in hotel_ids]
    
    if not hotels:
        logger.warning(f"No hotels found for given IDs: {hotel_ids}")
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
    
    logger.info(f"Compared {len(hotels)} hotels, price range: ${comparison['price_range']['min']}-${comparison['price_range']['max']}")
    return comparison


@tool
def book_hotel_tool(query: Dict[str, Any]) -> Dict[str, Any]:
    """Book a hotel by ID. Returns booking confirmation."""
    hotel_id = query.get('hotel_id')
    guest_name = query.get('guest_name', 'Guest')
    check_in = query.get('check_in', '')
    check_out = query.get('check_out', '')
    
    logger.debug(f"Booking hotel: hotel_id={hotel_id}, guest={guest_name}, check_in={check_in}, check_out={check_out}")
    
    if not hotel_id:
        logger.warning("Hotel ID is required for booking")
        return {"error": "Hotel ID is required"}
    
    hotel = next((h for h in HOTELS if h['id'] == hotel_id), None)
    
    if not hotel:
        logger.warning(f"Hotel {hotel_id} not found")
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
    
    logger.info(f"Hotel booking confirmed: {booking['booking_id']}, price: ${hotel['price']}")
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
    
    @log_method_entry_exit(level="DEBUG")
    def execute(self, task: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute hotel booking task"""
        logger.debug(f"HotelBookingAgent executing task: {task} with params: {params}")
        if task in self.tools:
            result = self._call_tool(task, params)
            logger.debug(f"Task '{task}' completed successfully")
            return result
        else:
            # Use LLM to determine which tool to use if task is ambiguous
            if self.llm:
                logger.debug(f"Task '{task}' not found in tools, using LLM routing")
                return self._llm_route_task(task, params)
            else:
                logger.warning(f"Unknown task '{task}' for HotelBookingAgent and no LLM available")
                return {"error": f"Unknown task '{task}' for HotelBookingAgent"}
    
    @log_method_entry_exit(level="DEBUG")
    def _llm_route_task(self, task: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Use LLM to route ambiguous tasks to appropriate tools"""
        available_tools = ", ".join(self.get_available_tools())
        prompt = f"""You are a Hotel Booking Agent. Based on the task and parameters, determine which tool to use.

Available tools: {available_tools}
Task: {task}
Parameters: {params}

Respond with only the tool name to use."""
        
        logger.debug(f"Using LLM to route task '{task}' to appropriate tool")
        tool_name = self.llm.invoke(prompt).strip()
        logger.debug(f"LLM suggested tool: {tool_name}")
        
        if tool_name in self.tools:
            return self._call_tool(tool_name, params)
        else:
            logger.warning(f"LLM suggested unknown tool '{tool_name}'")
            return {"error": f"LLM suggested unknown tool '{tool_name}'"}

