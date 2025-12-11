"""
Unit tests for PreferenceService.
"""
import pytest

from api.services.preference_service import PreferenceService
from database.repository import PreferencesNotFoundError
from database.models import UserPreferences
from api.schemas import UserPreferencesCreateRequest, FlightPreferences, HotelPreferences


class TestPreferenceService:
    """Tests for PreferenceService."""
    
    def test_get_preferences_success(self, mock_session, sample_preferences):
        """Test getting user preferences."""
        service = PreferenceService(mock_session)
        
        result = service.get_preferences("user_123")
        
        assert result.traveler_id == "user_123"
        assert result.flight_preferences == {"seat_type": "aisle"}
        assert result.hotel_preferences == {"min_rating": 4}
        assert result.summary is not None
    
    def test_get_preferences_not_found(self, mock_session):
        """Test getting non-existent preferences raises error."""
        service = PreferenceService(mock_session)
        
        with pytest.raises(PreferencesNotFoundError):
            service.get_preferences("user_nonexistent")
    
    def test_upsert_preferences_create(self, mock_session):
        """Test creating new preferences via upsert."""
        service = PreferenceService(mock_session)
        
        request = UserPreferencesCreateRequest(
            flight_preferences=FlightPreferences(seat_type="window"),
            hotel_preferences=HotelPreferences(min_rating=3),
        )
        
        result = service.upsert_preferences("user_new", request)
        
        assert result.traveler_id == "user_new"
        assert result.flight_preferences["seat_type"] == "window"
        assert result.hotel_preferences["min_rating"] == 3
    
    def test_upsert_preferences_update(self, mock_session, sample_preferences):
        """Test updating existing preferences via upsert."""
        service = PreferenceService(mock_session)
        
        request = UserPreferencesCreateRequest(
            flight_preferences=FlightPreferences(seat_type="aisle", preferred_airlines=["Delta"]),
        )
        
        result = service.upsert_preferences("user_123", request)
        
        assert result.traveler_id == "user_123"
        assert result.flight_preferences["seat_type"] == "aisle"
        assert "Delta" in result.flight_preferences["preferred_airlines"]
        # Hotel preferences should still exist from original
        assert result.hotel_preferences == {"min_rating": 4}
    
    def test_delete_preferences_success(self, mock_session, sample_preferences):
        """Test deleting user preferences."""
        service = PreferenceService(mock_session)
        
        result = service.delete_preferences("user_123")
        
        assert result.success is True
        assert "deleted successfully" in result.message
        
        # Verify it's deleted
        with pytest.raises(PreferencesNotFoundError):
            service.get_preferences("user_123")
    
    def test_delete_preferences_not_found(self, mock_session):
        """Test deleting non-existent preferences raises error."""
        service = PreferenceService(mock_session)
        
        with pytest.raises(PreferencesNotFoundError):
            service.delete_preferences("user_nonexistent")
    
    def test_get_preference_summary_success(self, mock_session, sample_preferences):
        """Test getting preference summary."""
        service = PreferenceService(mock_session)
        
        result = service.get_preference_summary("user_123")
        
        assert result["traveler_id"] == "user_123"
        assert "summary" in result
        assert isinstance(result["summary"], str)
        assert len(result["summary"]) > 0
    
    def test_get_preference_summary_not_found(self, mock_session):
        """Test getting summary for non-existent preferences."""
        service = PreferenceService(mock_session)
        
        # Should return a message indicating no preferences, not raise error
        result = service.get_preference_summary("user_nonexistent")
        
        assert result["traveler_id"] == "user_nonexistent"
        assert "summary" in result
        assert isinstance(result["summary"], str)
        # Repository returns a message like "No preferences set for this traveler"
        assert len(result["summary"]) > 0  # Should have some message
