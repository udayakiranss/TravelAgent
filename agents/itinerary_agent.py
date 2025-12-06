# itinerary_agent.py
# Itinerary management agent with multiple tools
# Supports both in-memory storage (CLI) and SQLite persistence (Web API)
from typing import Dict, Any, List, Optional
from langchain.tools import tool
from agents.base_agent import BaseAgent
from utils.logger import get_logger, log_method_entry_exit

logger = get_logger()


# In-memory storage for itineraries (used when no database session provided)
_ITINERARIES = {}


# =============================================================================
# Helper function for database operations
# =============================================================================

def _get_repository(session=None):
    """Get repository if session is provided, otherwise return None for in-memory mode."""
    if session is None:
        return None
    from database.repository import ItineraryRepository
    return ItineraryRepository(session)


def _itinerary_to_dict(itinerary) -> Dict[str, Any]:
    """Convert database Itinerary model to dictionary format."""
    return {
        "itinerary_id": itinerary.id,
        "traveler": itinerary.traveler_id,
        "flight": itinerary.flight_data,
        "hotel": itinerary.hotel_data,
        "car": itinerary.car_data,
        "total_cost": itinerary.total_cost,
        "status": itinerary.status,
        "version": itinerary.version,
        "original_query": itinerary.original_query,
        "created_at": itinerary.created_at.isoformat() if itinerary.created_at else None,
        "updated_at": itinerary.updated_at.isoformat() if itinerary.updated_at else None,
    }


# =============================================================================
# Tool Functions
# =============================================================================

@tool
def build_itinerary_tool(query: Dict[str, Any]) -> Dict[str, Any]:
    """Build a new itinerary from flight, hotel, and car bookings. Returns itinerary details."""
    # Extract parameters
    flight_booking = query.get('flight_booking')
    hotel_booking = query.get('hotel_booking')
    car_booking = query.get('car_booking')
    traveler_name = query.get('traveler_name', 'Guest')
    original_query = query.get('original_query')
    db_session = query.get('_db_session')  # Optional database session
    
    logger.debug(f"Building itinerary: traveler={traveler_name}, has_flight={flight_booking is not None}, has_hotel={hotel_booking is not None}, has_car={car_booking is not None}")
    
    # Try database mode first
    repo = _get_repository(db_session)
    
    if repo:
        # Database mode
        try:
            itinerary = repo.create(
                traveler_id=traveler_name,
                original_query=original_query,
                flight_data=flight_booking,
                hotel_data=hotel_booking,
                car_data=car_booking,
            )
            logger.info(f"Itinerary built (DB): {itinerary.id}, total_cost=${itinerary.total_cost}")
            return _itinerary_to_dict(itinerary)
        except Exception as e:
            logger.error(f"Database error building itinerary: {e}")
            return {"error": str(e)}
    else:
        # In-memory mode (backward compatible)
        itinerary_id = query.get('itinerary_id', f"ITIN-{len(_ITINERARIES) + 1}")
        
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
        
        logger.info(f"Itinerary built (memory): {itinerary_id}, total_cost=${itinerary['total_cost']}")
        return itinerary


@tool
def update_itinerary_tool(query: Dict[str, Any]) -> Dict[str, Any]:
    """Update an existing itinerary. Returns updated itinerary."""
    itinerary_id = query.get('itinerary_id')
    db_session = query.get('_db_session')
    version = query.get('version', 1)  # For optimistic locking
    
    logger.debug(f"Updating itinerary: id={itinerary_id}")
    
    if not itinerary_id:
        logger.warning("Itinerary ID is required for update")
        return {"error": "Itinerary ID is required"}
    
    # Try database mode first
    repo = _get_repository(db_session)
    
    if repo:
        # Database mode with optimistic locking
        try:
            from database.repository import ItineraryNotFoundError, VersionConflictError, InvalidStatusTransitionError
            
            # Prepare update kwargs (use ... sentinel for "not provided")
            kwargs = {"itinerary_id": itinerary_id, "version": version}
            
            if 'flight_booking' in query:
                kwargs['flight_data'] = query['flight_booking']
            if 'hotel_booking' in query:
                kwargs['hotel_data'] = query['hotel_booking']
            if 'car_booking' in query:
                kwargs['car_data'] = query['car_booking']
            
            itinerary = repo.update(**kwargs)
            logger.info(f"Itinerary updated (DB): {itinerary.id}, new_total_cost=${itinerary.total_cost}")
            return _itinerary_to_dict(itinerary)
            
        except ItineraryNotFoundError:
            logger.warning(f"Itinerary {itinerary_id} not found")
            return {"error": f"Itinerary {itinerary_id} not found"}
        except VersionConflictError as e:
            logger.warning(f"Version conflict for itinerary {itinerary_id}: {e}")
            return {"error": "VERSION_CONFLICT", "message": str(e), "current_version": e.current_version}
        except InvalidStatusTransitionError as e:
            logger.warning(f"Invalid status transition for itinerary {itinerary_id}: {e}")
            return {"error": "CANNOT_MODIFY", "message": str(e)}
        except Exception as e:
            logger.error(f"Database error updating itinerary: {e}")
            return {"error": str(e)}
    else:
        # In-memory mode
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
        
        logger.info(f"Itinerary updated (memory): {itinerary_id}, new_total_cost=${itinerary['total_cost']}")
        return itinerary


