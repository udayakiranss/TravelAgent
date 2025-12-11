"""
Health service for checking system status.
"""
from typing import Optional
from sqlmodel import Session
from sqlalchemy import text

from agents.llm_provider import LLMProvider
from api.schemas import HealthResponse
from utils.logger import get_logger

logger = get_logger()


class HealthService:
    """Service for health check operations."""
    
    def __init__(self, db: Session, llm: Optional[LLMProvider]):
        """
        Initialize health service.
        
        Args:
            db: Database session
            llm: Optional LLM provider
        """
        self.db = db
        self.llm = llm
    
    def check_health(self) -> HealthResponse:
        """
        Check health of database and LLM services.
        
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
        
        # Check LLM
        llm_status = "available" if self.llm else "unavailable"
        
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
