"""
API routes for the Travel Booking Web Application.
All endpoints are prefixed with /api/v1 for versioning.

Routes are thin HTTP controllers that delegate to the Orchestrator.
Business logic lives in Orchestrator and Agents (per DD-1, DD-2).
"""
import os
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from api.config import SelectionCriteria, DEFAULT_SELECTION_CRITERIA
from api.context import TravelContext
from api.schemas import (
    # Request models
    ItineraryCreateRequest,
    ItineraryUpdateRequest,
    NaturalLanguageQueryRequest,
    NaturalLanguageModifyRequest,
    UserPreferencesCreateRequest,
    FlightSearchRequest,
    HotelSearchRequest,
    CarSearchRequest,
    # Response models
    ItineraryResponse,
    ItineraryListResponse,
    ItineraryStatusResponse,
    ItineraryDeleteResponse,
    PlanResponse,
    ModifyResponse,
    HealthResponse,
    UserPreferencesResponse,
    UserPreferencesDeleteResponse,
    ChatHistoryResponse,
    FlightOption,
    HotelOption,
    CarOption,
)
from api.dependencies import get_db, get_llm, get_context, get_orchestrator
from database.repository import (
    TravelItineraryRepository,
    ChatMessageRepository,
    UserPreferencesRepository,
    ItineraryNotFoundError,
    VersionConflictError,
    InvalidStatusTransitionError,
    LLMUnavailableError,
    PreferencesNotFoundError,
)
from database.models import Itinerary
from agents.llm_provider import LLMProvider
from agents.orchestrator import Orchestrator
from utils.logger import get_logger
from tools.search_tools import search_flights as tool_search_flights
from tools.search_tools import search_hotels as tool_search_hotels
from tools.search_tools import search_cars as tool_search_cars

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
        flight_reservation=itinerary.flight_reservation,
        hotel_reservation=itinerary.hotel_reservation,
        car_reservation=itinerary.car_reservation,
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


def handle_domain_exception(e: Exception):
    """Convert domain exceptions to HTTP exceptions (DD-7)."""
    if isinstance(e, ItineraryNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                "ITINERARY_NOT_FOUND",
                f"Itinerary with id '{e.itinerary_id}' does not exist",
                404
            )
        )
    elif isinstance(e, VersionConflictError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=create_error_response(
                "VERSION_CONFLICT",
                f"Itinerary was modified. Expected version {e.expected_version}, found {e.current_version}",
                409,
                {"current_version": e.current_version}
            )
        )
    elif isinstance(e, InvalidStatusTransitionError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                "INVALID_STATUS_TRANSITION",
                f"Cannot transition from '{e.current_status}' to '{e.target_status}'",
                400
            )
        )
    elif isinstance(e, LLMUnavailableError):
        from api.dependencies import get_expected_api_key_name, get_llm_provider_name
        api_key_name = get_expected_api_key_name()
        provider = get_llm_provider_name()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=create_error_response(
                "LLM_UNAVAILABLE",
                f"LLM service is not available. Set {api_key_name} environment variable.",
                503
            )
        )
    else:
        raise


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
# Search Operations (New)
# =============================================================================

