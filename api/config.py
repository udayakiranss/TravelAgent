"""
API configuration settings for the Travel Booking Web Application.
Provides centralized configuration with environment variable overrides.
"""
import os
from enum import Enum


class SelectionCriteria(str, Enum):
    """Criteria for auto-selecting the best travel option."""
    FIRST_AVAILABLE = "first_available"
    CHEAPEST = "cheapest"
    BEST_RATED = "best_rated"


# Default selection criteria from environment or fallback to first_available
DEFAULT_SELECTION_CRITERIA = SelectionCriteria(
    os.getenv("OPTION_SELECTION_CRITERIA", "first_available")
)
