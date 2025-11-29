# car_rental_agent.py
# Car rental agent with multiple tools
from typing import Dict, Any
from langchain.tools import tool
from agents.base_agent import BaseAgent
from data.cars import CARS


@tool
def search_cars_tool(query: Dict[str, Any]) -> list:
    """Search rental cars by city. Returns list of available cars."""
    city = query.get('city', '')
    if city:
        city = city.upper()
    
    if not city:
        return []
    
    results = [c for c in CARS if c['city'] == city]
    return results


@tool
def compare_cars_tool(query: Dict[str, Any]) -> Dict[str, Any]:
    """Compare multiple rental cars by IDs. Returns comparison with prices and details."""
    car_ids = query.get('car_ids', [])
    
    if not car_ids:
        return {"error": "No car IDs provided"}
    
    cars = [c for c in CARS if c['id'] in car_ids]
    
    if not cars:
        return {"error": "No cars found for given IDs"}
    
    comparison = {
        "cars": cars,
        "cheapest": min(cars, key=lambda x: x['price']),
        "most_expensive": max(cars, key=lambda x: x['price']),
        "price_range": {
            "min": min(c['price'] for c in cars),
            "max": max(c['price'] for c in cars)
        }
    }
    return comparison


@tool
def book_car_tool(query: Dict[str, Any]) -> Dict[str, Any]:
    """Book a rental car by ID. Returns booking confirmation."""
    car_id = query.get('car_id')
    renter_name = query.get('renter_name', 'Guest')
    pickup_date = query.get('pickup_date', '')
    return_date = query.get('return_date', '')
    
    if not car_id:
        return {"error": "Car ID is required"}
    
    car = next((c for c in CARS if c['id'] == car_id), None)
    
    if not car:
        return {"error": f"Car {car_id} not found"}
    
    booking = {
        "status": "confirmed",
        "booking_id": f"CAR-{car_id}-{renter_name[:3].upper()}",
        "car": car,
        "renter": renter_name,
        "pickup_date": pickup_date,
        "return_date": return_date,
        "total_price": car['price']
    }
    return booking


class CarRentalAgent(BaseAgent):
    """Agent specialized in car rental operations"""
    
    def __init__(self, llm=None):
        super().__init__(llm=llm, name="CarRentalAgent")
    
    def _initialize_tools(self) -> Dict[str, Any]:
        """Initialize car rental tools"""
        return {
            'search_cars': search_cars_tool,
            'compare_cars': compare_cars_tool,
            'book_car': book_car_tool,
        }
    
    def execute(self, task: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute car rental task"""
        if task in self.tools:
            return self._call_tool(task, params)
        else:
            if self.llm:
                return self._llm_route_task(task, params)
            else:
                return {"error": f"Unknown task '{task}' for CarRentalAgent"}
    
    def _llm_route_task(self, task: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Use LLM to route ambiguous tasks to appropriate tools"""
        available_tools = ", ".join(self.get_available_tools())
        prompt = f"""You are a Car Rental Agent. Based on the task and parameters, determine which tool to use.

Available tools: {available_tools}
Task: {task}
Parameters: {params}

Respond with only the tool name to use."""
        
        tool_name = self.llm.invoke(prompt).strip()
        
        if tool_name in self.tools:
            return self._call_tool(tool_name, params)
        else:
            return {"error": f"LLM suggested unknown tool '{tool_name}'"}

