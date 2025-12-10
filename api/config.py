"""
API configuration settings for the Travel Booking Web Application.
Provides centralized configuration with environment variable overrides.
"""
import os
from enum import Enum

# Ensure .env values are loaded before reading environment variables
# This is important because main_web.py calls load_dotenv() after importing
# this module. Loading here guarantees config picks up .env values.
try:  # keep optional to avoid hard dependency
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass


class SelectionCriteria(str, Enum):
    """Criteria for auto-selecting the best travel option."""
    FIRST_AVAILABLE = "first_available"
    CHEAPEST = "cheapest"
    BEST_RATED = "best_rated"


class PreferenceLoadingMode(str, Enum):
    """
    Mode for loading user preferences during trip planning.
    
    SUMMARY_ONLY: Always include compact summary (~50 tokens) in prompt.
                  Faster, simpler, sufficient for basic personalization.
                  
    TOOL_BINDING: Include summary + bind load_full_preferences tool.
                  LLM can call tool when detailed prefs needed
                  (loyalty numbers, dietary restrictions, accessibility).
                  Adds ~1-2s latency when tool is called.
    """
    SUMMARY_ONLY = "summary"
    TOOL_BINDING = "tool_binding"


# Default selection criteria from environment or fallback to first_available
DEFAULT_SELECTION_CRITERIA = SelectionCriteria(
    os.getenv("OPTION_SELECTION_CRITERIA", "first_available")
)

# Preference loading mode from environment or fallback to summary
# Set PREFERENCE_LOADING_MODE=tool_binding to enable LLM tool calling for detailed prefs
PREFERENCE_LOADING_MODE = PreferenceLoadingMode(
    os.getenv("PREFERENCE_LOADING_MODE", "summary")
)
