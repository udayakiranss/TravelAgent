"""
Search routes for flights, hotels, and cars.
"""
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends

from api.schemas import FlightSearchRequest, HotelSearchRequest, CarSearchRequest
from api.dependencies import get_search_service
from api.services.search_service import SearchService
from utils.logger import get_logger

logger = get_logger()

router = APIRouter(tags=["Search"])


@router.post(
    "/search/flights",
    response_model=List[Dict[str, Any]],
    summary="Search flights",
    description="Search for available flights. Use airport codes (BLR, DXB) and dates (YYYY-MM-DD)."
)
def search_flights(
    request: FlightSearchRequest,
    service: SearchService = Depends(get_search_service),
):
    """Search for flights without creating an itinerary."""
    try:
        return service.search_flights(request.origin, request.destination, request.date)
    except Exception as e:
        logger.error(f"Flight search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/search/hotels",
    response_model=List[Dict[str, Any]],
    summary="Search hotels",
    description="Search for available hotels. Use city codes (DXB, LON, NYC)."
)
def search_hotels(
    request: HotelSearchRequest,
    service: SearchService = Depends(get_search_service),
):
    """Search for hotels without creating an itinerary."""
    try:
        return service.search_hotels(request.city)
    except Exception as e:
        logger.error(f"Hotel search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/search/cars",
    response_model=List[Dict[str, Any]],
    summary="Search cars",
    description="Search for available car rentals. Use city codes (DXB, LON, NYC)."
)
def search_cars(
    request: CarSearchRequest,
    service: SearchService = Depends(get_search_service),
):
    """Search for car rentals without creating an itinerary."""
    try:
        return service.search_cars(request.city)
    except Exception as e:
        logger.error(f"Car search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
