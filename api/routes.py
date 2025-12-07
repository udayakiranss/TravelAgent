"""
API routes for the Travel Booking Web Application.
All endpoints are prefixed with /api/v1 for versioning.
"""
import os
import asyncio
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from api.config import SelectionCriteria, DEFAULT_SELECTION_CRITERIA

from api.schemas import (
    # Request models
    ItineraryCreateRequest,
    ItineraryUpdateRequest,
    NaturalLanguageQueryRequest,
    NaturalLanguageModifyRequest,
    # Response models
    ItineraryResponse,
    ItineraryListResponse,
    ItineraryStatusResponse,
    ItineraryDeleteResponse,
    PlanResponse,
    ModifyResponse,
    HealthResponse,
    ErrorResponse,
)
from api.dependencies import get_db, get_llm, get_orchestrator
from database.repository import (
    ItineraryRepository,
    ChatHistoryRepository,
    ItineraryNotFoundError,
    VersionConflictError,
    InvalidStatusTransitionError,
)
from database.models import Itinerary
from agents.llm_provider import LLMProvider
from agents.orchestrator import Orchestrator
from utils.logger import get_logger, log_method_entry_exit

# Initialize logger
logger = get_logger()

# Create router with /api/v1 prefix
router = APIRouter(prefix="/api/v1", tags=["Travel Booking API"])


# =============================================================================
# Helper Functions
# =============================================================================

def itinerary_to_response(itinerary: Itinerary) -> ItineraryResponse:
    """Convert database model to response schema."""
    return ItineraryResponse(
        id=itinerary.id,
        traveler_id=itinerary.traveler_id,
        original_query=itinerary.original_query,
        status=itinerary.status,
        flight_data=itinerary.flight_data,
        hotel_data=itinerary.hotel_data,
        car_data=itinerary.car_data,
        total_cost=itinerary.total_cost,
        version=itinerary.version,
        created_at=itinerary.created_at,
        updated_at=itinerary.updated_at,
        cancelled_at=itinerary.cancelled_at,
    )


def create_error_response(
    error_code: str,
    message: str,
    status_code: int,
    details: dict = None
) -> dict:
    """Create standardized error response dict."""
    return {
        "error": error_code,
        "message": message,
        "status_code": status_code,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "details": details,
    }


def select_best_option(
    options: List[Dict[str, Any]], 
    criteria: SelectionCriteria
) -> Optional[Dict[str, Any]]:
    """
    Select best option from list based on criteria.
    
    Args:
        options: List of travel options (flights, hotels, or cars)
        criteria: Selection criteria to apply
        
    Returns:
        The best option based on criteria, or None if no options available
    """
    if not options:
        return None
    
    if criteria == SelectionCriteria.FIRST_AVAILABLE:
        return options[0]
    
    elif criteria == SelectionCriteria.CHEAPEST:
        # Look for 'price' or 'total_price' field
        def get_price(opt: Dict[str, Any]) -> float:
            return opt.get("price") or opt.get("total_price") or float("inf")
        return min(options, key=get_price)
    
    elif criteria == SelectionCriteria.BEST_RATED:
        # Look for 'rating' or 'score' field, fallback to first
        def get_rating(opt: Dict[str, Any]) -> float:
            return opt.get("rating") or opt.get("score") or 0
        return max(options, key=get_rating)
    
    return options[0]  # fallback


# =============================================================================
# Health Check
# =============================================================================

@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Check API, database, and LLM status"
)
def health_check(
    db: Session = Depends(get_db),
    llm: Optional[LLMProvider] = Depends(get_llm),
):
    """Health check endpoint."""
    logger.debug("Health check requested")
    
    # Check database
    db_status = "connected"
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = "error"
        logger.error(f"Database health check failed: {e}")
    
    # Check LLM
    llm_status = "available" if llm else "unavailable"
    
    # Overall status
    overall = "healthy"
    if db_status == "error":
        overall = "unhealthy"
    elif llm_status == "unavailable":
        overall = "degraded"
    
    logger.info(f"Health check: status={overall}, db={db_status}, llm={llm_status}")
    
    return HealthResponse(
        status=overall,
        database=db_status,
        llm=llm_status,
    )


# =============================================================================
# Itinerary CRUD Operations
# =============================================================================

