"""
API routes module.
Combines all route modules into a single router with /api/v1 prefix.
"""
from fastapi import APIRouter

from .health import router as health_router
from .search import router as search_router
from .itineraries import router as itineraries_router
from .preferences import router as preferences_router
from .agent import router as agent_router

# Create main router with /api/v1 prefix
router = APIRouter(prefix="/api/v1", tags=["Travel Booking API"])

# Include all sub-routers
router.include_router(health_router)
router.include_router(search_router)
router.include_router(itineraries_router)
router.include_router(preferences_router)
router.include_router(agent_router)

__all__ = ["router"]