@tool
def get_itinerary_tool(query: Dict[str, Any]) -> Dict[str, Any]:
    """Get itinerary details by ID. Returns itinerary information."""
    itinerary_id = query.get('itinerary_id')
    db_session = query.get('_db_session')
    
    logger.debug(f"Getting itinerary: id={itinerary_id}")
    
    if not itinerary_id:
        logger.warning("Itinerary ID is required")
        return {"error": "Itinerary ID is required"}
    
    # Try database mode first
    repo = _get_repository(db_session)
    
    if repo:
        # Database mode
        itinerary = repo.get_by_id(itinerary_id)
        if itinerary is None:
            logger.warning(f"Itinerary {itinerary_id} not found")
            return {"error": f"Itinerary {itinerary_id} not found"}
        
        logger.debug(f"Retrieved itinerary (DB) {itinerary_id} for traveler {itinerary.traveler_id}")
        return _itinerary_to_dict(itinerary)
    else:
        # In-memory mode
        if itinerary_id not in _ITINERARIES:
            logger.warning(f"Itinerary {itinerary_id} not found")
            return {"error": f"Itinerary {itinerary_id} not found"}
        
        itinerary = _ITINERARIES[itinerary_id]
        logger.debug(f"Retrieved itinerary (memory) {itinerary_id} for traveler {itinerary.get('traveler', 'Unknown')}")
        return itinerary


@tool
def list_itineraries_tool(query: Dict[str, Any]) -> Dict[str, Any]:
    """List all itineraries. Returns dict with items, total, page, limit, and has_more."""
    traveler_name = query.get('traveler_name')
    status = query.get('status')
    page = query.get('page', 1)
    limit = query.get('limit', 20)
    db_session = query.get('_db_session')
    
    logger.debug(f"Listing itineraries: traveler_filter={traveler_name or 'all'}, status={status or 'all'}")
    
    # Try database mode first
    repo = _get_repository(db_session)
    
    if repo:
        # Database mode with pagination
        itineraries, total = repo.list_all(
            status=status,
            traveler_id=traveler_name,
            page=page,
            limit=limit,
        )
        
        result = {
            "items": [_itinerary_to_dict(it) for it in itineraries],
            "total": total,
            "page": page,
            "limit": limit,
            "has_more": (page * limit) < total
        }
        logger.info(f"Found {total} itineraries (DB), returning page {page}")
        return result
    else:
        # In-memory mode - return same structure for consistency
        all_items = []
        for it in _ITINERARIES.values():
            # Filter by traveler if specified
            if traveler_name and it.get('traveler') != traveler_name:
                continue
            # Filter by status if specified
            if status and it.get('status') != status:
                continue
            # Create summary (exclude detailed booking data)
            summary = {k: v for k, v in it.items() if k not in ('flight', 'hotel', 'car')}
            all_items.append(summary)
        
        # Apply pagination
        total = len(all_items)
        offset = (max(1, page) - 1) * limit
        paginated_items = all_items[offset:offset + limit]
        
        result = {
            "items": paginated_items,
            "total": total,
            "page": page,
            "limit": limit,
            "has_more": (page * limit) < total
        }
        logger.info(f"Found {total} itineraries (memory), returning page {page}")
        return result