@router.post(
    "/itineraries",
    response_model=ItineraryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create itinerary",
    description="Create a new itinerary in draft status"
)
def create_itinerary(
    request: ItineraryCreateRequest,
    db: Session = Depends(get_db),
):
    """Create a new draft itinerary."""
    logger.info(f"Creating itinerary for traveler_id={request.traveler_id}")
    
    repo = ItineraryRepository(db)
    
    itinerary = repo.create(
        traveler_id=request.traveler_id,
        original_query=request.original_query,
    )
    
    logger.info(f"Created itinerary id={itinerary.id}")
    return itinerary_to_response(itinerary)


@router.get(
    "/itineraries",
    response_model=ItineraryListResponse,
    summary="List itineraries",
    description="List itineraries with optional filtering and pagination"
)
def list_itineraries(
    status: Optional[str] = Query(None, description="Filter by status: draft, confirmed, cancelled"),
    traveler_id: Optional[str] = Query(None, description="Filter by traveler ID"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    """List itineraries with pagination."""
    logger.debug(f"Listing itineraries: status={status}, traveler_id={traveler_id}, page={page}, limit={limit}")
    
    repo = ItineraryRepository(db)
    
    itineraries, total = repo.list_all(
        status=status,
        traveler_id=traveler_id,
        page=page,
        limit=limit,
    )
    
    logger.info(f"Listed itineraries: returned {len(itineraries)} of {total} total")
    
    return ItineraryListResponse(
        items=[itinerary_to_response(it) for it in itineraries],
        total=total,
        page=page,
        limit=limit,
        has_more=(page * limit) < total,
    )


@router.get(
    "/itineraries/{itinerary_id}",
    response_model=ItineraryResponse,
    summary="Get itinerary",
    description="Get itinerary details by ID"
)
def get_itinerary(
    itinerary_id: str,
    db: Session = Depends(get_db),
):
    """Get itinerary by ID."""
    logger.debug(f"Getting itinerary id={itinerary_id}")
    
    repo = ItineraryRepository(db)
    
    try:
        itinerary = repo.get_by_id_or_raise(itinerary_id)
        logger.debug(f"Found itinerary id={itinerary_id}, status={itinerary.status}")
        return itinerary_to_response(itinerary)
    except ItineraryNotFoundError:
        logger.warning(f"Itinerary not found: id={itinerary_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                "ITINERARY_NOT_FOUND",
                f"Itinerary with id '{itinerary_id}' does not exist",
                404
            )
        )


@router.put(
    "/itineraries/{itinerary_id}",
    response_model=ItineraryResponse,
    summary="Update itinerary",
    description="Update itinerary with optimistic locking"
)
def update_itinerary(
    itinerary_id: str,
    request: ItineraryUpdateRequest,
    db: Session = Depends(get_db),
):
    """Update itinerary with optimistic locking."""
    logger.info(f"Updating itinerary id={itinerary_id}, version={request.version}")
    
    repo = ItineraryRepository(db)
    
    try:
        # Build update kwargs - use ... as sentinel for "not provided"
        kwargs = {
            "itinerary_id": itinerary_id,
            "version": request.version,
        }
        
        # Only include fields that were explicitly provided in request
        if request.flight_data is not None or "flight_data" in request.model_fields_set:
            kwargs["flight_data"] = request.flight_data
        if request.hotel_data is not None or "hotel_data" in request.model_fields_set:
            kwargs["hotel_data"] = request.hotel_data
        if request.car_data is not None or "car_data" in request.model_fields_set:
            kwargs["car_data"] = request.car_data
        
        logger.debug(f"Update fields: {list(kwargs.keys())}")
        
        itinerary = repo.update(**kwargs)
        logger.info(f"Updated itinerary id={itinerary_id}, new_version={itinerary.version}")
        return itinerary_to_response(itinerary)
        
    except ItineraryNotFoundError:
        logger.warning(f"Update failed - itinerary not found: id={itinerary_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                "ITINERARY_NOT_FOUND",
                f"Itinerary with id '{itinerary_id}' does not exist",
                404
            )
        )
    except VersionConflictError as e:
        logger.warning(f"Version conflict on itinerary id={itinerary_id}: expected={e.expected_version}, current={e.current_version}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=create_error_response(
                "VERSION_CONFLICT",
                f"Itinerary was modified. Expected version {e.expected_version}, found {e.current_version}",
                409,
                {"current_version": e.current_version}
            )
        )
    except InvalidStatusTransitionError as e:
        logger.warning(f"Cannot modify itinerary id={itinerary_id} in status={e.current_status}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                "CANNOT_MODIFY_CONFIRMED",
                f"Cannot modify itinerary in '{e.current_status}' status",
                400
            )
        )


