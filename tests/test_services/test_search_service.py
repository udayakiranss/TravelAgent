"""
Unit tests for SearchService.
"""
import pytest
from unittest.mock import patch, MagicMock

from api.services.search_service import SearchService


class TestSearchService:
    """Tests for SearchService."""
    
    @patch('api.services.search_service.tool_search_flights')
    def test_search_flights_success(self, mock_tool):
        """Test successful flight search."""
        # Mock tool response
        mock_tool.invoke.return_value = [
            {
                "id": "FL-101",
                "from": "NYC",
                "to": "LON",
                "airline": "British Airways",
                "price": 850,
            }
        ]
        
        service = SearchService()
        result = service.search_flights("NYC", "LON", "2025-08-12")
        
        assert len(result) == 1
        assert result[0]["id"] == "FL-101"
        assert result[0]["from"] == "NYC"
        assert result[0]["to"] == "LON"
        mock_tool.invoke.assert_called_once_with({
            "query": {
                "from": "NYC",
                "to": "LON",
                "date": "2025-08-12"
            }
        })
    
    @patch('api.services.search_service.tool_search_flights')
    def test_search_flights_empty(self, mock_tool):
        """Test flight search with no results."""
        mock_tool.invoke.return_value = []
        
        service = SearchService()
        result = service.search_flights("NYC", "LON", "2025-08-12")
        
        assert result == []
    
    @patch('api.services.search_service.tool_search_flights')
    def test_search_flights_error(self, mock_tool):
        """Test flight search error handling."""
        mock_tool.invoke.side_effect = Exception("Search failed")
        
        service = SearchService()
        
        with pytest.raises(Exception, match="Search failed"):
            service.search_flights("NYC", "LON", "2025-08-12")
    
    @patch('api.services.search_service.tool_search_hotels')
    def test_search_hotels_success(self, mock_tool):
        """Test successful hotel search."""
        mock_tool.invoke.return_value = [
            {
                "id": "HT-101",
                "name": "The Ritz",
                "city": "LON",
                "price": 600,
            }
        ]
        
        service = SearchService()
        result = service.search_hotels("LON")
        
        assert len(result) == 1
        assert result[0]["id"] == "HT-101"
        assert result[0]["city"] == "LON"
        mock_tool.invoke.assert_called_once_with({
            "query": {"city": "LON"}
        })
    
    @patch('api.services.search_service.tool_search_hotels')
    def test_search_hotels_error(self, mock_tool):
        """Test hotel search error handling."""
        mock_tool.invoke.side_effect = Exception("Hotel search failed")
        
        service = SearchService()
        
        with pytest.raises(Exception, match="Hotel search failed"):
            service.search_hotels("LON")
    
    @patch('api.services.search_service.tool_search_cars')
    def test_search_cars_success(self, mock_tool):
        """Test successful car search."""
        mock_tool.invoke.return_value = [
            {
                "id": "CR-101",
                "company": "Hertz",
                "city": "LON",
                "price": 50,
            }
        ]
        
        service = SearchService()
        result = service.search_cars("LON")
        
        assert len(result) == 1
        assert result[0]["id"] == "CR-101"
        assert result[0]["city"] == "LON"
        mock_tool.invoke.assert_called_once_with({
            "query": {"city": "LON"}
        })
    
    @patch('api.services.search_service.tool_search_cars')
    def test_search_cars_error(self, mock_tool):
        """Test car search error handling."""
        mock_tool.invoke.side_effect = Exception("Car search failed")
        
        service = SearchService()
        
        with pytest.raises(Exception, match="Car search failed"):
            service.search_cars("LON")
