# alias_resolver.py
# Shared utility for loading and querying city/airport alias map
from typing import Any, Dict, List, Optional
import json
import os

from utils.logger import get_logger

logger = get_logger()

# Minimal Tier A alias map (fallback if file missing)
TIER_A_ALIASES: List[Dict[str, Any]] = [
    {
        "city": "New York",
        "country": "US",
        "primary_airport": "JFK",
        "airports": ["JFK", "LGA", "EWR", "NYC"],
        "aliases": ["new york", "nyc", "jfk", "laguardia", "lga", "ewr"],
    },
    {
        "city": "London",
        "country": "UK",
        "primary_airport": "LHR",
        "airports": ["LHR", "LGW", "STN", "LCY", "LTN", "LON"],
        "aliases": ["london", "lon", "lhr", "heathrow", "gatwick", "lgw", "stn", "lcy", "ltn"],
    },
    {
        "city": "Paris",
        "country": "FR",
        "primary_airport": "CDG",
        "airports": ["CDG", "ORY", "PAR"],
        "aliases": ["paris", "par", "cdg", "ory"],
    },
    {
        "city": "San Francisco",
        "country": "US",
        "primary_airport": "SFO",
        "airports": ["SFO"],
        "aliases": ["san francisco", "sf", "sfo"],
    },
    {
        "city": "Los Angeles",
        "country": "US",
        "primary_airport": "LAX",
        "airports": ["LAX"],
        "aliases": ["los angeles", "la", "lax"],
    },
    {
        "city": "Chicago",
        "country": "US",
        "primary_airport": "ORD",
        "airports": ["ORD", "MDW"],
        "aliases": ["chicago", "chi", "ord", "ohare", "mdw", "midway"],
    },
    {
        "city": "Washington",
        "country": "US",
        "primary_airport": "DCA",
        "airports": ["DCA", "IAD"],
        "aliases": ["washington", "dc", "dca", "iad"],
    },
]


class AliasResolver:
    """Utility for loading and querying city/airport alias map."""
    
    def __init__(self, alias_map_path: Optional[str] = None):
        """
        Initialize alias resolver.
        
        Args:
            alias_map_path: Path to JSON file with alias mappings.
                          If None, uses default path in data/ directory.
        """
        if alias_map_path is None:
            alias_map_path = os.path.join(
                os.path.dirname(__file__), "..", "data", "city_airport_aliases.json"
            )
        self.alias_map_path = alias_map_path
        self.alias_map = self._load_alias_map()
    
    def _load_alias_map(self) -> List[Dict[str, Any]]:
        """
        Load alias map from file or use defaults.
        
        Returns:
            List of alias map entries with _alias_set precomputed for fast lookup.
        """
        alias_entries: List[Dict[str, Any]] = []
        if os.path.exists(self.alias_map_path):
            try:
                with open(self.alias_map_path, "r", encoding="utf-8") as f:
                    alias_entries = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load alias map from {self.alias_map_path}: {e}")

        # Fallback to Tier A if file missing/empty
        if not alias_entries:
            alias_entries = TIER_A_ALIASES

        # Build alias sets for fast lookup
        for entry in alias_entries:
            aliases = entry.get("aliases", [])
            airports = entry.get("airports", [])
            alias_set = {a.lower() for a in aliases} | {a.lower() for a in airports}
            entry["_alias_set"] = alias_set
        
        logger.debug(f"AliasResolver: Loaded {len(alias_entries)} alias entries")
        return alias_entries
    
    def find_city_by_airport(self, code: str) -> Optional[Dict[str, Any]]:
        """
        Find city entry by airport code (IATA code).
        
        Args:
            code: Airport code (e.g., "JFK", "LHR")
        
        Returns:
            City entry dict if found, None otherwise
        """
        for entry in self.alias_map:
            if code in entry.get("airports", []):
                return entry
        return None
    
    def find_by_alias(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Find city entry by alias (city name, airport name, etc.).
        
        Args:
            text: Alias text to search for (case-insensitive)
        
        Returns:
            City entry dict if found, None otherwise
        """
        lower = text.lower().strip()
        for entry in self.alias_map:
            if lower in entry.get("_alias_set", set()):
                return entry
        return None
    
    def get_alias_map(self) -> List[Dict[str, Any]]:
        """
        Get the full alias map.
        
        Returns:
            List of all alias map entries
        """
        return self.alias_map
