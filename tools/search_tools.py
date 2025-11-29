from langchain.tools import tool
from typing import Dict, Any
from data.flights import FLIGHTS
from data.hotels import HOTELS
from data.cars import CARS

@tool
def search_flights(query: Dict[str, Any]):
    """Search flights using {from, to, date}. Returns list of flights."""
    frm, to, date = query.get('from'), query.get('to'), query.get('date')
    results = [f for f in FLIGHTS if f['from']==frm and f['to']==to and f['date']==date]
    return results

@tool
def search_hotels(query: Dict[str, Any]):
    """Search hotels by city."""
    city = query.get('city')
    results = [h for h in HOTELS if h['city']==city]
    return results

@tool
def search_cars(query: Dict[str, Any]):
    """Search cars by city."""
    city = query.get('city')
    results = [c for c in CARS if c['city']==city]
    return results
