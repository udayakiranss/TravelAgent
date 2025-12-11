"""
Search service for flight, hotel, and car search operations.
"""
from typing import List, Dict, Any

from tools.search_tools import search_flights as tool_search_flights
from tools.search_tools import search_hotels as tool_search_hotels
from tools.search_tools import search_cars as tool_search_cars
from utils.logger import get_logger

logger = get_logger()


class SearchService:
    """Service for search operations."""
    
    def search_flights(self, origin: str, destination: str, date: str) -> List[Dict[str, Any]]:
        """
        Search for available flights.
        
        Args:
            origin: Origin city/airport code
            destination: Destination city/airport code
            date: Date of travel (YYYY-MM-DD)
        
        Returns:
            List of flight options
        
        Raises:
            Exception: If search fails
        """
        logger.info(f"Searching flights: {origin} -> {destination} on {date}")
        try:
            # LangChain tool expects {"query": {...}} format
            results = tool_search_flights.invoke({
                "query": {
                    "from": origin,
                    "to": destination,
                    "date": date
                }
            })
            logger.info(f"Flight search returned {len(results)} results")
            return results
        except Exception as e:
            logger.error(f"Flight search failed: {e}")
            raise
    
    def search_hotels(self, city: str) -> List[Dict[str, Any]]:
        """
        Search for available hotels.
        
        Args:
            city: City code to search in
        
        Returns:
            List of hotel options
        
        Raises:
            Exception: If search fails
        """
        logger.info(f"Searching hotels in: {city}")
        try:
            # LangChain tool expects {"query": {...}} format
            results = tool_search_hotels.invoke({"query": {"city": city}})
            logger.info(f"Hotel search returned {len(results)} results")
            return results
        except Exception as e:
            logger.error(f"Hotel search failed: {e}")
            raise
    
    def search_cars(self, city: str) -> List[Dict[str, Any]]:
        """
        Search for available car rentals.
        
        Args:
            city: City code to search in
        
        Returns:
            List of car rental options
        
        Raises:
            Exception: If search fails
        """
        logger.info(f"Searching cars in: {city}")
        try:
            # LangChain tool expects {"query": {...}} format
            results = tool_search_cars.invoke({"query": {"city": city}})
            logger.info(f"Car search returned {len(results)} results")
            return results
        except Exception as e:
            logger.error(f"Car search failed: {e}")
            raise
