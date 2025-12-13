"""
Response utility functions for API routes.
Provides standardized response building and error handling.
"""
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from fastapi import HTTPException, status

from database.models import Itinerary
from api.schemas import ItineraryResponse
from database.repository import (
    ItineraryNotFoundError,
    VersionConflictError,
    InvalidStatusTransitionError,
    LLMUnavailableError,
)

if TYPE_CHECKING:
    pass

logger = None  # Will be initialized on first use


def _get_logger():
    """Lazy import logger to avoid circular dependencies."""
    global logger
    if logger is None:
        from utils.logger import get_logger
        logger = get_logger()
    return logger


def itinerary_to_response(itinerary: Itinerary) -> ItineraryResponse:
    """
    Convert database model to response schema.
    
    Args:
        itinerary: Itinerary database model
    
    Returns:
        ItineraryResponse with itinerary data
    """
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
    """
    Create standardized error response dict.
    
    Args:
        error_code: Error code (e.g., "ITINERARY_NOT_FOUND")
        message: Human-readable error description
        status_code: HTTP status code
        details: Optional additional error details
    
    Returns:
        Dictionary with standardized error response format
    """
    return {
        "error": error_code,
        "message": message,
        "status_code": status_code,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "details": details,
    }


def handle_domain_exception(e: Exception):
    """
    Convert domain exceptions to HTTP exceptions (DD-7).
    
    Maps domain exceptions to appropriate HTTP status codes:
    - ItineraryNotFoundError -> 404
    - VersionConflictError -> 409
    - InvalidStatusTransitionError -> 400
    - LLMUnavailableError -> 503
    
    Args:
        e: Domain exception to convert
    
    Raises:
        HTTPException: With appropriate status code and error response
    """
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
        from api.dependencies import get_expected_api_key_name
        api_key_name = get_expected_api_key_name()
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
