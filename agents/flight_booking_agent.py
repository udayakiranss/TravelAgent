# flight_booking_agent.py
# Flight booking agent with multiple tools
from typing import Dict, Any
from langchain.tools import tool
from agents.base_agent import BaseAgent
from data.flights import FLIGHTS
from utils.logger import get_logger, log_method_entry_exit

logger = get_logger()


@tool
def search_flights_tool(query: Dict[str, Any]) -> list:
    """Search flights by origin, destination, and date. Returns list of available flights."""
    frm = query.get('from', '').upper()
    to = query.get('to', '').upper()
    date = query.get('date', '')
    
    logger.debug(f"Searching flights: from={frm}, to={to}, date={date}")
    
    results = [
        f for f in FLIGHTS 
        if f['from'] == frm and f['to'] == to and f['date'] == date
    ]
    
    logger.info(f"Found {len(results)} flights matching criteria")
    return results


@tool
def compare_flights_tool(query: Dict[str, Any]) -> Dict[str, Any]:
    """Compare multiple flights by IDs. Returns comparison with prices and details."""
    flight_ids = query.get('flight_ids', [])
    
    logger.debug(f"Comparing flights with IDs: {flight_ids}")
    
    if not flight_ids:
        logger.warning("No flight IDs provided for comparison")
        return {"error": "No flight IDs provided"}
    
    flights = [f for f in FLIGHTS if f['id'] in flight_ids]
    
    if not flights:
        logger.warning(f"No flights found for given IDs: {flight_ids}")
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
    
    logger.info(f"Compared {len(flights)} flights, price range: ${comparison['price_range']['min']}-${comparison['price_range']['max']}")
    return comparison


@tool
def book_flight_tool(query: Dict[str, Any]) -> Dict[str, Any]:
    """Book a flight by ID. Returns booking confirmation."""
    flight_id = query.get('flight_id')
    passenger_name = query.get('passenger_name', 'Guest')
    
    logger.debug(f"Booking flight: flight_id={flight_id}, passenger={passenger_name}")
    
    if not flight_id:
        logger.warning("Flight ID is required for booking")
        return {"error": "Flight ID is required"}
    
    flight = next((f for f in FLIGHTS if f['id'] == flight_id), None)
    
    if not flight:
        logger.warning(f"Flight {flight_id} not found")
        return {"error": f"Flight {flight_id} not found"}
    
    booking = {
        "status": "confirmed",
        "booking_id": f"BK-{flight_id}-{passenger_name[:3].upper()}",
        "flight": flight,
        "passenger": passenger_name,
        "total_price": flight['price']
    }
    
    logger.info(f"Flight booking confirmed: {booking['booking_id']}, price: ${flight['price']}")
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
    
    @log_method_entry_exit(level="DEBUG")
    def execute(self, task: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute flight booking task"""
        logger.debug(f"FlightBookingAgent executing task: {task} with params: {params}")
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
                logger.warning(f"Unknown task '{task}' for FlightBookingAgent and no LLM available")
                return {"error": f"Unknown task '{task}' for FlightBookingAgent"}
    
    @log_method_entry_exit(level="DEBUG")
    def _llm_route_task(self, task: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Use LLM to route ambiguous tasks to appropriate tools"""
        available_tools = ", ".join(self.get_available_tools())
        prompt = f"""You are a Flight Booking Agent. Based on the task and parameters, determine which tool to use.

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

