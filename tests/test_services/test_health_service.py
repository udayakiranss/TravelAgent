"""
Unit tests for HealthService.
"""
import pytest
from unittest.mock import Mock, patch
from sqlalchemy.exc import SQLAlchemyError

from api.services.health_service import HealthService


class TestHealthService:
    """Tests for HealthService."""
    
    def test_check_health_all_healthy(self, mock_session, mock_llm):
        """Test health check when all services are healthy."""
        service = HealthService(mock_session, mock_llm)
        
        result = service.check_health()
        
        assert result.status == "healthy"
        assert result.database == "connected"
        assert result.llm == "available"
    
    def test_check_health_degraded_no_llm(self, mock_session):
        """Test health check when LLM is unavailable."""
        service = HealthService(mock_session, None)
        
        result = service.check_health()
        
        assert result.status == "degraded"
        assert result.database == "connected"
        assert result.llm == "unavailable"
    
    @patch('api.services.health_service.text')
    def test_check_health_unhealthy_database(self, mock_text, mock_llm):
        """Test health check when database is down."""
        # Create a mock session that raises an error
        mock_session = Mock()
        mock_session.execute.side_effect = SQLAlchemyError("Connection failed")
        
        service = HealthService(mock_session, mock_llm)
        
        result = service.check_health()
        
        assert result.status == "unhealthy"
        assert result.database == "error"
        assert result.llm == "available"
    
    def test_check_health_unhealthy_both(self, mock_llm):
        """Test health check when both database and LLM are down."""
        mock_session = Mock()
        mock_session.execute.side_effect = SQLAlchemyError("Connection failed")
        
        service = HealthService(mock_session, None)
        
        result = service.check_health()
        
        assert result.status == "unhealthy"
        assert result.database == "error"
        assert result.llm == "unavailable"
