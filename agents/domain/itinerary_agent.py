# itinerary_agent.py
# Itinerary management agent with database persistence via TravelContext
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from langchain.tools import tool
from agents.core.base_agent import BaseAgent
from utils.logger import get_logger, log_method_entry_exit
from llm.strategy.use_cases import UseCase

if TYPE_CHECKING:
    from api.context import TravelContext
    from database.models import Itinerary

logger = get_logger()


# =============================================================================
# Helper function for database operations
# =============================================================================

def _get_repository(session):
    """Get repository from session."""
    from database.repository import TravelItineraryRepository
    return TravelItineraryRepository(session)


def _itinerary_to_dict(itinerary: "Itinerary") -> Dict[str, Any]:
    """Convert database Itinerary model to dictionary format."""
    return {
        "itinerary_id": itinerary.id,
        "traveler_id": itinerary.traveler_id,
        "flight_reservation": itinerary.flight_reservation,
        "hotel_reservation": itinerary.hotel_reservation,
        "car_reservation": itinerary.car_reservation,
        "total_cost": itinerary.total_cost,
        "status": itinerary.status,
        "version": itinerary.version,
        "original_query": itinerary.original_query,
        "created_at": itinerary.created_at.isoformat() if itinerary.created_at else None,
        "updated_at": itinerary.updated_at.isoformat() if itinerary.updated_at else None,
    }


# =============================================================================
# Tool Functions (for LangChain compatibility)
# =============================================================================

@tool
def build_itinerary_tool(query: Dict[str, Any]) -> Dict[str, Any]:
    """Build a new itinerary from flight, hotel, and car reservations. Returns itinerary details."""
    # This tool is primarily for LLM-based workflows
    # For context-aware operations, use ItineraryAgent.build() directly
    return {"info": "Use ItineraryAgent.build() with TravelContext for database operations"}


@tool
def get_itinerary_tool(query: Dict[str, Any]) -> Dict[str, Any]:
    """Get itinerary details by ID. Returns itinerary information."""
    return {"info": "Use ItineraryAgent.get() with TravelContext for database operations"}


@tool
def list_itineraries_tool(query: Dict[str, Any]) -> Dict[str, Any]:
    """List all itineraries. Returns dict with items, total, page, limit, and has_more."""
    return {"info": "Use ItineraryAgent.list_all() with TravelContext for database operations"}


# =============================================================================
# Itinerary Agent Class
# =============================================================================

