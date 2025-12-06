import pytest
from agents.hotel_booking_agent import HotelBookingAgent, search_hotels_tool, book_hotel_tool

class TestHotelBookingAgent:
    
    @pytest.fixture
    def agent(self, mock_llm):
        return HotelBookingAgent(llm=mock_llm)

    def test_search_hotels_tool(self):
        query = {"city": "LON"}
        results = search_hotels_tool.invoke({"query": query})
        assert isinstance(results, list)
        
    def test_book_hotel_tool(self):
        # Assuming H101 exists
        query = {"hotel_id": "H101", "guest_name": "Test User"}
        result = book_hotel_tool.invoke({"query": query})
        assert result["status"] == "confirmed"
        
        # Invalid hotel
        query = {"hotel_id": "INVALID"}
        result = book_hotel_tool.invoke({"query": query})
        assert "error" in result
