import httpx
import time
import functools
import json
import sys
import os

# Add parent directory to sys.path to allow importing from utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Optional, Dict, Any, List
from mcp.server.fastmcp import FastMCP, Context
from pydantic import BaseModel, Field

# Import logging utilities
from utils.logger import get_logger, SessionContext, _format_duration

# Initialize Logger
logger = get_logger()
# Ensure logger is setup (logs to stdout/file based on env)
logger.setup()

# Initialize MCP Server
mcp = FastMCP("Travel Booking Agent")

# API Base URL
API_BASE_URL = "http://localhost:8000/api/v1"

# =============================================================================
# Logging Decorator
# =============================================================================

def logged_mcp_action(action_type: str = "TOOL"):
    """
    Decorator to add logging and request tracing to MCP actions.
    
    Args:
        action_type: "TOOL" or "RESOURCE" to distinguish in logs
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate unique Request ID for this MCP interaction
            request_id = f"MCP-{SessionContext.new_session()[:8]}"
            SessionContext.set_session_id(request_id)
            
            start_time = time.perf_counter()
            func_name = func.__name__
            
            # Sanitize args for logging (truncate long strings)
            sanitized_kwargs = {
                k: (f"{str(v)[:50]}..." if isinstance(v, str) and len(str(v)) > 50 else v)
                for k, v in kwargs.items()
            }
            
            logger.info(f"[{action_type}] → ENTRY: {func_name} | args={sanitized_kwargs}")
            
            try:
                result = await func(*args, **kwargs)
                
                duration_ms = (time.perf_counter() - start_time) * 1000
                duration_str = _format_duration(duration_ms)
                
                # Log response summary (truncate if large)
                result_summary = str(result)
                if len(result_summary) > 200:
                    result_summary = result_summary[:200] + "..."
                
                logger.info(f"[{action_type}] ← EXIT: {func_name} | success | duration={duration_str}")
                logger.debug(f"[{action_type}] RESPONSE: {result_summary}")
                return result
                
            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                duration_str = _format_duration(duration_ms)
                
                logger.error(f"[{action_type}] ← EXIT: {func_name} | failed | duration={duration_str} | error={str(e)}")
                # Re-raise or return error string? 
                # MCP tools usually return strings to the LLM. 
                # If we raise, the MCP server might crash or return a generic error.
                # The existing code returns f"Failed: {str(e)}".
                # We will let the inner function handle the return value, 
                # but if an *unexpected* exception occurs that wasn't caught, we log it here.
                raise
            finally:
                SessionContext.clear_session()
        return wrapper
    return decorator

# Enable verbose HTTP logging (set to True for debugging)
VERBOSE_HTTP = os.environ.get("MCP_VERBOSE", "false").lower() == "true"

# HTTP Client for making requests
async def make_request(method: str, endpoint: str, data: Optional[Dict] = None, params: Optional[Dict] = None) -> Dict[str, Any]:
    """Helper to make HTTP requests to the Travel Booking API."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            url = f"{API_BASE_URL}{endpoint}"
            # Pass the current request ID to the API for full distributed tracing
            headers = {"X-Request-ID": SessionContext.get_session_id() or ""}
            
            # Log request if verbose mode enabled
            if VERBOSE_HTTP:
                logger.info(f"[HTTP] → {method} {url}")
                if data:
                    logger.info(f"[HTTP] REQUEST BODY: {json.dumps(data, indent=2)}")
                if params:
                    logger.info(f"[HTTP] PARAMS: {params}")
            
            response = await client.request(method, url, json=data, params=params, headers=headers)
            
            # Log response if verbose mode enabled
            if VERBOSE_HTTP:
                logger.info(f"[HTTP] ← {response.status_code}")
                try:
                    resp_body = response.json()
                    resp_str = json.dumps(resp_body, indent=2)
                    # Truncate very large responses
                    if len(resp_str) > 1000:
                        resp_str = resp_str[:1000] + "\n... (truncated)"
                    logger.info(f"[HTTP] RESPONSE BODY:\n{resp_str}")
                except Exception:
                    logger.info(f"[HTTP] RESPONSE: {response.text[:500]}")
            
            # Raise exception for 4xx/5xx errors so they can be caught
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPStatusError as e:
            # Log error details
            logger.error(f"[HTTP] ERROR: {e.response.status_code} - {e.response.text[:200]}")
            # Try to return the error detail from the API if available
            try:
                error_detail = e.response.json()
                error_msg = error_detail.get("detail", {}).get("message") or error_detail.get("detail") or str(e)
                raise RuntimeError(f"API Error: {error_msg}")
            except Exception:
                raise RuntimeError(f"API Request Failed: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Connection Error: {str(e)}")