class ItineraryAgent(BaseAgent):
    """
    Agent specialized in itinerary management.
    Uses database persistence via TravelContext.session.
    """
    
    def __init__(self, llm=None):
        """
        Initialize the itinerary agent.
        
        Args:
            llm: Optional LLM provider for intelligent routing
        """
        super().__init__(llm=llm, name="ItineraryAgent")
    
    def _initialize_tools(self) -> Dict[str, Any]:
        """Initialize itinerary management tools"""
        return {
            'build_itinerary': build_itinerary_tool,
            'get_itinerary': get_itinerary_tool,
            'list_itineraries': list_itineraries_tool,
        }
    
    # =========================================================================
    # Context-Aware Operations
    # =========================================================================
    
    @log_method_entry_exit(level="DEBUG")
    def build(
        self,
        flight_reservation: Optional[Dict[str, Any]],
        hotel_reservation: Optional[Dict[str, Any]],
        car_reservation: Optional[Dict[str, Any]],
        ctx: "TravelContext"
    ) -> "Itinerary":
        """
        Build a new itinerary with the given reservations.
        
        Args:
            flight_reservation: Selected flight data
            hotel_reservation: Selected hotel data
            car_reservation: Selected car data
            ctx: TravelContext with session and traveler_id
        
        Returns:
            Created Itinerary instance
        """
        logger.info(f"Building itinerary for traveler: {ctx.traveler_id}")
        
        repo = _get_repository(ctx.session)
        
        itinerary = repo.create(
            traveler_id=ctx.traveler_id,
            original_query=ctx.original_query,
            flight_reservation=flight_reservation,
            hotel_reservation=hotel_reservation,
            car_reservation=car_reservation,
        )
        
        logger.info(f"Created itinerary: id={itinerary.id}, total_cost=${itinerary.total_cost}")
        return itinerary
    
    @log_method_entry_exit(level="DEBUG")
    def get(self, ctx: "TravelContext") -> Optional["Itinerary"]:
        """
        Get itinerary by ID from context.
        
        Args:
            ctx: TravelContext with session and itinerary_id
        
        Returns:
            Itinerary instance or None if not found
        """
        if not ctx.itinerary_id:
            logger.warning("No itinerary_id in context")
            return None
        
        repo = _get_repository(ctx.session)
        itinerary = repo.get_by_id(ctx.itinerary_id)
        
        if itinerary:
            logger.debug(f"Retrieved itinerary: id={ctx.itinerary_id}")
        else:
            logger.warning(f"Itinerary not found: id={ctx.itinerary_id}")
        
        return itinerary
    
    @log_method_entry_exit(level="DEBUG")
    def update(
        self,
        ctx: "TravelContext",
        flight_reservation: Optional[Dict[str, Any]] = ...,
        hotel_reservation: Optional[Dict[str, Any]] = ...,
        car_reservation: Optional[Dict[str, Any]] = ...,
    ) -> "Itinerary":
        """
        Update itinerary with new reservations.
        
        Args:
            ctx: TravelContext with session, itinerary_id, and current itinerary
            flight_reservation: New flight data (... to keep existing, None to clear)
            hotel_reservation: New hotel data (... to keep existing, None to clear)
            car_reservation: New car data (... to keep existing, None to clear)
        
        Returns:
            Updated Itinerary instance
        """
        if not ctx.itinerary_id or not ctx.itinerary:
            raise ValueError("Context must have itinerary_id and itinerary loaded")
        
        repo = _get_repository(ctx.session)
        
        itinerary = repo.update(
            itinerary_id=ctx.itinerary_id,
            version=ctx.itinerary.version,
            flight_reservation=flight_reservation,
            hotel_reservation=hotel_reservation,
            car_reservation=car_reservation,
        )
        
        logger.info(f"Updated itinerary: id={itinerary.id}, new_version={itinerary.version}")
        return itinerary
    
    @log_method_entry_exit(level="DEBUG")
    def confirm(self, ctx: "TravelContext") -> "Itinerary":
        """
        Confirm a draft itinerary.
        
        Args:
            ctx: TravelContext with session and itinerary_id
        
        Returns:
            Confirmed Itinerary instance
        """
        if not ctx.itinerary_id:
            raise ValueError("Context must have itinerary_id")
        
        repo = _get_repository(ctx.session)
        itinerary = repo.confirm(ctx.itinerary_id)
        
        logger.info(f"Confirmed itinerary: id={itinerary.id}")
        return itinerary
    
    @log_method_entry_exit(level="DEBUG")
    def cancel(self, ctx: "TravelContext") -> "Itinerary":
        """
        Cancel an itinerary.
        
        Args:
            ctx: TravelContext with session and itinerary_id
        
        Returns:
            Cancelled Itinerary instance
        """
        if not ctx.itinerary_id:
            raise ValueError("Context must have itinerary_id")
        
        repo = _get_repository(ctx.session)
        itinerary = repo.cancel(ctx.itinerary_id)
        
        logger.info(f"Cancelled itinerary: id={itinerary.id}")
        return itinerary
    
    @log_method_entry_exit(level="DEBUG")
    def delete(self, ctx: "TravelContext") -> bool:
        """
        Delete a draft itinerary.
        
        Args:
            ctx: TravelContext with session and itinerary_id
        
        Returns:
            True if deleted successfully
        """
        if not ctx.itinerary_id:
            raise ValueError("Context must have itinerary_id")
        
        repo = _get_repository(ctx.session)
        result = repo.delete(ctx.itinerary_id)
        
        logger.info(f"Deleted itinerary: id={ctx.itinerary_id}")
        return result
    
    @log_method_entry_exit(level="DEBUG")
    def list_all(
        self,
        ctx: "TravelContext",
        status: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[List["Itinerary"], int]:
        """
        List itineraries with optional filtering.
        
        Args:
            ctx: TravelContext with session
            status: Filter by status
            page: Page number
            limit: Items per page
        
        Returns:
            Tuple of (list of itineraries, total count)
        """
        repo = _get_repository(ctx.session)
        
        itineraries, total = repo.list_all(
            status=status,
            traveler_id=ctx.traveler_id if ctx.traveler_id else None,
            page=page,
            limit=limit,
        )
        
        logger.info(f"Listed itineraries: {len(itineraries)} of {total} total")
        return itineraries, total
    
    # =========================================================================
    # Legacy Execute Method (for backward compatibility)
    # =========================================================================
    
    @log_method_entry_exit(level="DEBUG")
    def execute(self, task: str, params: Dict[str, Any], ctx: Optional["TravelContext"] = None) -> Any:
        """
        Execute itinerary management task.
        
        For context-aware operations, use the specific methods (build, get, update, etc.) directly.
        
        Args:
            task: Task name to execute
            params: Task parameters
            ctx: Optional TravelContext
        
        Returns:
            Task result
        """
        logger.debug(f"ItineraryAgent executing task: {task}")
        
        # Context-aware operations
        if ctx is not None:
            if task == 'build_itinerary':
                return self.build(
                    flight_reservation=params.get('flight_reservation'),
                    hotel_reservation=params.get('hotel_reservation'),
                    car_reservation=params.get('car_reservation'),
                    ctx=ctx
                )
            elif task == 'get_itinerary':
                return self.get(ctx)
            elif task == 'confirm_itinerary':
                return self.confirm(ctx)
            elif task == 'cancel_itinerary':
                return self.cancel(ctx)
        
        # Fallback for tool-based execution
        if task in self.tools:
            return self._call_tool(task, params)
        
        # Use LLM routing if available
        if self.llm:
            logger.debug(f"Task '{task}' not found, using LLM routing")
            return self._llm_route_task(task, params, ctx)
        
        logger.warning(f"Unknown task '{task}' for ItineraryAgent")
        return {"error": f"Unknown task '{task}' for ItineraryAgent"}
    
    @log_method_entry_exit(level="DEBUG")
    def _llm_route_task(self, task: str, params: Dict[str, Any], ctx: Optional["TravelContext"] = None) -> Dict[str, Any]:
        """Use LLM to route ambiguous tasks to appropriate tools - prompt from prompts.yaml"""
        display_params = {k: v for k, v in params.items() if not k.startswith('_')}
        available_tools = ", ".join(self.get_available_tools())
        
        # Get prompt from prompts.yaml via model_strategy
        if ctx and ctx.model_strategy:
            try:
                prompt = ctx.model_strategy.get_prompt_for_use_case(
                    UseCase.TASK_ROUTING,
                    agent_name="Itinerary Management Agent",
                    available_tools=available_tools,
                    task=task,
                    params=display_params
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
        
        logger.debug(f"Using LLM to route task '{task}' to appropriate tool")
        tool_name = self.llm.invoke(prompt).strip()
        logger.debug(f"LLM suggested tool: {tool_name}")
        
        if tool_name in self.tools:
            return self._call_tool(tool_name, params)
        else:
            logger.warning(f"LLM suggested unknown tool '{tool_name}'")
            return {"error": f"LLM suggested unknown tool '{tool_name}'"}


# =============================================================================
# Utility function for converting itinerary to dict
# =============================================================================

def itinerary_to_dict(itinerary: "Itinerary") -> Dict[str, Any]:
    """Public helper to convert Itinerary model to dictionary."""
    return _itinerary_to_dict(itinerary)
