"""
Planning service for natural language trip planning operations.
Handles plan creation, execution, and response building.
"""
from typing import TYPE_CHECKING, Dict, Any, Union
from fastapi.responses import JSONResponse
from fastapi import status

from api.schemas import PlanResponse, NaturalLanguageQueryRequest
from api.config import DEFAULT_SELECTION_CRITERIA
from agents.planning import TravelPlanner
from agents.orchestration import Orchestrator
from database.repository import LLMUnavailableError, UserPreferencesRepository
from api.utils import create_error_response
from utils.logger import get_logger

if TYPE_CHECKING:
    from api.context import TravelContext

logger = get_logger()


class PlanningService:
    """Service for trip planning operations."""
    
    def __init__(self, planner: TravelPlanner, orchestrator: Orchestrator):
        """
        Initialize planning service.
        
        Args:
            planner: TravelPlanner instance
            orchestrator: Orchestrator instance
        """
        self.planner = planner
        self.orchestrator = orchestrator
    
    def plan_trip(
        self,
        request: NaturalLanguageQueryRequest,
        ctx: "TravelContext",
    ) -> Union[PlanResponse, JSONResponse]:
        """
        Plan a trip from natural language query.
        
        Handles:
        - Plan creation from NL query
        - Clarification handling
        - Plan execution
        - Response building
        
        Args:
            request: NaturalLanguageQueryRequest with query and traveler info
            ctx: TravelContext (will be populated with request data)
        
        Returns:
            PlanResponse with results, or JSONResponse for clarification needed
        
        Raises:
            LLMUnavailableError: If LLM is required but unavailable
        """
        logger.info(
            f"Plan trip request",
            extra={
                "query_preview": request.query[:50] + "..." if len(request.query) > 50 else request.query,
                "traveler_id": request.traveler_id,
            },
        )
        
        # Populate context from request
        ctx.traveler_id = request.traveler_id
        ctx.criteria = request.selection_criteria or DEFAULT_SELECTION_CRITERIA
        ctx.original_query = request.query
        
        # Load user preferences summary for personalization
        try:
            pref_repo = UserPreferencesRepository(ctx.session)
            ctx.preference_summary = pref_repo.get_summary(ctx.traveler_id)
            logger.debug(f"Loaded preference summary for {ctx.traveler_id}: {ctx.preference_summary[:50]}..." if ctx.preference_summary else "No preferences found")
        except Exception as e:
            logger.warning(f"Failed to load preferences for {ctx.traveler_id}: {e}")
            ctx.preference_summary = "No preferences set for this traveler"
        
        logger.info(f"Planning service: traveler={ctx.traveler_id}, criteria={ctx.criteria.value}")
        
        # Step 1: Create plan from NL query (Planner handles NL parsing + validation)
        plan = self.planner.create_plan_from_query(request.query, ctx)
        
        # Handle clarification path from deterministic planner
        if plan.status == "needs_clarification":
            logger.info(
                "Plan requires clarification",
                extra={
                    "plan_id": plan.plan_metadata.plan_id,
                    "missing_fields": [mi.field for mi in plan.missing_info],
                },
            )
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "code": "MISSING_INFORMATION",
                    "message": "Additional information required to plan the trip.",
                    "missing_info": [mi.model_dump() for mi in plan.missing_info],
                    "plan_id": plan.plan_metadata.plan_id,
                    "query": request.query,
                },
            )
        
        # Step 2: Execute plan (Orchestrator runs agents and creates itinerary)
        logger.info(
            f"Planning service: Executing plan",
            extra={"plan_id": plan.plan_metadata.plan_id, "task_count": len(plan.tasks)},
        )
        result = self.orchestrator.execute_plan(plan, ctx, include_summary=request.include_summary)
        
        itinerary_id = result.get("itinerary_id")
        logger.info(f"Planning service: Plan trip completed, itinerary_id={itinerary_id}")
        
        # Build response
        return self._build_plan_response(result, ctx, request.query, itinerary_id)
    
    def _build_plan_response(
        self,
        result: Dict[str, Any],
        ctx: "TravelContext",
        query: str,
        itinerary_id: str,
    ) -> PlanResponse:
        """
        Build PlanResponse from orchestrator result.
        
        Handles both successful and partial results (when itinerary wasn't created).
        
        Args:
            result: Result dict from orchestrator.execute_plan()
            ctx: TravelContext with criteria
            query: Original query string
            itinerary_id: Created itinerary ID (may be None)
        
        Returns:
            PlanResponse with all results
        """
        # Handle case where itinerary wasn't built - return partial results with warning
        if itinerary_id is None:
            logger.warning("Plan execution completed but no itinerary was created")
            return PlanResponse(
                itinerary_id=None,
                flight_options=result.get("flight_options", []),
                hotel_options=result.get("hotel_options", []),
                car_options=result.get("car_options", []),
                flight_reservation=result.get("flight_reservation"),
                hotel_reservation=result.get("hotel_reservation"),
                car_reservation=result.get("car_reservation"),
                selection_criteria_used=result.get("selection_criteria_used", ctx.criteria.value),
                preference_summary=result.get("preference_summary"),
                summary=result.get("summary", "Plan execution completed but no itinerary was created. Missing itinerary task in plan."),
                query=query
            )
        
        # Normal successful response
        return PlanResponse(
            itinerary_id=itinerary_id,
            flight_options=result.get("flight_options", []),
            hotel_options=result.get("hotel_options", []),
            car_options=result.get("car_options", []),
            flight_reservation=result.get("flight_reservation"),
            hotel_reservation=result.get("hotel_reservation"),
            car_reservation=result.get("car_reservation"),
            selection_criteria_used=result.get("selection_criteria_used", ctx.criteria.value),
            preference_summary=result.get("preference_summary"),
            summary=result.get("summary", ""),
            query=query
        )