# =============================================================================
# Resources (Read-Only Context)
# =============================================================================

@mcp.resource("travel://health")
@logged_mcp_action("RESOURCE")
async def get_health() -> str:
    """Get the health status of the Travel Booking System."""
    try:
        response = await make_request("GET", "/health")
        return f"Status: {response.get('status')}\nDatabase: {response.get('database')}\nLLM: {response.get('llm')}"
    except Exception as e:
        return f"System Unhealthy: {str(e)}"

@mcp.resource("travel://itineraries/{itinerary_id}")
@logged_mcp_action("RESOURCE")
async def get_itinerary_resource(itinerary_id: str) -> str:
    """Get full details of a specific itinerary."""
    try:
        data = await make_request("GET", f"/itineraries/{itinerary_id}")
        return str(data)
    except Exception as e:
        return f"Error fetching itinerary: {str(e)}"

@mcp.resource("travel://itineraries/{itinerary_id}/history")
@logged_mcp_action("RESOURCE")
async def get_itinerary_history_resource(itinerary_id: str) -> str:
    """Get chat/conversation history for a specific itinerary."""
    try:
        data = await make_request("GET", f"/itineraries/{itinerary_id}/history")
        
        # Format history nicely for LLM context
        messages = data.get("messages", [])
        if not messages:
            return "No conversation history."
            
        formatted = [f"Conversation Log for {itinerary_id}:"]
        for msg in messages:
            timestamp = msg.get('created_at', '')[:19]
            formatted.append(f"[{timestamp}] {msg['role'].upper()}: {msg['content']}")
            
        return "\n".join(formatted)
    except Exception as e:
        return f"Error fetching history: {str(e)}"

@mcp.resource("travel://preferences/{traveler_id}")
@logged_mcp_action("RESOURCE")
async def get_preferences_resource(traveler_id: str) -> str:
    """Get user preferences for a specific traveler."""
    try:
        data = await make_request("GET", f"/preferences/{traveler_id}")
        return str(data)
    except Exception as e:
        return f"Error fetching preferences: {str(e)}"

# =============================================================================
# Tools (Actions)
# =============================================================================

@mcp.tool()
@logged_mcp_action("TOOL")
async def search_flights(origin: str, destination: str, date: str) -> str:
    """
    Search for available flights without creating an itinerary.
    
    Args:
        origin: Origin city or airport code (e.g. "NYC", "London", "JFK")
        destination: Destination city or airport code (e.g. "PAR", "Paris", "LHR")  
        date: Travel date in YYYY-MM-DD format (e.g. "2025-12-08")
    
    Returns:
        Formatted string listing available flights with details
    """
    # Validate inputs
    if not origin:
        return "Error: origin parameter is required."
    if not destination:
        return "Error: destination parameter is required."
    if not date:
        return "Error: date parameter is required."
    
    # Build payload with validated parameters
    origin_str = str(origin).strip()
    destination_str = str(destination).strip()
    date_str = str(date).strip()
    
    payload = {
        "origin": origin_str,
        "destination": destination_str,
        "date": date_str
    }
    
    try:
        response = await make_request("POST", "/search/flights", data=payload)
        
        # Handle empty or None response
        if not response or (isinstance(response, list) and len(response) == 0):
            return f"No flights found from {origin_str} to {destination_str} on {date_str}."
        
        # Ensure response is a list
        if not isinstance(response, list):
            return f"Unexpected response format from API: {type(response)}"
        
        result = [f"Found {len(response)} flights:"]
        for flight in response:
            if not isinstance(flight, dict):
                continue
                
            # Handle both 'from'/'to' and 'origin'/'destination' keys
            flight_origin = flight.get('origin') or flight.get('from', '?')
            flight_destination = flight.get('destination') or flight.get('to', '?')
            flight_id = flight.get('id', '')
            airline = flight.get('airline', 'Unknown')
            price = flight.get('price', 0)
            departure = flight.get('departure', '')
            arrival = flight.get('arrival', '')
            duration = flight.get('duration', '')
            
            result.append(
                f"- {airline} ({flight_id}): ${price} | {flight_origin} -> {flight_destination}"
            )
            if departure and arrival:
                result[-1] += f" | Dep: {departure}, Arr: {arrival}"
            if duration:
                result[-1] += f" | Duration: {duration}"
        return "\n".join(result)
    except KeyError as e:
        logger.error(f"Flight search KeyError: Missing key {e} in response")
        return f"Flight Search Failed: Missing data in API response - {str(e)}"
    except AttributeError as e:
        logger.error(f"Flight search AttributeError: {e}")
        return f"Flight Search Failed: Invalid response format - {str(e)}"
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        logger.error(f"Flight search error [{error_type}]: {error_msg}", exc_info=True)
        return f"Flight Search Failed [{error_type}]: {error_msg}"

