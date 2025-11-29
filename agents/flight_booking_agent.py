# flight_booking_agent.py
# Flight booking agent with multiple tools
from typing import Dict, Any
from langchain.tools import tool
from agents.base_agent import BaseAgent
from data.flights import FLIGHTS


@tool
def search_flights_tool(query: Dict[str, Any]) -> list:
    """Search flights by origin, destination, and date. Returns list of available flights."""
    frm = query.get('from', '').upper()
    to = query.get('to', '').upper()
    date = query.get('date', '')
    
    results = [
        f for f in FLIGHTS 
        if f['from'] == frm and f['to'] == to and f['date'] == date
    ]
    return results


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
    
    def execute(self, task: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute flight booking task"""
        if task in self.tools:
            return self._call_tool(task, params)
        else:
            # Use LLM to determine which tool to use if task is ambiguous
            if self.llm:
                return self._llm_route_task(task, params)
            else:
                return {"error": f"Unknown task '{task}' for FlightBookingAgent"}
    
    def _llm_route_task(self, task: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Use LLM to route ambiguous tasks to appropriate tools"""
        available_tools = ", ".join(self.get_available_tools())
        prompt = f"""You are a Flight Booking Agent. Based on the task and parameters, determine which tool to use.

Available tools: {available_tools}
Task: {task}
Parameters: {params}

Respond with only the tool name to use."""
        
        tool_name = self.llm.invoke(prompt).strip()
        
        if tool_name in self.tools:
            return self._call_tool(tool_name, params)
        else:
            return {"error": f"LLM suggested unknown tool '{tool_name}'"}

