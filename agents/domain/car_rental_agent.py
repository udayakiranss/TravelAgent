# car_rental_agent.py
# Car rental agent with multiple tools
from typing import Dict, Any, Optional, TYPE_CHECKING
from langchain.tools import tool
from agents.core.base_agent import BaseAgent
from data.cars import CARS
from utils.logger import get_logger
from llm.strategy.use_cases import UseCase

if TYPE_CHECKING:
    from api.context import TravelContext

logger = get_logger()


@tool
def search_cars_tool(query: Dict[str, Any]) -> list:
    """Search rental cars by city. Returns list of available cars."""
    city = query.get('city', '')
    if city:
        city = city.upper()
    
    if not city:
        return {"error": "city is required"}
    
    results = [c for c in CARS if c['city'] == city]
    logger.info(f"Car search: {city} -> {len(results)} results")
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
    
    logger.info(f"Compared {len(cars)} cars: ${comparison['price_range']['min']}-${comparison['price_range']['max']}")
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
    
    logger.info(f"Car booked: {booking['booking_id']} for ${car['price']}")
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
    
    def search_with_selection(
        self, 
        params: Dict[str, Any], 
        ctx: "TravelContext"
    ) -> Dict[str, Any]:
        """Search for rental cars and return the best option based on context criteria."""
        all_cars = self._call_tool('search_cars', params)
        
        if isinstance(all_cars, dict) and "error" in all_cars:
            return {"reservation": None, "options": [], "error": all_cars["error"]}
        
        if not all_cars:
             return {"reservation": None, "options": []}
        
        selected = self._select_best(all_cars, ctx.criteria)
        return {
            "reservation": selected,
            "options": all_cars
        }
    
    def execute(self, task: str, params: Dict[str, Any], ctx: Optional["TravelContext"] = None) -> Any:
        """Execute car rental task"""
        if task == 'search_cars' and ctx is not None:
            return self.search_with_selection(params, ctx)
        
        if task in self.tools:
            return self._call_tool(task, params)
        
        if self.llm:
            return self._llm_route_task(task, params, ctx)
        
        logger.warning(f"Unknown task '{task}' for {self.name}")
        return {"error": f"Unknown task '{task}' for {self.name}"}
    
    def _llm_route_task(self, task: str, params: Dict[str, Any], ctx: Optional["TravelContext"] = None) -> Dict[str, Any]:
        """Use LLM to route ambiguous tasks to appropriate tools - prompt from prompts.yaml"""
        available_tools = ", ".join(self.get_available_tools())
        
        # Get prompt from prompts.yaml via model_strategy
        if ctx and ctx.model_strategy:
            try:
                prompt = ctx.model_strategy.get_prompt_for_use_case(
                    UseCase.TASK_ROUTING,
                    agent_name="Car Rental Agent",
                    available_tools=available_tools,
                    task=task,
                    params=params
                )
                logger.debug("Retrieved task routing prompt from prompts.yaml")
            except Exception as e:
                logger.error(f"Failed to get prompt from prompts.yaml: {e}")
                raise ValueError(f"Cannot proceed without prompt from prompts.yaml: {e}") from e
        else:
            raise ValueError(
                "TravelContext with model_strategy is required. "
                "Prompt must come from prompts.yaml."
            )
        
        tool_name = self.llm.invoke(prompt).strip()
        logger.debug(f"LLM routed task '{task}' -> tool '{tool_name}'")
        
        if tool_name in self.tools:
            return self._call_tool(tool_name, params)
        
        logger.warning(f"LLM suggested unknown tool '{tool_name}'")
        return {"error": f"LLM suggested unknown tool '{tool_name}'"}
