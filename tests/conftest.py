import pytest
from unittest.mock import MagicMock
from agents.core import LLMProvider

@pytest.fixture
def mock_llm():
    """Fixture for a mock LLM provider"""
    llm = MagicMock(spec=LLMProvider)
    llm.model_name = "mock-model"
    llm.model_provider = "mock-provider"
    return llm

@pytest.fixture
def mock_flight_data():
    """Fixture for mock flight data"""
    return [
        {
            "id": "FL-101",
            "from": "NYC",
            "to": "LON",
            "date": "2025-08-12",
            "airline": "British Airways",
            "price": 850,
            "duration": "7h 00m"
        },
        {
            "id": "FL-102",
            "from": "NYC",
            "to": "LON",
            "date": "2025-08-12",
            "airline": "Virgin Atlantic",
            "price": 820,
            "duration": "7h 15m"
        }
    ]

@pytest.fixture
def mock_hotel_data():
    """Fixture for mock hotel data"""
    return [
        {
            "id": "HT-101",
            "name": "The Ritz London",
            "city": "LON",
            "price": 600,
            "rating": 5.0,
            "amenities": ["Spa", "WiFi", "Bar"]
        }
    ]
