"""
Preference service for user preferences operations.
"""
from typing import Optional

from database.repository import UserPreferencesRepository, PreferencesNotFoundError
from api.schemas import (
    UserPreferencesResponse,
    UserPreferencesDeleteResponse,
    UserPreferencesCreateRequest,
)
from utils.logger import get_logger

logger = get_logger()


class PreferenceService:
    """Service for user preferences operations."""
    
    def __init__(self, session):
        """
        Initialize preference service.
        
        Args:
            session: Database session
        """
        self.session = session
        self.repo = UserPreferencesRepository(session)
    
    def get_preferences(self, traveler_id: str) -> UserPreferencesResponse:
        """
        Get user preferences by traveler ID.
        
        Args:
            traveler_id: Traveler identifier
        
        Returns:
            UserPreferencesResponse with preferences data
        
        Raises:
            PreferencesNotFoundError: If preferences don't exist
        """
        logger.debug(f"Getting preferences for traveler_id={traveler_id}")
        
        preferences = self.repo.get_by_id_or_raise(traveler_id)
        
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
    
    def upsert_preferences(
        self,
        traveler_id: str,
        request: UserPreferencesCreateRequest,
    ) -> UserPreferencesResponse:
        """
        Create or update user preferences (upsert).
        
        Args:
            traveler_id: Traveler identifier
            request: UserPreferencesCreateRequest with preference data
        
        Returns:
            UserPreferencesResponse with updated preferences
        """
        logger.info(f"Upserting preferences for traveler_id={traveler_id}")
        
        # Convert Pydantic models to dicts
        preferences = self.repo.upsert(
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
    
    def delete_preferences(self, traveler_id: str) -> UserPreferencesDeleteResponse:
        """
        Delete user preferences.
        
        Args:
            traveler_id: Traveler identifier
        
        Returns:
            UserPreferencesDeleteResponse with deletion result
        
        Raises:
            PreferencesNotFoundError: If preferences don't exist
        """
        logger.info(f"Deleting preferences for traveler_id={traveler_id}")
        
        self.repo.delete(traveler_id)
        
        return UserPreferencesDeleteResponse(
            success=True,
            message=f"Preferences for traveler '{traveler_id}' deleted successfully"
        )
    
    def get_preference_summary(self, traveler_id: str) -> dict:
        """
        Get preference summary for a traveler (fast endpoint for prompts).
        
        Args:
            traveler_id: Traveler identifier
        
        Returns:
            Dictionary with traveler_id and summary string
        """
        summary = self.repo.get_summary(traveler_id)
        
        return {
            "traveler_id": traveler_id,
            "summary": summary
        }