@mcp.tool()
@logged_mcp_action("TOOL")
async def search_hotels(city: str) -> str:
    """
    Search for available hotels without creating an itinerary.
    
    Args:
        city: City name to search for hotels (e.g. "Paris", "New York")
    """
    payload = {"city": city}
    
    try:
        response = await make_request("POST", "/search/hotels", data=payload)
        if not response:
            return f"No hotels found in {city}."
        
        result = [f"Found {len(response)} hotels in {city}:"]
        for hotel in response:
            name = hotel.get('name', 'Unknown')
            price = hotel.get('total_price') or hotel.get('price', 0)
            rating = hotel.get('rating', 'N/A')
            category = hotel.get('category', '')
            location = hotel.get('location', hotel.get('city', 'N/A'))
            
            result.append(
                f"- {name}: ${price} per night"
            )
            if rating != 'N/A':
                result[-1] += f" | Rating: {rating}/5"
            if category:
                result[-1] += f" | Category: {category}"
            result[-1] += f" | Location: {location}"
        return "\n".join(result)
    except Exception as e:
        return f"Hotel Search Failed: {str(e)}"

@mcp.tool()
@logged_mcp_action("TOOL")
async def search_cars(city: str) -> str:
    """
    Search for available car rentals without creating an itinerary.
    
    Args:
        city: City name to search for car rentals
    """
    payload = {"city": city}
    
    try:
        response = await make_request("POST", "/search/cars", data=payload)
        if not response:
            return f"No cars found in {city}."
        
        result = [f"Found {len(response)} cars in {city}:"]
        for car in response:
            company = car.get('company', 'Unknown')
            car_type = car.get('car_type') or car.get('type', 'Unknown')
            model = car.get('model', 'Unknown')
            price = car.get('total_price') or car.get('price', 0)
            
            result.append(
                f"- {company} {car_type} ({model}): ${price} per day"
            )
        return "\n".join(result)
    except Exception as e:
        return f"Car Search Failed: {str(e)}"

@mcp.tool()
@logged_mcp_action("TOOL")
async def plan_trip(query: str, traveler_id: str, selection_criteria: Optional[str] = None) -> str:
    """
    Plan a new trip based on natural language query.
    
    Args:
        query: Natural language description of the trip (e.g., "Weekend in Paris").
        traveler_id: ID of the traveler.
        selection_criteria: Optional criteria for auto-selection ('cheapest', 'fastest', 'best_rated').
    """
    payload = {
        "query": query,
        "traveler_id": traveler_id,
        "include_summary": True
    }
    if selection_criteria:
        payload["selection_criteria"] = selection_criteria
        
    try:
        response = await make_request("POST", "/agent/plan", data=payload)
        return f"Trip Planned Successfully!\nItinerary ID: {response['itinerary_id']}\nSummary: {response.get('summary', 'No summary provided')}"
    except Exception as e:
        return f"Planning Failed: {str(e)}"

