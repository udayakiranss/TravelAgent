# planner.py
# LLM-based planner that intelligently selects agents to handle user queries
from typing import Dict, Any, List, Optional
from agents.llm_provider import LLMProvider
from utils.logger import get_logger
import json

logger = get_logger()


def plan_trip(intent: dict, llm: Optional[LLMProvider] = None) -> List[Dict[str, Any]]:
    """
    Plan a trip using LLM to intelligently select agents and tasks
    
    Args:
        intent: User intent dictionary
        llm: Optional LLM provider for intelligent planning
    
    Returns:
        List of tasks with agent assignments
    """
    if llm is None:
        return _rule_based_plan(intent)
    
    return _llm_based_plan(intent, llm)


def _rule_based_plan(intent: dict) -> List[Dict[str, Any]]:
    """Fallback rule-based planning"""
    tasks = []
    needs = intent.get('needs', [])
    
    if 'flight' in needs:
        tasks.append({
            'agent': 'FlightBookingAgent',
            'task': 'search_flights',
            'params': {
                'from': intent.get('from'),
                'to': intent.get('to'),
                'date': intent.get('date')
            }
        })
    
    if 'hotel' in needs:
        tasks.append({
            'agent': 'HotelBookingAgent',
            'task': 'search_hotels',
            'params': {'city': intent.get('to')}
        })
    
    if 'car' in needs:
        tasks.append({
            'agent': 'CarRentalAgent',
            'task': 'search_cars',
            'params': {'city': intent.get('to')}
        })
    
    # Build itinerary
    tasks.append({
        'agent': 'ItineraryAgent',
        'task': 'build_itinerary',
        'params': {}
    })
    
    logger.debug(f"Rule-based plan: {len(tasks)} tasks")
    return tasks


def _llm_based_plan(intent: dict, llm: LLMProvider) -> List[Dict[str, Any]]:
    """LLM-based intelligent planning"""
    available_agents = [
        "FlightBookingAgent - handles flight search, comparison, and booking",
        "HotelBookingAgent - handles hotel search, comparison, and booking",
        "CarRentalAgent - handles car search, comparison, and booking",
        "ItineraryAgent - handles itinerary creation, updates, and retrieval",
    ]
    
    prompt = f"""You are a travel planning assistant. Based on the user's intent, create a plan that selects the appropriate agents and tasks.

Available Agents:
{chr(10).join(f"- {agent}" for agent in available_agents)}

User Intent:
{json.dumps(intent, indent=2)}

Create a JSON array of tasks. Each task should have:
- "agent": The agent name (FlightBookingAgent, HotelBookingAgent, CarRentalAgent, ItineraryAgent)
- "task": The specific task for that agent
- "params": Parameters needed for the task

For FlightBookingAgent, tasks can be: search_flights, compare_flights, book_flight
For HotelBookingAgent, tasks can be: search_hotels, compare_hotels, book_hotel
For CarRentalAgent, tasks can be: search_cars, compare_cars, book_car
For ItineraryAgent, tasks can be: build_itinerary, update_itinerary, get_itinerary

Return ONLY a valid JSON array, no other text. Example format:
[
  {{
    "agent": "FlightBookingAgent",
    "task": "search_flights",
    "params": {{"from": "NYC", "to": "LON", "date": "2025-08-12"}}
  }},
  {{
    "agent": "HotelBookingAgent",
    "task": "search_hotels",
    "params": {{"city": "LON"}}
  }},
  {{
    "agent": "CarRentalAgent",
    "task": "search_cars",
    "params": {{"city": "LON"}}
  }},
  {{
    "agent": "ItineraryAgent",
    "task": "build_itinerary",
    "params": {{}}
  }}
]"""

    try:
        response = llm.invoke_structured(
            prompt,
            response_format={
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "agent": {"type": "string"},
                        "task": {"type": "string"},
                        "params": {"type": "object"}
                    },
                    "required": ["agent", "task", "params"]
                }
            }
        )
        
        # Handle response format
        if isinstance(response, dict) and "raw_response" in response:
            try:
                tasks = json.loads(response["raw_response"])
            except:
                return _rule_based_plan(intent)
        elif isinstance(response, list):
            tasks = response
        else:
            return _rule_based_plan(intent)
        
        # Validate and return tasks
        validated_tasks = []
        for task in tasks:
            if isinstance(task, dict) and "agent" in task and "task" in task:
                validated_tasks.append({
                    "agent": task["agent"],
                    "task": task["task"],
                    "params": task.get("params", {})
                })
        
        if validated_tasks:
            logger.debug(f"LLM-based plan: {len(validated_tasks)} tasks")
            return validated_tasks
        else:
            logger.warning("LLM planning returned no valid tasks, falling back to rule-based")
            return _rule_based_plan(intent)
    
    except Exception as e:
        logger.warning(f"LLM planning failed: {e}, using rule-based")
        return _rule_based_plan(intent)