@router.delete(
    "/itineraries/{itinerary_id}",
    response_model=ItineraryDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete itinerary",
    description="Delete a draft itinerary permanently"
)
def delete_itinerary(
    itinerary_id: str,
    db: Session = Depends(get_db),
):
    """Delete a draft itinerary."""
    logger.info(f"Deleting itinerary id={itinerary_id}")
    
    repo = ItineraryRepository(db)
    
    try:
        repo.delete(itinerary_id)
        logger.info(f"Deleted itinerary id={itinerary_id}")
        return ItineraryDeleteResponse(
            success=True,
            message=f"Itinerary {itinerary_id} deleted successfully"
        )
    except ItineraryNotFoundError:
        logger.warning(f"Delete failed - itinerary not found: id={itinerary_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                "ITINERARY_NOT_FOUND",
                f"Itinerary with id '{itinerary_id}' does not exist",
                404
            )
        )
    except InvalidStatusTransitionError as e:
        logger.warning(f"Cannot delete itinerary id={itinerary_id} in status={e.current_status}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                "CANNOT_DELETE_CONFIRMED",
                f"Cannot delete itinerary in '{e.current_status}' status. Only drafts can be deleted.",
                400
            )
        )


# =============================================================================
# Status Management
# =============================================================================

@router.post(
    "/itineraries/{itinerary_id}/confirm",
    response_model=ItineraryStatusResponse,
    summary="Confirm itinerary",
    description="Confirm a draft itinerary (locks from further edits)"
)
def confirm_itinerary(
    itinerary_id: str,
    db: Session = Depends(get_db),
):
    """Confirm a draft itinerary."""
    logger.info(f"Confirming itinerary id={itinerary_id}")
    
    repo = ItineraryRepository(db)
    
    try:
        itinerary = repo.confirm(itinerary_id)
        logger.info(f"Confirmed itinerary id={itinerary_id}")
        return ItineraryStatusResponse(
            id=itinerary.id,
            status=itinerary.status,
            message="Itinerary confirmed successfully"
        )
    except ItineraryNotFoundError:
        logger.warning(f"Confirm failed - itinerary not found: id={itinerary_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                "ITINERARY_NOT_FOUND",
                f"Itinerary with id '{itinerary_id}' does not exist",
                404
            )
        )
    except InvalidStatusTransitionError as e:
        logger.warning(f"Cannot confirm itinerary id={itinerary_id} in status={e.current_status}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                "INVALID_STATUS_TRANSITION",
                f"Cannot confirm itinerary in '{e.current_status}' status. Only drafts can be confirmed.",
                400
            )
        )


@router.post(
    "/itineraries/{itinerary_id}/cancel",
    response_model=ItineraryStatusResponse,
    summary="Cancel itinerary",
    description="Cancel an itinerary (draft or confirmed)"
)
def cancel_itinerary(
    itinerary_id: str,
    db: Session = Depends(get_db),
):
    """Cancel an itinerary."""
    logger.info(f"Cancelling itinerary id={itinerary_id}")
    
    repo = ItineraryRepository(db)
    
    try:
        itinerary = repo.cancel(itinerary_id)
        logger.info(f"Cancelled itinerary id={itinerary_id}")
        return ItineraryStatusResponse(
            id=itinerary.id,
            status=itinerary.status,
            message="Itinerary cancelled successfully",
            cancelled_at=itinerary.cancelled_at
        )
    except ItineraryNotFoundError:
        logger.warning(f"Cancel failed - itinerary not found: id={itinerary_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                "ITINERARY_NOT_FOUND",
                f"Itinerary with id '{itinerary_id}' does not exist",
                404
            )
        )
    except InvalidStatusTransitionError as e:
        logger.warning(f"Cannot cancel itinerary id={itinerary_id} in status={e.current_status}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                "INVALID_STATUS_TRANSITION",
                f"Cannot cancel itinerary in '{e.current_status}' status. Already cancelled.",
                400
            )
        )


# =============================================================================
# LLM Operations
# =============================================================================

# Timeout for LLM operations (in seconds)
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "60"))