# =============================================================================
# Itinerary Agent Class
# =============================================================================

class ItineraryAgent(BaseAgent):
    """Agent specialized in itinerary management.
    
    Supports two modes:
    - In-memory mode (default): Uses global _ITINERARIES dict for CLI compatibility
    - Database mode: When db_session is provided in params, uses SQLite repository
    """
    
    def __init__(self, llm=None, db_session=None):
        """
        Initialize the itinerary agent.
        
        Args:
            llm: Optional LLM provider for intelligent routing
            db_session: Optional SQLModel session for database persistence
        """
        super().__init__(llm=llm, name="ItineraryAgent")
        self.db_session = db_session
    
    def _initialize_tools(self) -> Dict[str, Any]:
        """Initialize itinerary management tools"""
        return {
            'build_itinerary': build_itinerary_tool,
            'update_itinerary': update_itinerary_tool,
            'get_itinerary': get_itinerary_tool,
            'list_itineraries': list_itineraries_tool,
        }
    
    @log_method_entry_exit(level="DEBUG")
    def execute(self, task: str, params: Dict[str, Any], db_session=None) -> Dict[str, Any]:
        """Execute itinerary management task.
        
        Args:
            task: Task name to execute
            params: Task parameters
            db_session: Optional database session (overrides instance session)
        
        Returns:
            Task result dictionary
        """
        # Inject database session if available
        session = db_session or self.db_session
        if session:
            params = {**params, '_db_session': session}
        
        logger.debug(f"ItineraryAgent executing task: {task} with params: {list(params.keys())}")
        
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
        # Remove internal params from display
        display_params = {k: v for k, v in params.items() if not k.startswith('_')}
        
        available_tools = ", ".join(self.get_available_tools())
        prompt = f"""You are an Itinerary Management Agent. Based on the task and parameters, determine which tool to use.

Available tools: {available_tools}
Task: {task}
Parameters: {display_params}

Respond with only the tool name to use."""
        
        logger.debug(f"Using LLM to route task '{task}' to appropriate tool")
        tool_name = self.llm.invoke(prompt).strip()
        logger.debug(f"LLM suggested tool: {tool_name}")
        
        if tool_name in self.tools:
            return self._call_tool(tool_name, params)
        else:
            logger.warning(f"LLM suggested unknown tool '{tool_name}'")
            return {"error": f"LLM suggested unknown tool '{tool_name}'"}


# =============================================================================
# Utility functions for direct repository access (used by API layer)
# =============================================================================

def get_itinerary_from_db(itinerary_id: str, session) -> Optional[Dict[str, Any]]:
    """Get itinerary directly from database (for API use)."""
    repo = _get_repository(session)
    if repo:
        itinerary = repo.get_by_id(itinerary_id)
        return _itinerary_to_dict(itinerary) if itinerary else None
    return None


def confirm_itinerary(itinerary_id: str, session) -> Dict[str, Any]:
    """Confirm an itinerary (API use)."""
    from database.repository import ItineraryRepository, ItineraryNotFoundError, InvalidStatusTransitionError
    repo = ItineraryRepository(session)
    try:
        itinerary = repo.confirm(itinerary_id)
        return _itinerary_to_dict(itinerary)
    except (ItineraryNotFoundError, InvalidStatusTransitionError) as e:
        return {"error": str(e)}


def cancel_itinerary(itinerary_id: str, session) -> Dict[str, Any]:
    """Cancel an itinerary (API use)."""
    from database.repository import ItineraryRepository, ItineraryNotFoundError, InvalidStatusTransitionError
    repo = ItineraryRepository(session)
    try:
        itinerary = repo.cancel(itinerary_id)
        return _itinerary_to_dict(itinerary)
    except (ItineraryNotFoundError, InvalidStatusTransitionError) as e:
        return {"error": str(e)}


def delete_itinerary(itinerary_id: str, session) -> Dict[str, Any]:
    """Delete a draft itinerary (API use)."""
    from database.repository import ItineraryRepository, ItineraryNotFoundError, InvalidStatusTransitionError
    repo = ItineraryRepository(session)
    try:
        repo.delete(itinerary_id)
        return {"success": True, "message": f"Itinerary {itinerary_id} deleted"}
    except (ItineraryNotFoundError, InvalidStatusTransitionError) as e:
        return {"error": str(e)}
