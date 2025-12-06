# itinerary_agent.py
# Itinerary management agent with multiple tools
from typing import Dict, Any, List
from langchain.tools import tool
from agents.base_agent import BaseAgent
from utils.logger import get_logger, log_method_entry_exit

logger = get_logger()


# In-memory storage for itineraries (in production, use a database)
_ITINERARIES = {}


@tool
def build_itinerary_tool(query: Dict[str, Any]) -> Dict[str, Any]:
    """Build a new itinerary from flight, hotel, and car bookings. Returns itinerary details."""
    itinerary_id = query.get('itinerary_id', f"ITIN-{len(_ITINERARIES) + 1}")
    flight_booking = query.get('flight_booking')
    hotel_booking = query.get('hotel_booking')
    car_booking = query.get('car_booking')
    traveler_name = query.get('traveler_name', 'Guest')
    
    logger.debug(f"Building itinerary: id={itinerary_id}, traveler={traveler_name}, has_flight={flight_booking is not None}, has_hotel={hotel_booking is not None}, has_car={car_booking is not None}")
    
    itinerary = {
        "itinerary_id": itinerary_id,
        "traveler": traveler_name,
        "flight": flight_booking,
        "hotel": hotel_booking,
        "car": car_booking,
        "total_cost": 0,
        "status": "draft"
    }
    
    # Calculate total cost
    if flight_booking and isinstance(flight_booking, dict):
        itinerary["total_cost"] += flight_booking.get('total_price', flight_booking.get('price', 0))
    if hotel_booking and isinstance(hotel_booking, dict):
        itinerary["total_cost"] += hotel_booking.get('total_price', hotel_booking.get('price', 0))
    if car_booking and isinstance(car_booking, dict):
        itinerary["total_cost"] += car_booking.get('total_price', car_booking.get('price', 0))
    
    _ITINERARIES[itinerary_id] = itinerary
    
    logger.info(f"Itinerary built: {itinerary_id}, total_cost=${itinerary['total_cost']}")
    return itinerary


@tool
def update_itinerary_tool(query: Dict[str, Any]) -> Dict[str, Any]:
    """Update an existing itinerary. Returns updated itinerary."""
    itinerary_id = query.get('itinerary_id')
    
    logger.debug(f"Updating itinerary: id={itinerary_id}")
    
    if not itinerary_id:
        logger.warning("Itinerary ID is required for update")
        return {"error": "Itinerary ID is required"}
    
    if itinerary_id not in _ITINERARIES:
        logger.warning(f"Itinerary {itinerary_id} not found")
        return {"error": f"Itinerary {itinerary_id} not found"}
    
    itinerary = _ITINERARIES[itinerary_id]
    
    # Update fields
    updates = []
    if 'flight_booking' in query:
        itinerary['flight'] = query['flight_booking']
        updates.append('flight')
    if 'hotel_booking' in query:
        itinerary['hotel'] = query['hotel_booking']
        updates.append('hotel')
    if 'car_booking' in query:
        itinerary['car'] = query['car_booking']
        updates.append('car')
    if 'status' in query:
        itinerary['status'] = query['status']
        updates.append('status')
    
    logger.debug(f"Updated fields: {updates}")
    
    # Recalculate total cost
    itinerary['total_cost'] = 0
    if itinerary.get('flight') and isinstance(itinerary['flight'], dict):
        itinerary['total_cost'] += itinerary['flight'].get('total_price', itinerary['flight'].get('price', 0))
    if itinerary.get('hotel') and isinstance(itinerary['hotel'], dict):
        itinerary['total_cost'] += itinerary['hotel'].get('total_price', itinerary['hotel'].get('price', 0))
    if itinerary.get('car') and isinstance(itinerary['car'], dict):
        itinerary['total_cost'] += itinerary['car'].get('total_price', itinerary['car'].get('price', 0))
    
    logger.info(f"Itinerary updated: {itinerary_id}, new_total_cost=${itinerary['total_cost']}")
    return itinerary


@tool
def get_itinerary_tool(query: Dict[str, Any]) -> Dict[str, Any]:
    """Get itinerary details by ID. Returns itinerary information."""
    itinerary_id = query.get('itinerary_id')
    
    logger.debug(f"Getting itinerary: id={itinerary_id}")
    
    if not itinerary_id:
        logger.warning("Itinerary ID is required")
        return {"error": "Itinerary ID is required"}
    
    if itinerary_id not in _ITINERARIES:
        logger.warning(f"Itinerary {itinerary_id} not found")
        return {"error": f"Itinerary {itinerary_id} not found"}
    
    itinerary = _ITINERARIES[itinerary_id]
    logger.debug(f"Retrieved itinerary {itinerary_id} for traveler {itinerary.get('traveler', 'Unknown')}")
    return itinerary


@tool
def list_itineraries_tool(query: Dict[str, Any]) -> List[Dict[str, Any]]:
    """List all itineraries. Returns list of itinerary summaries."""
    traveler_name = query.get('traveler_name')
    
    logger.debug(f"Listing itineraries: traveler_filter={traveler_name or 'all'}")
    
    if traveler_name:
        # Filter by traveler name
        filtered = [
            {k: v for k, v in it.items() if k != 'flight' and k != 'hotel' and k != 'car'}
            for it in _ITINERARIES.values()
            if it.get('traveler') == traveler_name
        ]
        logger.info(f"Found {len(filtered)} itineraries for traveler {traveler_name}")
        return filtered
    else:
        # Return all itinerary summaries
        all_itineraries = [
            {k: v for k, v in it.items() if k != 'flight' and k != 'hotel' and k != 'car'}
            for it in _ITINERARIES.values()
        ]
        logger.info(f"Found {len(all_itineraries)} total itineraries")
        return all_itineraries


class ItineraryAgent(BaseAgent):
    """Agent specialized in itinerary management"""
    
    def __init__(self, llm=None):
        super().__init__(llm=llm, name="ItineraryAgent")
    
    def _initialize_tools(self) -> Dict[str, Any]:
        """Initialize itinerary management tools"""
        return {
            'build_itinerary': build_itinerary_tool,
            'update_itinerary': update_itinerary_tool,
            'get_itinerary': get_itinerary_tool,
            'list_itineraries': list_itineraries_tool,
        }
    
    @log_method_entry_exit(level="DEBUG")
    def execute(self, task: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute itinerary management task"""
        logger.debug(f"ItineraryAgent executing task: {task} with params: {params}")
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
                logger.warning(f"Unknown task '{task}' for ItineraryAgent and no LLM available")
                return {"error": f"Unknown task '{task}' for ItineraryAgent"}
    
    @log_method_entry_exit(level="DEBUG")
    def _llm_route_task(self, task: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Use LLM to route ambiguous tasks to appropriate tools"""
        available_tools = ", ".join(self.get_available_tools())
        prompt = f"""You are an Itinerary Management Agent. Based on the task and parameters, determine which tool to use.

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