@router.post(
    "/search/flights",
    response_model=List[Dict[str, Any]],
    summary="Search flights",
    description="Search for available flights. Use airport codes (BLR, DXB) and dates (YYYY-MM-DD)."
)
def search_flights(request: FlightSearchRequest):
    """Search for flights without creating an itinerary."""
    logger.info(f"Searching flights: {request.origin} -> {request.destination} on {request.date}")
    try:
        # LangChain tool expects {"query": {...}} format
        results = tool_search_flights.invoke({
            "query": {
                "from": request.origin,
                "to": request.destination,
                "date": request.date
            }
        })
        logger.info(f"Flight search returned {len(results)} results")
        return results
    except Exception as e:
        logger.error(f"Flight search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/search/hotels",
    response_model=List[Dict[str, Any]],
    summary="Search hotels",
    description="Search for available hotels. Use city codes (DXB, LON, NYC)."
)
def search_hotels(request: HotelSearchRequest):
    """Search for hotels without creating an itinerary."""
    logger.info(f"Searching hotels in: {request.city}")
    try:
        # LangChain tool expects {"query": {...}} format
        results = tool_search_hotels.invoke({"query": {"city": request.city}})
        logger.info(f"Hotel search returned {len(results)} results")
        return results
    except Exception as e:
        logger.error(f"Hotel search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/search/cars",
    response_model=List[Dict[str, Any]],
    summary="Search cars",
    description="Search for available car rentals. Use city codes (DXB, LON, NYC)."
)
def search_cars(request: CarSearchRequest):
    """Search for car rentals without creating an itinerary."""
    logger.info(f"Searching cars in: {request.city}")
    try:
        # LangChain tool expects {"query": {...}} format
        results = tool_search_cars.invoke({"query": {"city": request.city}})
        logger.info(f"Car search returned {len(results)} results")
        return results
    except Exception as e:
        logger.error(f"Car search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
    
    repo = TravelItineraryRepository(db)
    
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
    
    repo = TravelItineraryRepository(db)
    
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
    
    repo = TravelItineraryRepository(db)
    
    try:
        itinerary = repo.get_by_id_or_raise(itinerary_id)
        logger.debug(f"Found itinerary id={itinerary_id}, status={itinerary.status}")
        return itinerary_to_response(itinerary)
    except ItineraryNotFoundError as e:
        handle_domain_exception(e)


@router.get(
    "/itineraries/{itinerary_id}/history",
    response_model=ChatHistoryResponse,
    summary="Get chat history",
    description="Get chat history for an itinerary"
)
def get_itinerary_history(
    itinerary_id: str,
    limit: int = Query(20, ge=1, le=100, description="Number of messages to return"),
    db: Session = Depends(get_db),
):
    """Get chat history for an itinerary."""
    logger.debug(f"Getting history for itinerary id={itinerary_id}")
    
    # Check if itinerary exists first
    repo = TravelItineraryRepository(db)
    if not repo.get_by_id(itinerary_id):
        raise HTTPException(
            status_code=404,
            detail=create_error_response("ITINERARY_NOT_FOUND", f"Itinerary {itinerary_id} not found", 404)
        )
    
    chat_repo = ChatMessageRepository(db)
    messages = chat_repo.get_history(itinerary_id, limit=limit)
    
    return ChatHistoryResponse(
        itinerary_id=itinerary_id,
        messages=messages
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
    
    repo = TravelItineraryRepository(db)
    
    try:
        # Build update kwargs - use ... as sentinel for "not provided"
        kwargs = {
            "itinerary_id": itinerary_id,
            "version": request.version,
        }
        
        # Only include fields that were explicitly provided in request
        if request.flight_reservation is not None or "flight_reservation" in request.model_fields_set:
            kwargs["flight_reservation"] = request.flight_reservation
        if request.hotel_reservation is not None or "hotel_reservation" in request.model_fields_set:
            kwargs["hotel_reservation"] = request.hotel_reservation
        if request.car_reservation is not None or "car_reservation" in request.model_fields_set:
            kwargs["car_reservation"] = request.car_reservation
        
        logger.debug(f"Update fields: {list(kwargs.keys())}")
        
        itinerary = repo.update(**kwargs)
        logger.info(f"Updated itinerary id={itinerary_id}, new_version={itinerary.version}")
        return itinerary_to_response(itinerary)
        
    except (ItineraryNotFoundError, VersionConflictError, InvalidStatusTransitionError) as e:
        handle_domain_exception(e)


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
    
    repo = TravelItineraryRepository(db)
    
    try:
        repo.delete(itinerary_id)
        logger.info(f"Deleted itinerary id={itinerary_id}")
        return ItineraryDeleteResponse(
            success=True,
            message=f"Itinerary {itinerary_id} deleted successfully"
        )
    except (ItineraryNotFoundError, InvalidStatusTransitionError) as e:
        handle_domain_exception(e)


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
    ctx: TravelContext = Depends(get_context),
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    """Confirm a draft itinerary."""
    logger.info(f"Confirming itinerary id={itinerary_id}")
    
    # Set up context
    ctx.itinerary_id = itinerary_id
    
    try:
        itinerary = orchestrator.confirm_itinerary(ctx)
        logger.info(f"Confirmed itinerary id={itinerary_id}")
        return ItineraryStatusResponse(
            id=itinerary.id,
            status=itinerary.status,
            message="Itinerary confirmed successfully"
        )
    except (ItineraryNotFoundError, InvalidStatusTransitionError) as e:
        handle_domain_exception(e)


@router.post(
    "/itineraries/{itinerary_id}/cancel",
    response_model=ItineraryStatusResponse,
    summary="Cancel itinerary",
    description="Cancel an itinerary (draft or confirmed)"
)
def cancel_itinerary(
    itinerary_id: str,
    ctx: TravelContext = Depends(get_context),
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    """Cancel an itinerary."""
    logger.info(f"Cancelling itinerary id={itinerary_id}")
    
    # Set up context
    ctx.itinerary_id = itinerary_id
    
    try:
        itinerary = orchestrator.cancel_itinerary(ctx)
        logger.info(f"Cancelled itinerary id={itinerary_id}")
        return ItineraryStatusResponse(
            id=itinerary.id,
            status=itinerary.status,
            message="Itinerary cancelled successfully",
            cancelled_at=itinerary.cancelled_at
        )
    except (ItineraryNotFoundError, InvalidStatusTransitionError) as e:
        handle_domain_exception(e)


# =============================================================================
# LLM Operations (Thin Routes per DD-1, DD-2)
# =============================================================================

@router.post(
    "/agent/plan",
    response_model=PlanResponse,
    summary="Plan trip",
    description="Generate travel options, auto-select best option, and create draft itinerary"
)
def plan_trip(
    request: NaturalLanguageQueryRequest,
    ctx: TravelContext = Depends(get_context),
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    """
    Plan a trip from natural language query.
    
    Delegates to Orchestrator.plan_trip() which:
    1. Parses the NL query to intent (DD-1)
    2. Runs agents with context-aware selection (DD-3)
    3. Creates draft itinerary
    
    Returns itinerary_id, all options, selected reservations, and summary.
    """
    logger.info(f"Plan trip request: query='{request.query[:50]}...'" if len(request.query) > 50 else f"Plan trip request: query='{request.query}'")
    
    # Populate context from request (DD-2)
    ctx.traveler_id = request.traveler_id
    ctx.criteria = request.selection_criteria or DEFAULT_SELECTION_CRITERIA
    
    logger.info(f"Traveler: {ctx.traveler_id}, Criteria: {ctx.criteria.value}")
    
    try:
        # Delegate to orchestrator (thin route)
        result = orchestrator.plan_trip(request.query, ctx, include_summary=request.include_summary)
        
        logger.info(f"Plan trip completed: itinerary_id={result['itinerary_id']}")
        
        return PlanResponse(
            itinerary_id=result["itinerary_id"],
            flight_options=result["flight_options"],
            hotel_options=result["hotel_options"],
            car_options=result["car_options"],
            flight_reservation=result["flight_reservation"],
            hotel_reservation=result["hotel_reservation"],
            car_reservation=result["car_reservation"],
            selection_criteria_used=result["selection_criteria_used"],
            preference_summary=result.get("preference_summary"),
            summary=result["summary"],
            query=request.query
        )
        
    except LLMUnavailableError as e:
        handle_domain_exception(e)
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
    ctx: TravelContext = Depends(get_context),
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    """
    Modify an itinerary using natural language instructions.
    
    Loads conversation context into TravelContext, then delegates to Orchestrator.
    """
    logger.info(f"Modify itinerary request: id={itinerary_id}, instruction='{request.instruction[:50]}...'" if len(request.instruction) > 50 else f"Modify itinerary request: id={itinerary_id}, instruction='{request.instruction}'")
    
    # Populate context from request
    ctx.traveler_id = request.traveler_id
    ctx.itinerary_id = itinerary_id
    
    try:
        # Load conversation state into context
        repo = TravelItineraryRepository(ctx.session)
        ctx.itinerary = repo.get_by_id_or_raise(itinerary_id)
        ctx.original_query = ctx.itinerary.original_query
        
        chat_repo = ChatMessageRepository(ctx.session)
        ctx.chat_history = chat_repo.get_history(itinerary_id, limit=10)
        
        # Delegate to orchestrator (thin route)
        result = orchestrator.modify_itinerary(request.instruction, ctx)
        
        # Save chat messages
        chat_repo.add_message(itinerary_id, "user", request.instruction)
        if result.get("message"):
            chat_repo.add_message(itinerary_id, "assistant", result["message"])
        
        logger.info(f"Modification processed for itinerary id={itinerary_id}")
        
        return ModifyResponse(
            success=result["success"],
            updated_itinerary=itinerary_to_response(result["updated_itinerary"]) if result.get("updated_itinerary") else None,
            message=result["message"],
            partial=result.get("partial", False)
        )
        
    except (ItineraryNotFoundError, LLMUnavailableError) as e:
        handle_domain_exception(e)
    except InvalidStatusTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                "CANNOT_MODIFY_CONFIRMED",
                f"Cannot modify itinerary in '{e.current_status}' status",
                400
            )
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


# =============================================================================
# User Preferences CRUD Operations
# =============================================================================

@router.get(
    "/preferences/{traveler_id}",
    response_model=UserPreferencesResponse,
    summary="Get user preferences",
    description="Get user preferences by traveler ID"
)
def get_preferences(
    traveler_id: str,
    db: Session = Depends(get_db),
):
    """Get user preferences by traveler ID."""
    logger.debug(f"Getting preferences for traveler_id={traveler_id}")
    
    repo = UserPreferencesRepository(db)
    
    try:
        preferences = repo.get_by_id_or_raise(traveler_id)
        return UserPreferencesResponse(
            traveler_id=preferences.traveler_id,
            flight_preferences=preferences.flight_preferences,
            hotel_preferences=preferences.hotel_preferences,
            car_preferences=preferences.car_preferences,
            budget_range=preferences.budget_range,
            dietary_restrictions=preferences.dietary_restrictions,
            accessibility_needs=preferences.accessibility_needs,
            loyalty_programs=preferences.loyalty_programs,
            past_bookings_summary=preferences.past_bookings_summary,
            summary=preferences.generate_summary(),
            created_at=preferences.created_at,
            updated_at=preferences.updated_at,
        )
    except PreferencesNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                "PREFERENCES_NOT_FOUND",
                f"Preferences not found for traveler '{traveler_id}'",
                404
            )
        )


@router.put(
    "/preferences/{traveler_id}",
    response_model=UserPreferencesResponse,
    summary="Create or update preferences",
    description="Create or update user preferences (upsert)"
)
def upsert_preferences(
    traveler_id: str,
    request: UserPreferencesCreateRequest,
    db: Session = Depends(get_db),
):
    """Create or update user preferences."""
    logger.info(f"Upserting preferences for traveler_id={traveler_id}")
    
    repo = UserPreferencesRepository(db)
    
    # Convert Pydantic models to dicts
    preferences = repo.upsert(
        traveler_id=traveler_id,
        flight_preferences=request.flight_preferences.model_dump() if request.flight_preferences else None,
        hotel_preferences=request.hotel_preferences.model_dump() if request.hotel_preferences else None,
        car_preferences=request.car_preferences.model_dump() if request.car_preferences else None,
        budget_range=request.budget_range.model_dump() if request.budget_range else None,
        dietary_restrictions=request.dietary_restrictions,
        accessibility_needs=request.accessibility_needs,
        loyalty_programs=[lp.model_dump() for lp in request.loyalty_programs] if request.loyalty_programs else None,
        past_bookings_summary=request.past_bookings_summary,
    )
    
    logger.info(f"Upserted preferences for traveler_id={traveler_id}")
    
    return UserPreferencesResponse(
        traveler_id=preferences.traveler_id,
        flight_preferences=preferences.flight_preferences,
        hotel_preferences=preferences.hotel_preferences,
        car_preferences=preferences.car_preferences,
        budget_range=preferences.budget_range,
        dietary_restrictions=preferences.dietary_restrictions,
        accessibility_needs=preferences.accessibility_needs,
        loyalty_programs=preferences.loyalty_programs,
        past_bookings_summary=preferences.past_bookings_summary,
        summary=preferences.generate_summary(),
        created_at=preferences.created_at,
        updated_at=preferences.updated_at,
    )


@router.delete(
    "/preferences/{traveler_id}",
    response_model=UserPreferencesDeleteResponse,
    summary="Delete preferences",
    description="Delete user preferences"
)
def delete_preferences(
    traveler_id: str,
    db: Session = Depends(get_db),
):
    """Delete user preferences."""
    logger.info(f"Deleting preferences for traveler_id={traveler_id}")
    
    repo = UserPreferencesRepository(db)
    
    try:
        repo.delete(traveler_id)
        return UserPreferencesDeleteResponse(
            success=True,
            message=f"Preferences for traveler '{traveler_id}' deleted successfully"
        )
    except PreferencesNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                "PREFERENCES_NOT_FOUND",
                f"Preferences not found for traveler '{traveler_id}'",
                404
            )
        )


@router.get(
    "/preferences/{traveler_id}/summary",
    summary="Get preference summary",
    description="Get compact preference summary for a traveler (~50 tokens)"
)
def get_preference_summary(
    traveler_id: str,
    db: Session = Depends(get_db),
):
    """Get preference summary for a traveler (fast endpoint for prompts)."""
    repo = UserPreferencesRepository(db)
    summary = repo.get_summary(traveler_id)
    
    return {
        "traveler_id": traveler_id,
        "summary": summary
    }
