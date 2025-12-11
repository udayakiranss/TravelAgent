"""
User preferences routes.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from api.schemas import (
    UserPreferencesCreateRequest,
    UserPreferencesResponse,
    UserPreferencesDeleteResponse,
)
from api.dependencies import get_preference_service
from api.services.preference_service import PreferenceService
from database.repository import PreferencesNotFoundError
from api.utils import create_error_response
from utils.logger import get_logger

logger = get_logger()

router = APIRouter(tags=["Preferences"])


@router.get(
    "/preferences/{traveler_id}",
    response_model=UserPreferencesResponse,
    summary="Get user preferences",
    description="Get user preferences by traveler ID"
)
def get_preferences(
    traveler_id: str,
    service: PreferenceService = Depends(get_preference_service),
):
    """Get user preferences by traveler ID."""
    try:
        return service.get_preferences(traveler_id)
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
    service: PreferenceService = Depends(get_preference_service),
):
    """Create or update user preferences."""
    return service.upsert_preferences(traveler_id, request)


@router.delete(
    "/preferences/{traveler_id}",
    response_model=UserPreferencesDeleteResponse,
    summary="Delete preferences",
    description="Delete user preferences"
)
def delete_preferences(
    traveler_id: str,
    service: PreferenceService = Depends(get_preference_service),
):
    """Delete user preferences."""
    try:
        return service.delete_preferences(traveler_id)
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
    service: PreferenceService = Depends(get_preference_service),
):
    """Get preference summary for a traveler (fast endpoint for prompts)."""
    return service.get_preference_summary(traveler_id)
