import pytest
from agents.itinerary_agent import ItineraryAgent, build_itinerary_tool, update_itinerary_tool, get_itinerary_tool, _ITINERARIES

class TestItineraryAgent:
    
    @pytest.fixture(autouse=True)
    def clear_itineraries(self):
        # Clear global state before each test
        _ITINERARIES.clear()
        yield
        _ITINERARIES.clear()

    @pytest.fixture
    def agent(self, mock_llm):
        return ItineraryAgent(llm=mock_llm)

    def test_build_itinerary_tool(self):
        query = {
            "flight_booking": {"price": 500},
            "hotel_booking": {"price": 300},
            "traveler_name": "Test User"
        }
        result = build_itinerary_tool.invoke({"query": query})
        assert result["total_cost"] == 800
        assert result["traveler"] == "Test User"
        assert result["itinerary_id"] in _ITINERARIES

    def test_update_itinerary_tool(self):
        # Create initial itinerary
        init_query = {"flight_booking": {"price": 500}}
        itinerary = build_itinerary_tool.invoke({"query": init_query})
        itin_id = itinerary["itinerary_id"]
        
        # Update
        update_query = {
            "itinerary_id": itin_id,
            "hotel_booking": {"price": 300}
        }
        updated = update_itinerary_tool.invoke({"query": update_query})
        assert updated["total_cost"] == 800
        assert updated["hotel"] == {"price": 300}

    def test_get_itinerary_tool(self):
        # Create initial itinerary
        init_query = {"flight_booking": {"price": 500}}
        itinerary = build_itinerary_tool.invoke({"query": init_query})
        itin_id = itinerary["itinerary_id"]
        
        # Get
        query = {"itinerary_id": itin_id}
        result = get_itinerary_tool.invoke({"query": query})
        assert result == itinerary
