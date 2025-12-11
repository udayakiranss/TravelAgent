"""
Health check routes.
"""
from fastapi import APIRouter, Depends

from api.schemas import HealthResponse
from api.dependencies import get_health_service
from api.services.health_service import HealthService
from utils.logger import get_logger

logger = get_logger()

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Check API, database, and LLM status"
)
def health_check(
    service: HealthService = Depends(get_health_service),
):
    """Health check endpoint."""
    return service.check_health()
