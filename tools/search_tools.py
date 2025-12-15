from langchain_core.tools import tool
from typing import Dict, Any
from data.flights import FLIGHTS
from data.hotels import HOTELS
from data.cars import CARS

def _normalize_airport_code(code: str) -> str:
    """Normalize airport codes to match flight data.
    
    Maps specific airport codes to city codes used in FLIGHTS data:
    - JFK, LGA, EWR -> NYC
    - LHR, LGW, STN, LCY, LTN -> LON
    - CDG, ORY -> PAR
    """
    if not code:
        return code
    code = code.upper()
    # NYC area airports
    if code in ['JFK', 'LGA', 'EWR']:
        return 'NYC'
    # London area airports
    if code in ['LHR', 'LGW', 'STN', 'LCY', 'LTN']:
        return 'LON'
    # Paris area airports
    if code in ['CDG', 'ORY']:
        return 'PAR'
    # Return as-is if no mapping found
    return code

@tool
def search_flights(query: Dict[str, Any]):
    """Search flights using {from, to, date}. Returns list of flights."""
    # Handle multiple parameter name variations
    frm = query.get('from') or query.get('origin') or ''
    to = query.get('to') or query.get('destination') or ''
    # Handle date variations: 'date', 'departure_date', 'departureDate'
    date = query.get('date') or query.get('departure_date') or query.get('departureDate') or ''
    
    if not frm or not to:
        return []
    
    # Normalize airport codes
    frm = _normalize_airport_code(frm)
    to = _normalize_airport_code(to)
    
    # If date is provided, filter by date; otherwise return all matching routes
    if date:
        results = [f for f in FLIGHTS if f['from']==frm and f['to']==to and f['date']==date]
    else:
        # If no date, return all flights for the route
        results = [f for f in FLIGHTS if f['from']==frm and f['to']==to]
    
    return results

def _normalize_city_code(city: str) -> str:
    """Normalize city name to airport code format used in HOTELS/CARS data."""
    if not city:
        return city
    city = city.strip().upper()
    
    # City name mappings
    city_mappings = {
        'LONDON': 'LON',
        'NEW YORK': 'NYC',
        'NEW YORK CITY': 'NYC',
        'SAN FRANCISCO': 'SFO',
        'SF': 'SFO',
        'DUBAI': 'DXB',
        'DELHI': 'DEL',
        'MUMBAI': 'BOM',
        'BANGALORE': 'BLR',
        'BENGALURU': 'BLR',
        'CHENNAI': 'MAA',
        'HYDERABAD': 'HYD',
        'KOLKATA': 'CCU',
        'PARIS': 'PAR',
        'TOKYO': 'TYO',
        'SYDNEY': 'SYD',
    }
    
    # Check if it's already a code (3 letters) or if we have a mapping
    if len(city) == 3 and city.isalpha():
        return city
    elif city in city_mappings:
        return city_mappings[city]
    else:
        return city[:3] if len(city) >= 3 else city

@tool
def search_hotels(query: Dict[str, Any]):
    """Search hotels by city."""
    city = query.get('city', '')
    if not city:
        return []
    
    # Normalize city name to airport code format
    city = _normalize_city_code(city)
    results = [h for h in HOTELS if h['city']==city]
    return results

@tool
def search_cars(query: Dict[str, Any]):
    """Search cars by city."""
    city = query.get('city', '')
    if not city:
        return []
    
    # Normalize city name to airport code format
    city = _normalize_city_code(city)
    results = [c for c in CARS if c['city']==city]
    return results