@router.post(
    "/agent/plan",
    response_model=PlanResponse,
    summary="Plan trip",
    description="Generate travel options, auto-select best option, and create draft itinerary"
)
def plan_trip(
    request: NaturalLanguageQueryRequest,
    db: Session = Depends(get_db),
    llm: Optional[LLMProvider] = Depends(get_llm),
):
    """
    Generate travel options from natural language query.
    Creates a draft itinerary with auto-selected options based on criteria.
    Returns itinerary_id for subsequent modifications or confirmation.
    """
    logger.info(f"Plan trip request: query='{request.query[:50]}...'" if len(request.query) > 50 else f"Plan trip request: query='{request.query}'")
    logger.info(f"Traveler: {request.traveler_id}, Criteria: {request.selection_criteria}, Include summary: {request.include_summary}")
    
    if llm is None:
        from api.dependencies import get_expected_api_key_name, get_llm_provider_name
        api_key_name = get_expected_api_key_name()
        provider = get_llm_provider_name()
        logger.error(f"LLM service unavailable - {api_key_name} not set for provider '{provider}'")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=create_error_response(
                "LLM_UNAVAILABLE",
                f"LLM service is not available. Set {api_key_name} environment variable.",
                503
            )
        )
    
    try:
        # Create orchestrator and parse intent
        logger.debug("Creating orchestrator and parsing intent")
        orchestrator = Orchestrator(llm=llm, memory=None)
        
        # Parse the query to get intent
        from main import interpret_nl_with_llm
        intent = interpret_nl_with_llm(request.query, llm)
        logger.debug(f"Parsed intent: {intent}")
        
        # Run the orchestrator to get results
        logger.info("Running orchestrator for trip planning")
        results = orchestrator.run_intent(intent)
        
        # Extract options from results
        flight_options = []
        hotel_options = []
        car_options = []
        
        for key, value in results.items():
            if 'FlightBookingAgent' in key and isinstance(value, (list, dict)):
                if isinstance(value, list):
                    flight_options.extend(value)
                else:
                    flight_options.append(value)
            elif 'HotelBookingAgent' in key and isinstance(value, (list, dict)):
                if isinstance(value, list):
                    hotel_options.extend(value)
                else:
                    hotel_options.append(value)
            elif 'CarRentalAgent' in key and isinstance(value, (list, dict)):
                if isinstance(value, list):
                    car_options.extend(value)
                else:
                    car_options.append(value)
        
        logger.info(f"Found options: {len(flight_options)} flights, {len(hotel_options)} hotels, {len(car_options)} cars")
        
        # Determine selection criteria (use request value or fall back to default)
        criteria = request.selection_criteria or DEFAULT_SELECTION_CRITERIA
        logger.debug(f"Using selection criteria: {criteria}")
        
        # Auto-select best options based on criteria
        selected_flight = select_best_option(flight_options, criteria)
        selected_hotel = select_best_option(hotel_options, criteria)
        selected_car = select_best_option(car_options, criteria)
        
        logger.info(f"Auto-selected: flight={selected_flight is not None}, hotel={selected_hotel is not None}, car={selected_car is not None}")
        
        # Create draft itinerary with selected options
        repo = ItineraryRepository(db)
        itinerary = repo.create(
            traveler_id=request.traveler_id,
            original_query=request.query,
            flight_data=selected_flight,
            hotel_data=selected_hotel,
            car_data=selected_car,
        )
        
        logger.info(f"Created draft itinerary: id={itinerary.id}")
        
        # Generate summary using ResponseFormatter if requested
        summary = None
        if request.include_summary:
            try:
                from agents.response_formatter import ResponseFormatter
                formatter = ResponseFormatter(llm=llm)
                summary = formatter.format_results(
                    results={
                        "flight": selected_flight,
                        "hotel": selected_hotel,
                        "car": selected_car,
                    },
                    intent=intent
                )
                logger.debug("Generated summary via ResponseFormatter")
            except Exception as e:
                logger.warning(f"Failed to generate summary: {e}")
                summary = f"Found {len(flight_options)} flights, {len(hotel_options)} hotels, {len(car_options)} cars"
        else:
            summary = f"Found {len(flight_options)} flights, {len(hotel_options)} hotels, {len(car_options)} cars"
        
        logger.info(f"Plan trip completed: itinerary_id={itinerary.id}")
        
        return PlanResponse(
            itinerary_id=itinerary.id,
            flight_options=flight_options,
            hotel_options=hotel_options,
            car_options=car_options,
            selected_flight=selected_flight,
            selected_hotel=selected_hotel,
            selected_car=selected_car,
            selection_criteria_used=criteria.value,
            summary=summary,
            query=request.query
        )
        
    except Exception as e:
        logger.error(f"Plan trip failed: {type(e).__name__}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response(
                "PLANNING_ERROR",
                f"Error during trip planning: {str(e)}",
                500
            )
        )


