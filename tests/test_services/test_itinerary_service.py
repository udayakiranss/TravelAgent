"""
Unit tests for ItineraryService.
"""
import pytest
from unittest.mock import Mock, patch

from api.services.itinerary_service import ItineraryService
from database.repository import (
    ItineraryNotFoundError,
    VersionConflictError,
    InvalidStatusTransitionError,
)
from database.models import Itinerary
from api.schemas import ItineraryUpdateRequest


class TestItineraryService:
    """Tests for ItineraryService."""
    
    def test_create_itinerary_success(self, mock_session):
        """Test creating a new itinerary."""
        service = ItineraryService(mock_session)
        
        result = service.create_itinerary(
            traveler_id="user_123",
            original_query="Plan a trip to Paris"
        )
        
        assert result.traveler_id == "user_123"
        assert result.original_query == "Plan a trip to Paris"
        assert result.status == "draft"
        assert result.version == 1
        assert result.id.startswith("itin-")
    
    def test_get_itinerary_success(self, mock_session, sample_itinerary):
        """Test getting an itinerary by ID."""
        service = ItineraryService(mock_session)
        
        result = service.get_itinerary(sample_itinerary.id)
        
        assert result.id == sample_itinerary.id
        assert result.traveler_id == sample_itinerary.traveler_id
        assert result.status == "draft"
    
    def test_get_itinerary_not_found(self, mock_session):
        """Test getting non-existent itinerary raises error."""
        service = ItineraryService(mock_session)
        
        with pytest.raises(ItineraryNotFoundError):
            service.get_itinerary("itin-nonexistent")
    
    def test_list_itineraries_empty(self, mock_session):
        """Test listing itineraries when empty."""
        service = ItineraryService(mock_session)
        
        result = service.list_itineraries()
        
        assert result.total == 0
        assert result.items == []
        assert result.page == 1
        assert result.has_more is False
    
    def test_list_itineraries_with_data(self, mock_session, sample_itinerary):
        """Test listing itineraries with data."""
        service = ItineraryService(mock_session)
        
        result = service.list_itineraries()
        
        assert result.total == 1
        assert len(result.items) == 1
        assert result.items[0].id == sample_itinerary.id
    
    def test_list_itineraries_filter_by_status(self, mock_session):
        """Test filtering itineraries by status."""
        # Create multiple itineraries with different statuses
        for status in ["draft", "draft", "confirmed"]:
            itinerary = Itinerary(
                traveler_id="user_123",
                status=status
            )
            mock_session.add(itinerary)
        mock_session.commit()
        
        service = ItineraryService(mock_session)
        
        result = service.list_itineraries(status="draft")
        
        assert result.total == 2
        assert all(item.status == "draft" for item in result.items)
    
    def test_list_itineraries_pagination(self, mock_session):
        """Test pagination of itinerary list."""
        # Create 25 itineraries
        for i in range(25):
            itinerary = Itinerary(traveler_id=f"user_{i}")
            mock_session.add(itinerary)
        mock_session.commit()
        
        service = ItineraryService(mock_session)
        
        # Page 1
        result = service.list_itineraries(page=1, limit=10)
        assert result.total == 25
        assert len(result.items) == 10
        assert result.has_more is True
        
        # Page 3
        result = service.list_itineraries(page=3, limit=10)
        assert len(result.items) == 5
        assert result.has_more is False
    
    def test_update_itinerary_success(self, mock_session, sample_itinerary):
        """Test updating an itinerary."""
        service = ItineraryService(mock_session)
        
        request = ItineraryUpdateRequest(
            version=1,
            flight_reservation={"airline": "Test Air", "price": 500}
        )
        
        result = service.update_itinerary(sample_itinerary.id, request)
        
        assert result.version == 2
        assert result.flight_reservation["airline"] == "Test Air"
        assert result.total_cost == 500
    
    def test_update_itinerary_version_conflict(self, mock_session, sample_itinerary):
        """Test version conflict error."""
        service = ItineraryService(mock_session)
        
        request = ItineraryUpdateRequest(
            version=999,  # Wrong version
            flight_reservation={"airline": "Test Air"}
        )
        
        with pytest.raises(VersionConflictError):
            service.update_itinerary(sample_itinerary.id, request)
    
    def test_update_itinerary_not_found(self, mock_session):
        """Test updating non-existent itinerary."""
        service = ItineraryService(mock_session)
        
        request = ItineraryUpdateRequest(version=1)
        
        with pytest.raises(ItineraryNotFoundError):
            service.update_itinerary("itin-nonexistent", request)
    
    def test_delete_itinerary_success(self, mock_session, sample_itinerary):
        """Test deleting a draft itinerary."""
        service = ItineraryService(mock_session)
        
        result = service.delete_itinerary(sample_itinerary.id)
        
        assert result.success is True
        assert "deleted successfully" in result.message
        
        # Verify it's deleted
        with pytest.raises(ItineraryNotFoundError):
            service.get_itinerary(sample_itinerary.id)
    
    def test_delete_confirmed_itinerary_fails(self, mock_session, sample_confirmed_itinerary):
        """Test that confirmed itineraries cannot be deleted."""
        service = ItineraryService(mock_session)
        
        with pytest.raises(InvalidStatusTransitionError):
            service.delete_itinerary(sample_confirmed_itinerary.id)
    
    def test_confirm_itinerary_success(self, mock_session, sample_itinerary, mock_orchestrator, mock_context):
        """Test confirming a draft itinerary."""
        # Mock orchestrator to return confirmed itinerary
        confirmed_itinerary = Itinerary(
            id=sample_itinerary.id,
            traveler_id=sample_itinerary.traveler_id,
            status="confirmed",
            version=2
        )
        mock_orchestrator.confirm_itinerary.return_value = confirmed_itinerary
        
        service = ItineraryService(mock_session)
        
        result = service.confirm_itinerary(
            sample_itinerary.id,
            mock_orchestrator,
            mock_context
        )
        
        assert result.status == "confirmed"
        assert result.id == sample_itinerary.id
        assert "confirmed successfully" in result.message
        mock_orchestrator.confirm_itinerary.assert_called_once()
    
    def test_confirm_already_confirmed_fails(self, mock_session, sample_confirmed_itinerary, mock_orchestrator, mock_context):
        """Test that confirming an already confirmed itinerary fails."""
        # Mock orchestrator to raise error
        mock_orchestrator.confirm_itinerary.side_effect = InvalidStatusTransitionError(
            "confirmed", "confirmed"
        )
        
        service = ItineraryService(mock_session)
        
        with pytest.raises(InvalidStatusTransitionError):
            service.confirm_itinerary(
                sample_confirmed_itinerary.id,
                mock_orchestrator,
                mock_context
            )
    
    def test_cancel_itinerary_success(self, mock_session, sample_itinerary, mock_orchestrator, mock_context):
        """Test cancelling an itinerary."""
        # Mock orchestrator to return cancelled itinerary
        cancelled_itinerary = Itinerary(
            id=sample_itinerary.id,
            traveler_id=sample_itinerary.traveler_id,
            status="cancelled",
            version=2
        )
        mock_orchestrator.cancel_itinerary.return_value = cancelled_itinerary
        
        service = ItineraryService(mock_session)
        
        result = service.cancel_itinerary(
            sample_itinerary.id,
            mock_orchestrator,
            mock_context
        )
        
        assert result.status == "cancelled"
        assert result.id == sample_itinerary.id
        assert "cancelled successfully" in result.message
        mock_orchestrator.cancel_itinerary.assert_called_once()
    
    def test_get_chat_history_success(self, mock_session, sample_itinerary, sample_chat_messages):
        """Test getting chat history for an itinerary."""
        service = ItineraryService(mock_session)
        
        result = service.get_chat_history(sample_itinerary.id, limit=10)
        
        assert result.itinerary_id == sample_itinerary.id
        assert len(result.messages) == 2
        assert result.messages[0].role == "user"
        assert result.messages[1].role == "assistant"
    
    def test_get_chat_history_not_found(self, mock_session):
        """Test getting chat history for non-existent itinerary."""
        service = ItineraryService(mock_session)
        
        with pytest.raises(ItineraryNotFoundError):
            service.get_chat_history("itin-nonexistent")
