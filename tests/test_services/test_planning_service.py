"""
Unit tests for PlanningService.
"""
import pytest
from unittest.mock import Mock, MagicMock
from fastapi.responses import JSONResponse
from fastapi import status

from api.services.planning_service import PlanningService
from api.schemas import NaturalLanguageQueryRequest, PlanResponse
from database.repository import LLMUnavailableError


class TestPlanningService:
    """Tests for PlanningService."""
    
    def test_plan_trip_success(self, mock_planner, mock_orchestrator, mock_context):
        """Test successful trip planning."""
        # Mock plan creation
        mock_plan = Mock()
        mock_plan.status = "ready"
        mock_plan.plan_metadata.plan_id = "plan-123"
        mock_plan.tasks = [Mock(), Mock()]
        mock_planner.create_plan_from_query.return_value = mock_plan
        
        # Mock plan execution
        mock_orchestrator.execute_plan.return_value = {
            "itinerary_id": "itin-123",
            "flight_reservation": {"airline": "Test Air", "price": 500},
            "summary": "Trip planned successfully"
        }
        
        service = PlanningService(mock_planner, mock_orchestrator)
        
        request = NaturalLanguageQueryRequest(
            query="Plan a trip from NYC to Paris",
            traveler_id="user_123"
        )
        
        result = service.plan_trip(request, mock_context)
        
        assert isinstance(result, PlanResponse)
        assert result.itinerary_id == "itin-123"
        assert result.flight_reservation["airline"] == "Test Air"
        assert result.summary == "Trip planned successfully"
        assert result.query == "Plan a trip from NYC to Paris"
        mock_planner.create_plan_from_query.assert_called_once()
        mock_orchestrator.execute_plan.assert_called_once()
    
    def test_plan_trip_needs_clarification(self, mock_planner, mock_orchestrator, mock_context):
        """Test planning when clarification is needed."""
        # Mock plan that needs clarification
        mock_plan = Mock()
        mock_plan.status = "needs_clarification"
        mock_plan.plan_metadata.plan_id = "plan-123"
        mock_missing_info = Mock()
        mock_missing_info.field = "date"
        mock_missing_info.model_dump.return_value = {"field": "date", "message": "Date is required"}
        mock_plan.missing_info = [mock_missing_info]
        mock_planner.create_plan_from_query.return_value = mock_plan
        
        service = PlanningService(mock_planner, mock_orchestrator)
        
        request = NaturalLanguageQueryRequest(
            query="Plan a trip to Paris",
            traveler_id="user_123"
        )
        
        result = service.plan_trip(request, mock_context)
        
        assert isinstance(result, JSONResponse)
        assert result.status_code == status.HTTP_400_BAD_REQUEST
        # Verify orchestrator was not called
        mock_orchestrator.execute_plan.assert_not_called()
    
    def test_plan_trip_no_itinerary_created(self, mock_planner, mock_orchestrator, mock_context):
        """Test planning when plan executes but no itinerary is created."""
        # Mock plan creation
        mock_plan = Mock()
        mock_plan.status = "ready"
        mock_plan.plan_metadata.plan_id = "plan-123"
        mock_plan.tasks = [Mock()]
        mock_planner.create_plan_from_query.return_value = mock_plan
        
        # Mock plan execution without itinerary_id
        mock_orchestrator.execute_plan.return_value = {
            "flight_options": [{"id": "FL-1"}],
            "summary": "Search completed but no itinerary created"
        }
        
        service = PlanningService(mock_planner, mock_orchestrator)
        
        request = NaturalLanguageQueryRequest(
            query="Search flights from NYC to Paris",
            traveler_id="user_123"
        )
        
        result = service.plan_trip(request, mock_context)
        
        assert isinstance(result, PlanResponse)
        assert result.itinerary_id is None
        assert len(result.flight_options) == 1
        assert "no itinerary" in result.summary.lower()
    
    def test_plan_trip_with_preferences(self, mock_planner, mock_orchestrator, mock_context):
        """Test planning with user preferences."""
        mock_plan = Mock()
        mock_plan.status = "ready"
        mock_plan.plan_metadata.plan_id = "plan-123"
        mock_plan.tasks = [Mock()]
        mock_planner.create_plan_from_query.return_value = mock_plan
        
        mock_orchestrator.execute_plan.return_value = {
            "itinerary_id": "itin-123",
            "preference_summary": "User prefers aisle seats",
            "summary": "Trip planned with preferences"
        }
        
        service = PlanningService(mock_planner, mock_orchestrator)
        
        request = NaturalLanguageQueryRequest(
            query="Plan a trip to Paris",
            traveler_id="user_123"
        )
        
        result = service.plan_trip(request, mock_context)
        
        assert result.preference_summary == "User prefers aisle seats"
        assert result.summary == "Trip planned with preferences"
    
    def test_build_plan_response_with_partial_results(self, mock_planner, mock_orchestrator, mock_context):
        """Test building response with partial results."""
        service = PlanningService(mock_planner, mock_orchestrator)
        
        result_dict = {
            "flight_options": [{"id": "FL-1"}],
            "hotel_options": [{"id": "HT-1"}],
            "selection_criteria_used": "cheapest"
        }
        
        response = service._build_plan_response(
            result_dict,
            mock_context,
            "Test query",
            None  # No itinerary_id
        )
        
        assert response.itinerary_id is None
        assert len(response.flight_options) == 1
        assert len(response.hotel_options) == 1
        assert response.selection_criteria_used == "cheapest"
        assert "no itinerary was created" in response.summary
    
    def test_build_plan_response_success(self, mock_planner, mock_orchestrator, mock_context):
        """Test building successful response."""
        service = PlanningService(mock_planner, mock_orchestrator)
        
        result_dict = {
            "itinerary_id": "itin-123",
            "flight_reservation": {"airline": "Test Air"},
            "summary": "Success"
        }
        
        response = service._build_plan_response(
            result_dict,
            mock_context,
            "Test query",
            "itin-123"
        )
        
        assert response.itinerary_id == "itin-123"
        assert response.flight_reservation["airline"] == "Test Air"
        assert response.summary == "Success"
        assert response.query == "Test query"
