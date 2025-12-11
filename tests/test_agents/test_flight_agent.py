import pytest  # type: ignore
from agents.flight_booking_agent import FlightBookingAgent, search_flights_tool, compare_flights_tool, book_flight_tool

class TestFlightBookingAgent:
    
    @pytest.fixture
    def agent(self, mock_llm):
        return FlightBookingAgent(llm=mock_llm)

    def test_initialization(self, agent):
        assert agent.name == "FlightBookingAgent"
        assert "search_flights" in agent.tools
        assert "compare_flights" in agent.tools
        assert "book_flight" in agent.tools

    def test_search_flights_tool(self):
        # Test with valid search
        query = {"from": "NYC", "to": "LON", "date": "2025-08-12"}
        results = search_flights_tool.invoke({"query": query})
        assert isinstance(results, list)
        # Note: This relies on the hardcoded data in FLIGHTS. 
        # Ideally we should mock FLIGHTS, but for now we test the logic.
        
    def test_compare_flights_tool(self):
        # Test with valid IDs
        query = {"flight_ids": ["F001", "F002"]}
        result = compare_flights_tool.invoke({"query": query})
        assert "cheapest" in result
        assert "most_expensive" in result
        
        # Test with invalid IDs
        query = {"flight_ids": ["INVALID"]}
        result = compare_flights_tool.invoke({"query": query})
        assert "error" in result

    def test_book_flight_tool(self):
        # Test booking
        query = {"flight_id": "F001", "passenger_name": "Test User"}
        result = book_flight_tool.invoke({"query": query})
        assert result["status"] == "confirmed"
        assert "BK-F001" in result["booking_id"]
        
        # Test invalid flight
        query = {"flight_id": "INVALID"}
        result = book_flight_tool.invoke({"query": query})
        assert "error" in result

    def test_execute_direct_tool(self, agent):
        # Test executing a tool directly
        params = {"from": "NYC", "to": "LON", "date": "2025-08-12"}
        result = agent.execute("search_flights", params)
        assert isinstance(result, list)

    def test_execute_unknown_tool_with_llm(self, agent, mock_llm):
        # Mock LLM to return a valid tool name
        mock_llm.invoke.return_value = "search_flights"
        
        params = {"from": "NYC", "to": "LON", "date": "2025-08-12"}
        result = agent.execute("find_flights", params) # Ambiguous task
        
        mock_llm.invoke.assert_called_once()
        assert isinstance(result, list)