@mcp.tool()
@logged_mcp_action("TOOL")
async def modify_itinerary(itinerary_id: str, traveler_id: str, instruction: str) -> str:
    """
    Modify an existing itinerary using natural language.
    
    Args:
        itinerary_id: The ID of the itinerary to modify.
        traveler_id: The traveler's ID (for context/auth).
        instruction: Natural language modification instruction (e.g., "Change flight to 5pm").
    """
    payload = {
        "instruction": instruction,
        "traveler_id": traveler_id
    }
    
    try:
        response = await make_request("POST", f"/itineraries/{itinerary_id}/modify", data=payload)
        return f"Modification Successful: {response.get('message')}"
    except Exception as e:
        return f"Modification Failed: {str(e)}"

@mcp.tool()
@logged_mcp_action("TOOL")
async def list_itineraries(traveler_id: Optional[str] = None, status: Optional[str] = None, limit: int = 5) -> str:
    """
    List itineraries with filtering.
    
    Args:
        traveler_id: Filter by traveler ID.
        status: Filter by status ('draft', 'confirmed', 'cancelled').
        limit: Max number of items to return.
    """
    params = {"limit": limit}
    if traveler_id:
        params["traveler_id"] = traveler_id
    if status:
        params["status"] = status
        
    try:
        response = await make_request("GET", "/itineraries", params=params)
        items = response.get("items", [])
        
        if not items:
            return "No itineraries found."
            
        result = [f"Found {response['total']} itineraries (showing {len(items)}):"]
        for item in items:
            result.append(f"- [{item['status']}] ID: {item['id']} | {item.get('original_query', 'No Query')} | Cost: ${item['total_cost']}")
        
        return "\n".join(result)
    except Exception as e:
        return f"Listing Failed: {str(e)}"

@mcp.tool()
@logged_mcp_action("TOOL")
async def confirm_itinerary(itinerary_id: str) -> str:
    """
    Confirm a draft itinerary. Locks it from further edits.
    
    Args:
        itinerary_id: The ID of the itinerary to confirm.
    """
    try:
        response = await make_request("POST", f"/itineraries/{itinerary_id}/confirm")
        return f"Itinerary Confirmed: {response.get('message')}"
    except Exception as e:
        return f"Confirmation Failed: {str(e)}"

@mcp.tool()
@logged_mcp_action("TOOL")
async def cancel_itinerary(itinerary_id: str) -> str:
    """
    Cancel an itinerary.
    
    Args:
        itinerary_id: The ID of the itinerary to cancel.
    """
    try:
        response = await make_request("POST", f"/itineraries/{itinerary_id}/cancel")
        return f"Itinerary Cancelled: {response.get('message')}"
    except Exception as e:
        return f"Cancellation Failed: {str(e)}"

@mcp.tool()
@logged_mcp_action("TOOL")
async def upsert_preferences(
    traveler_id: str,
    flight_preferences: Optional[Dict[str, Any]] = None,
    hotel_preferences: Optional[Dict[str, Any]] = None,
    dietary_restrictions: Optional[List[str]] = None,
    budget_range: Optional[Dict[str, Any]] = None
) -> str:
    """
    Create or update user preferences.
    
    Args:
        traveler_id: The ID of the traveler.
        flight_preferences: e.g. {"seat_type": "aisle", "preferred_airlines": ["Delta"]}
        hotel_preferences: e.g. {"min_rating": 4, "amenities": ["wifi"]}
        dietary_restrictions: List of restrictions e.g. ["vegetarian"]
        budget_range: e.g. {"min": 500, "max": 2000, "currency": "USD"}
    """
    payload = {}
    if flight_preferences:
        payload["flight_preferences"] = flight_preferences
    if hotel_preferences:
        payload["hotel_preferences"] = hotel_preferences
    if dietary_restrictions:
        payload["dietary_restrictions"] = dietary_restrictions
    if budget_range:
        payload["budget_range"] = budget_range
        
    try:
        response = await make_request("PUT", f"/preferences/{traveler_id}", data=payload)
        return f"Preferences Updated Successfully. New Summary: {response.get('summary')}"
    except Exception as e:
        return f"Update Failed: {str(e)}"

if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
