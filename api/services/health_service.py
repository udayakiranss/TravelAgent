"""
Health service for checking system status.
"""
from typing import Optional, TYPE_CHECKING
from sqlmodel import Session
from sqlalchemy import text

from api.schemas import HealthResponse
from utils.logger import get_logger

if TYPE_CHECKING:
    from llm import ModelInvocationStrategy
    from llm.strategy.use_cases import UseCase

logger = get_logger()


class HealthService:
    """Service for health check operations."""
    
    def __init__(self, db: Session, strategy: Optional["ModelInvocationStrategy"] = None):
        """
        Initialize health service.
        
        Args:
            db: Database session
            strategy: Optional Model Invocation Strategy (preferred)
                     If None, LLM health check will show as unavailable
        """
        self.db = db
        self.strategy = strategy
    
    def check_health(self) -> HealthResponse:
        """
        Check health of database and LLM services.
        
        Uses ModelInvocationStrategy to check LLM availability by attempting
        to get an LLM for a use case (planner).
        
        Returns:
            HealthResponse with status of all components
        """
        logger.debug("Health check requested")
        
        # Check database
        db_status = "connected"
        try:
            self.db.execute(text("SELECT 1"))
        except Exception as e:
            db_status = "error"
            logger.error(f"Database health check failed: {e}")
        
        # Check LLM via ModelInvocationStrategy
        llm_status = "unavailable"
        if self.strategy:
            try:
                # Try to get an LLM for planner use case to verify configuration is valid
                from llm.strategy.use_cases import UseCase
                llm = self.strategy.get_llm_for_use_case(UseCase.PLANNER)
                llm_status = "available" if llm else "unavailable"
            except Exception as e:
                logger.warning(f"LLM health check failed: {e}")
                llm_status = "unavailable"
        else:
            logger.debug("No ModelInvocationStrategy provided, LLM status unavailable")
        
        # Overall status
        overall = "healthy"
        if db_status == "error":
            overall = "unhealthy"
        elif llm_status == "unavailable":
            overall = "degraded"
        
        logger.info(f"Health check: status={overall}, db={db_status}, llm={llm_status}")
        
        return HealthResponse(
            status=overall,
            database=db_status,
            llm=llm_status,
        )
