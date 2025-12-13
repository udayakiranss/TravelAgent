"""
Unit tests for HealthService.
"""
import pytest
from unittest.mock import Mock, patch
from sqlalchemy.exc import SQLAlchemyError

from api.services.health_service import HealthService


class TestHealthService:
    """Tests for HealthService."""
    
    def test_check_health_all_healthy(self, mock_session):
        """Test health check when all services are healthy."""
        # Create mock strategy that returns an LLM
        mock_strategy = Mock()
        mock_llm = Mock()
        mock_strategy.get_llm_for_use_case.return_value = mock_llm
        
        service = HealthService(mock_session, mock_strategy)
        
        result = service.check_health()
        
        assert result.status == "healthy"
        assert result.database == "connected"
        assert result.llm == "available"
        mock_strategy.get_llm_for_use_case.assert_called_once()
    
    def test_check_health_degraded_no_strategy(self, mock_session):
        """Test health check when ModelInvocationStrategy is unavailable."""
        service = HealthService(mock_session, None)
        
        result = service.check_health()
        
        assert result.status == "degraded"
        assert result.database == "connected"
        assert result.llm == "unavailable"
    
    @patch('api.services.health_service.text')
    def test_check_health_unhealthy_database(self, mock_text):
        """Test health check when database is down."""
        # Create a mock session that raises an error
        mock_session = Mock()
        mock_session.execute.side_effect = SQLAlchemyError("Connection failed")
        
        # Create mock strategy that returns an LLM
        mock_strategy = Mock()
        mock_llm = Mock()
        mock_strategy.get_llm_for_use_case.return_value = mock_llm
        
        service = HealthService(mock_session, mock_strategy)
        
        result = service.check_health()
        
        assert result.status == "unhealthy"
        assert result.database == "error"
        assert result.llm == "available"
    
    def test_check_health_unhealthy_both(self):
        """Test health check when both database and LLM are down."""
        # Create a mock session that raises an error
        mock_session = Mock()
        mock_session.execute.side_effect = SQLAlchemyError("Connection failed")
        
        service = HealthService(mock_session, None)
        
        result = service.check_health()
        
        assert result.status == "unhealthy"
        assert result.database == "error"
        assert result.llm == "unavailable"
    
    def test_check_health_strategy_raises_exception(self, mock_session):
        """Test health check when strategy raises an exception."""
        mock_strategy = Mock()
        mock_strategy.get_llm_for_use_case.side_effect = Exception("Config error")
        
        service = HealthService(mock_session, mock_strategy)
        
        result = service.check_health()
        
        assert result.status == "degraded"
        assert result.database == "connected"
        assert result.llm == "unavailable"
