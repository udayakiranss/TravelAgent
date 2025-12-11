"""
Itinerary CRUD and status management routes.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlmodel import Session

from api.schemas import (
    ItineraryCreateRequest,
    ItineraryUpdateRequest,
    ItineraryResponse,
    ItineraryListResponse,
    ItineraryStatusResponse,
    ItineraryDeleteResponse,
    ChatHistoryResponse,
)
from api.dependencies import get_db, get_context, get_orchestrator, get_itinerary_service
from api.context import TravelContext
from api.services.itinerary_service import ItineraryService
from database.repository import (
    ItineraryNotFoundError,
    VersionConflictError,
    InvalidStatusTransitionError,
)
from agents.orchestrator import Orchestrator
from api.utils import handle_domain_exception, create_error_response
from utils.logger import get_logger

logger = get_logger()

router = APIRouter(tags=["Itineraries"])


@router.post(
    "/itineraries",
    response_model=ItineraryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create itinerary",
    description="Create a new itinerary in draft status"
)
def create_itinerary(
    request: ItineraryCreateRequest,
    service: ItineraryService = Depends(get_itinerary_service),
):
    """Create a new draft itinerary."""
    return service.create_itinerary(request.traveler_id, request.original_query)


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
    service: ItineraryService = Depends(get_itinerary_service),
):
    """List itineraries with pagination."""
    return service.list_itineraries(status, traveler_id, page, limit)


@router.get(
    "/itineraries/{itinerary_id}",
    response_model=ItineraryResponse,
    summary="Get itinerary",
    description="Get itinerary details by ID"
)
def get_itinerary(
    itinerary_id: str,
    service: ItineraryService = Depends(get_itinerary_service),
):
    """Get itinerary by ID."""
    try:
        return service.get_itinerary(itinerary_id)
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
    service: ItineraryService = Depends(get_itinerary_service),
):
    """Get chat history for an itinerary."""
    try:
        return service.get_chat_history(itinerary_id, limit)
    except ItineraryNotFoundError as e:
        handle_domain_exception(e)


@router.put(
    "/itineraries/{itinerary_id}",
    response_model=ItineraryResponse,
    summary="Update itinerary",
    description="Update itinerary with optimistic locking"
)
def update_itinerary(
    itinerary_id: str,
    request: ItineraryUpdateRequest,
    service: ItineraryService = Depends(get_itinerary_service),
):
    """Update itinerary with optimistic locking."""
    try:
        return service.update_itinerary(itinerary_id, request)
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
    service: ItineraryService = Depends(get_itinerary_service),
):
    """Delete a draft itinerary."""
    try:
        return service.delete_itinerary(itinerary_id)
    except (ItineraryNotFoundError, InvalidStatusTransitionError) as e:
        handle_domain_exception(e)


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
    service: ItineraryService = Depends(get_itinerary_service),
):
    """Confirm a draft itinerary."""
    try:
        return service.confirm_itinerary(itinerary_id, orchestrator, ctx)
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
    service: ItineraryService = Depends(get_itinerary_service),
):
    """Cancel an itinerary."""
    try:
        return service.cancel_itinerary(itinerary_id, orchestrator, ctx)
    except (ItineraryNotFoundError, InvalidStatusTransitionError) as e:
        handle_domain_exception(e)
