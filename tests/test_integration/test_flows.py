import pytest
from agents.orchestrator import Orchestrator
from agents.itinerary_agent import _ITINERARIES

class TestIntegrationFlows:
    
    @pytest.fixture(autouse=True)
    def clear_state(self):
        _ITINERARIES.clear()
        yield
        _ITINERARIES.clear()

    def test_full_booking_flow_rule_based(self):
        # Test a full flow without LLM (using rule-based planning)
        orchestrator = Orchestrator(llm=None)
        
        intent = {
            "needs": ["flight", "hotel", "car"],
            "from": "NYC",
            "to": "LON",
            "date": "2025-08-12",
            "auto_pay": True,
            "budget": 5000,
            "payment_method": "card"
        }
        
        results = orchestrator.run_intent(intent)
        
        # Verify all steps executed
        assert "FlightBookingAgent.search_flights" in results
        assert "HotelBookingAgent.search_hotels" in results
        assert "CarRentalAgent.search_cars" in results
        assert "ItineraryAgent.build_itinerary" in results
        assert "PaymentAgent.process_payment" in results
        
        # Verify itinerary was created
        itinerary_result = results["ItineraryAgent.build_itinerary"]
        assert "itinerary_id" in itinerary_result
        
        # Verify payment
        payment_result = results["PaymentAgent.process_payment"]
        assert payment_result["status"] == "success"
        
        # Verify context passing (payment amount should match itinerary cost)
        # Note: In rule-based plan, we might not have explicitly chained the cost, 
        # but the orchestrator enriches params.
        # Let's check if the payment amount matches the budget passed in intent 
        # (as per rule-based logic in planner.py)
        assert payment_result["charged"] == 5000

    def test_orchestrator_context_passing(self, mock_llm):
        # Test that orchestrator correctly passes context between agents
        orchestrator = Orchestrator(llm=mock_llm)
        
        # Manually define tasks to test specific flow
        tasks = [
            {
                "agent": "FlightBookingAgent",
                "task": "book_flight",
                "params": {"flight_id": "F001"}
            },
            {
                "agent": "ItineraryAgent",
                "task": "build_itinerary",
                "params": {} # Should be enriched with flight booking
            }
        ]
        
        # Mock planner to return these tasks
        mock_llm.invoke_structured.return_value = tasks
        
        intent = {"needs": ["flight"]}
        results = orchestrator.run_intent(intent)
        
        # Verify flight booking
        assert "FlightBookingAgent.book_flight" in results
        flight_booking = results["FlightBookingAgent.book_flight"]
        
        # Verify itinerary creation and enrichment
        assert "ItineraryAgent.build_itinerary" in results
        itinerary = results["ItineraryAgent.build_itinerary"]
        
        assert itinerary["flight"] == flight_booking
