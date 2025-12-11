# flight_booking_agent.py
# Flight booking agent with multiple tools
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from langchain.tools import tool
from agents.core.base_agent import BaseAgent
from data.flights import FLIGHTS
from utils.logger import get_logger, log_method_entry_exit

if TYPE_CHECKING:
    from api.context import TravelContext

logger = get_logger()


@tool
def search_flights_tool(query: Dict[str, Any]) -> list:
    """Search flights by origin, destination, and date. Returns list of available flights."""
    # Unwrap if params are nested under 'query' key (from LangChain tool invocation)
    if 'query' in query and isinstance(query['query'], dict):
        query = query['query']
    
    logger.debug(f"Flight search tool called with query: {query}")
    
    # Handle multiple parameter name variations
    origin = query.get('origin') or query.get('from') or ''
    destination = query.get('destination') or query.get('to') or ''
    # Handle date variations: 'date', 'departure_date', 'departureDate'
    date = query.get('date') or query.get('departure_date') or query.get('departureDate') or ''

    if not origin or not destination:
        logger.warning(f"Flight search missing required params: origin={origin}, destination={destination}")
        return []

    origin = origin.upper()
    destination = destination.upper()
    
    # Normalize airport codes (e.g., JFK/LGA/EWR -> NYC, LHR/LGW -> LON)
    origin = _normalize_airport_code(origin)
    destination = _normalize_airport_code(destination)
    
    # If date is provided, filter by date; otherwise return all matching routes
    if date:
        results = [
            f for f in FLIGHTS 
            if f['from'] == origin and f['to'] == destination and f['date'] == date
        ]
    else:
        # If no date, return all flights for the route
        results = [
            f for f in FLIGHTS 
            if f['from'] == origin and f['to'] == destination
        ]
        logger.info(f"Flight search: {origin}->{destination} (no date filter) -> {len(results)} results")
    
    logger.info(f"Flight search: {origin}->{destination} on {date or 'any date'} -> {len(results)} results")
    return results


def _normalize_airport_code(code: str) -> str:
    """Normalize airport codes to match flight data.
    
    Maps specific airport codes to city codes used in FLIGHTS data:
    - JFK, LGA, EWR -> NYC
    - LHR, LGW, STN, LCY, LTN -> LON
    - CDG, ORY -> PAR
    """
    code = code.upper()
    # NYC area airports
    if code in ['JFK', 'LGA', 'EWR']:
        return 'NYC'
    # London area airports
    if code in ['LHR', 'LGW', 'STN', 'LCY', 'LTN']:
        return 'LON'
    # Paris area airports
    if code in ['CDG', 'ORY']:
        return 'PAR'
    # Return as-is if no mapping found
    return code


@tool
def compare_flights_tool(query: Dict[str, Any]) -> Dict[str, Any]:
    """Compare multiple flights by IDs. Returns comparison with prices and details."""
    flight_ids = query.get('flight_ids', [])
    
    if not flight_ids:
        return {"error": "No flight IDs provided"}
    
    flights = [f for f in FLIGHTS if f['id'] in flight_ids]
    
    if not flights:
        return {"error": "No flights found for given IDs"}
    
    comparison = {
        "flights": flights,
        "cheapest": min(flights, key=lambda x: x['price']),
        "most_expensive": max(flights, key=lambda x: x['price']),
        "price_range": {
            "min": min(f['price'] for f in flights),
            "max": max(f['price'] for f in flights)
        }
    }
    
    logger.info(f"Compared {len(flights)} flights: ${comparison['price_range']['min']}-${comparison['price_range']['max']}")
    return comparison


@tool
def book_flight_tool(query: Dict[str, Any]) -> Dict[str, Any]:
    """Book a flight by ID. Returns booking confirmation."""
    flight_id = query.get('flight_id')
    passenger_name = query.get('passenger_name', 'Guest')
    
    if not flight_id:
        return {"error": "Flight ID is required"}
    
    flight = next((f for f in FLIGHTS if f['id'] == flight_id), None)
    
    if not flight:
        return {"error": f"Flight {flight_id} not found"}
    
    booking = {
        "status": "confirmed",
        "booking_id": f"BK-{flight_id}-{passenger_name[:3].upper()}",
        "flight": flight,
        "passenger": passenger_name,
        "total_price": flight['price']
    }
    
    logger.info(f"Flight booked: {booking['booking_id']} for ${flight['price']}")
    return booking


class FlightBookingAgent(BaseAgent):
    """Agent specialized in flight booking operations"""
    
    def __init__(self, llm=None):
        super().__init__(llm=llm, name="FlightBookingAgent")
    
    def _initialize_tools(self) -> Dict[str, Any]:
        """Initialize flight booking tools"""
        return {
            'search_flights': search_flights_tool,
            'compare_flights': compare_flights_tool,
            'book_flight': book_flight_tool,
        }
    
    def search_with_selection(
        self, 
        params: Dict[str, Any], 
        ctx: "TravelContext"
    ) -> Dict[str, Any]:
        """
        Search for flights and return the best option based on context criteria.
        Returns dict with keys 'reservation' and 'options'.
        """
        try:
            all_flights = self._call_tool('search_flights', params)
        except Exception as e:
            logger.error(f"Flight search failed: {e}")
            return {"reservation": None, "options": [], "error": str(e)}
        
        # Handle error case (dict with error key)
        if isinstance(all_flights, dict) and "error" in all_flights:
            return {"reservation": None, "options": [], "error": all_flights["error"]}
        
        # Ensure all_flights is a list
        if not isinstance(all_flights, list):
            logger.warning(f"Flight search returned non-list result: {type(all_flights)}")
            all_flights = []
        
        if not all_flights:
            logger.warning(f"No flights found for params: {params}")
            return {"reservation": None, "options": []}

        selected = self._select_best(all_flights, ctx.criteria)
        
        if selected:
            # Convert to reservation format
            reservation = {
                **selected,
                "origin": selected.get("from", selected.get("origin")),
                "destination": selected.get("to", selected.get("destination")),
            }
        else:
            reservation = None
        
        return {
            "reservation": reservation,
            "options": all_flights
        }
    
    def execute(self, task: str, params: Dict[str, Any], ctx: Optional["TravelContext"] = None) -> Any:
        """Execute flight booking task"""
        # Handle context-aware search
        if task == 'search_flights' and ctx is not None:
            return self.search_with_selection(params, ctx)
        
        if task in self.tools:
            return self._call_tool(task, params)
        
        # Use LLM to determine which tool to use if task is ambiguous
        if self.llm:
            return self._llm_route_task(task, params)
        
        logger.warning(f"Unknown task '{task}' for {self.name}")
        return {"error": f"Unknown task '{task}' for {self.name}"}
    
    def _llm_route_task(self, task: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Use LLM to route ambiguous tasks to appropriate tools"""
        available_tools = ", ".join(self.get_available_tools())
        prompt = f"""You are a Flight Booking Agent. Based on the task and parameters, determine which tool to use.

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

