import pytest
from agents.planner import plan_trip, _rule_based_plan, _llm_based_plan

class TestPlanner:
    
    def test_rule_based_plan(self):
        intent = {
            "needs": ["flight", "hotel"],
            "from": "NYC",
            "to": "LON",
            "date": "2025-08-12",
            "auto_pay": True,
            "budget": 2000
        }
        
        plan = _rule_based_plan(intent)
        
        # Verify plan structure
        assert len(plan) >= 4 # flight, hotel, itinerary, payment
        
        agent_names = [task["agent"] for task in plan]
        assert "FlightBookingAgent" in agent_names
        assert "HotelBookingAgent" in agent_names
        assert "ItineraryAgent" in agent_names
        assert "PaymentAgent" in agent_names

    def test_plan_trip_fallback(self):
        # Test that plan_trip falls back to rule-based when no LLM is provided
        intent = {"needs": ["flight"]}
        plan = plan_trip(intent, llm=None)
        assert len(plan) > 0
        assert plan[0]["agent"] == "FlightBookingAgent"

    def test_llm_based_plan(self, mock_llm):
        intent = {"needs": ["flight"]}
        
        # Mock LLM response
        mock_llm.invoke_structured.return_value = [
            {
                "agent": "FlightBookingAgent",
                "task": "search_flights",
                "params": {"from": "NYC", "to": "LON"}
            }
        ]
        
        plan = plan_trip(intent, llm=mock_llm)
        assert len(plan) == 1
        assert plan[0]["agent"] == "FlightBookingAgent"
