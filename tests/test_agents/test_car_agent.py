import pytest
from agents.domain.car_rental_agent import CarRentalAgent, search_cars_tool, book_car_tool

class TestCarRentalAgent:
    
    @pytest.fixture
    def agent(self, mock_llm):
        return CarRentalAgent(llm=mock_llm)

    def test_search_cars_tool(self):
        query = {"city": "LON"}
        results = search_cars_tool.invoke({"query": query})
        assert isinstance(results, list)
        
    def test_book_car_tool(self):
        # Use a valid car ID (C001 exists in data/cars.py)
        query = {"car_id": "C001", "renter_name": "Test User"}
        result = book_car_tool.invoke({"query": query})
        assert result["status"] == "confirmed"
        
        # Invalid car
        query = {"car_id": "INVALID"}
        result = book_car_tool.invoke({"query": query})
        assert "error" in result