@router.post(
    "/itineraries/{itinerary_id}/modify",
    response_model=ModifyResponse,
    summary="Modify via NL",
    description="Modify itinerary via natural language instruction"
)
def modify_itinerary_nl(
    itinerary_id: str,
    request: NaturalLanguageModifyRequest,
    db: Session = Depends(get_db),
    llm: Optional[LLMProvider] = Depends(get_llm),
):
    """
    Modify an itinerary using natural language instructions.
    Uses LLM to interpret the instruction and update relevant components.
    """
    logger.info(f"Modify itinerary request: id={itinerary_id}, instruction='{request.instruction[:50]}...'" if len(request.instruction) > 50 else f"Modify itinerary request: id={itinerary_id}, instruction='{request.instruction}'")
    
    if llm is None:
        from api.dependencies import get_expected_api_key_name, get_llm_provider_name
        api_key_name = get_expected_api_key_name()
        provider = get_llm_provider_name()
        logger.error(f"LLM service unavailable - {api_key_name} not set for provider '{provider}'")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=create_error_response(
                "LLM_UNAVAILABLE",
                f"LLM service is not available. Set {api_key_name} environment variable.",
                503
            )
        )
    
    # Get current itinerary
    repo = ItineraryRepository(db)
    chat_repo = ChatHistoryRepository(db)
    
    try:
        itinerary = repo.get_by_id_or_raise(itinerary_id)
    except ItineraryNotFoundError:
        logger.warning(f"Modify failed - itinerary not found: id={itinerary_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                "ITINERARY_NOT_FOUND",
                f"Itinerary with id '{itinerary_id}' does not exist",
                404
            )
        )
    
    if itinerary.status != "draft":
        logger.warning(f"Cannot modify itinerary id={itinerary_id} in status={itinerary.status}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                "CANNOT_MODIFY_CONFIRMED",
                f"Cannot modify itinerary in '{itinerary.status}' status",
                400
            )
        )
    
    try:
        # Get chat history for context
        logger.debug(f"Getting chat history for itinerary id={itinerary_id}")
        chat_history = chat_repo.get_history(itinerary_id, limit=10)
        
        # Build context for LLM
        current_state = {
            "flight": itinerary.flight_data,
            "hotel": itinerary.hotel_data,
            "car": itinerary.car_data,
            "total_cost": itinerary.total_cost,
        }
        
        # Create prompt for LLM to determine what to modify
        history_text = "\n".join([f"{m.role}: {m.content}" for m in chat_history])
        
        modification_prompt = f"""You are a travel agent assistant. Based on the current itinerary state and user instruction, determine what needs to be modified.

Current Itinerary State:
{current_state}

Previous Conversation:
{history_text}

User Instruction: {request.instruction}

Analyze the instruction and respond with a JSON object containing:
- "component": which component to modify ("flight", "hotel", or "car")
- "action": what action to take ("search_new", "remove", "update")
- "parameters": any search parameters extracted from the instruction

Respond with ONLY the JSON object."""

        # Get LLM response
        logger.debug("Invoking LLM for modification analysis")
        llm_response = llm.invoke(modification_prompt)
        logger.debug(f"LLM response received")
        
        # Save chat messages
        chat_repo.add_message(itinerary_id, "user", request.instruction)
        
        # For now, return a simplified response
        # Full implementation would parse LLM response and call appropriate agents
        chat_repo.add_message(
            itinerary_id, 
            "assistant", 
            f"Processing modification request: {request.instruction}"
        )
        
        # Refresh itinerary
        db.refresh(itinerary)
        
        logger.info(f"Modification request processed for itinerary id={itinerary_id}")
        
        return ModifyResponse(
            success=True,
            updated_itinerary=itinerary_to_response(itinerary),
            message=f"Modification request received: {request.instruction}. Full LLM modification implementation pending.",
            partial=False
        )
        
    except Exception as e:
        logger.error(f"Modification failed for itinerary id={itinerary_id}: {type(e).__name__}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=create_error_response(
                "MODIFICATION_ERROR",
                f"Error during modification: {str(e)}",
                500
            )
        )

