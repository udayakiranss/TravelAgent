import pytest
from unittest.mock import MagicMock
from agents.orchestrator import Orchestrator

class TestOrchestrator:
    
    @pytest.fixture
    def orchestrator(self, mock_llm):
        return Orchestrator(llm=mock_llm)

    def test_initialization(self, orchestrator):
        assert len(orchestrator.agents) == 5
        assert "FlightBookingAgent" in orchestrator.agents

    def test_enrich_params(self, orchestrator):
        # Test context enrichment
        context = {
            "FlightBookingAgent": {"total_price": 500},
            "HotelBookingAgent": {"total_price": 300}
        }
        
        # Test itinerary enrichment
        task = {"task": "build_itinerary"}
        params = {}
        enriched = orchestrator._enrich_params(params, context, task)
        # Updated to use new naming convention: flight_reservation instead of flight_booking
        assert "flight_reservation" in enriched
        assert "hotel_reservation" in enriched
        
        # Test payment enrichment
        context["ItineraryAgent"] = {"total_cost": 800}
        task = {"task": "process_payment"}
        params = {}
        enriched = orchestrator._enrich_params(params, context, task)
        assert enriched["amount"] == 800

    def test_run_intent_rule_based(self, orchestrator, mock_llm):
        # Mock planner to return a fixed plan (bypassing actual planner logic for unit test)
        # However, since we can't easily mock the imported plan_trip function without patching,
        # we will rely on the fact that plan_trip uses the passed LLM.
        
        # If we want to test orchestrator logic specifically, we should patch agents.planner.plan_trip
        # But for now let's test the flow with a mocked LLM that returns a plan
        
        mock_llm.invoke_structured.return_value = [
            {
                "agent": "FlightBookingAgent",
                "task": "search_flights",
                "params": {"from": "NYC", "to": "LON"}
            }
        ]
        
        # Added date to prevent needs_clarification status from planner
        intent = {"needs": ["flight"], "from": "NYC", "to": "LON", "date": "2025-08-12"}
        results = orchestrator.run_intent(intent)
        
        assert "FlightBookingAgent.search_flights" in results["results"]

