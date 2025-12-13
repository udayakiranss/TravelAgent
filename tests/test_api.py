"""
API tests for Travel Booking Web Application.
Uses TestClient from FastAPI with LLM mocking strategy.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from main_web import app
from api.dependencies import get_db, get_llm, get_orchestrator
from agents.orchestration import Orchestrator
from database.models import Itinerary, ChatHistory


# =============================================================================
# Test Database Setup
# =============================================================================

@pytest.fixture(name="session")
def session_fixture():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    
    with Session(engine) as session:
        yield session
    
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="client")
def client_fixture(session: Session):
    """Create test client with overridden database dependency."""
    
    def get_session_override():
        return session
    
    def get_llm_override():
        # Return None for most tests (no LLM)
        return None
    
    def get_orchestrator_override():
        # Return fresh orchestrator with no LLM
        orch = Orchestrator(llm=None)
        orch.llm = None
        return orch
    
    app.dependency_overrides[get_db] = get_session_override
    app.dependency_overrides[get_llm] = get_llm_override
    app.dependency_overrides[get_orchestrator] = get_orchestrator_override
    
    client = TestClient(app)
    yield client
    
    app.dependency_overrides.clear()


@pytest.fixture(name="mock_llm")
def mock_llm_fixture():
    """Create a mock LLM provider for testing LLM operations."""
    mock = Mock()
    mock.invoke.return_value = '{"component": "flight", "action": "search_new", "parameters": {}}'
    mock.invoke_structured.return_value = {
        "needs": ["flight", "hotel"],
        "from": "NYC",
        "to": "LON",
        "date": "2025-08-12"
    }
    return mock


@pytest.fixture(name="client_with_llm")
def client_with_llm_fixture(session: Session, mock_llm):
    """Create test client with mocked LLM provider."""
    
    def get_session_override():
        return session
    
    def get_llm_override():
        return mock_llm
    
    def get_orchestrator_override():
        # Return fresh orchestrator with mocked LLM
        return Orchestrator(llm=mock_llm)
    
    app.dependency_overrides[get_db] = get_session_override
    app.dependency_overrides[get_llm] = get_llm_override
    app.dependency_overrides[get_orchestrator] = get_orchestrator_override
    
    client = TestClient(app)
    yield client
    
    app.dependency_overrides.clear()


# =============================================================================
# Root and Health Check Tests
# =============================================================================

class TestRootAndHealth:
    """Tests for root and health endpoints."""
    
    def test_root(self, client: TestClient):
        """Test root endpoint returns API info."""
        response = client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["name"] == "Travel Booking API"
        assert data["version"] == "1.0.0"
        assert "docs" in data
    
    def test_health_check(self, client: TestClient):
        """Test health check endpoint."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
        assert data["database"] == "connected"
        assert "llm" in data
        assert "timestamp" in data


# =============================================================================
# Itinerary CRUD Tests
# =============================================================================

class TestItineraryCRUD:
    """Tests for itinerary CRUD operations."""
    
    def test_create_itinerary(self, client: TestClient):
        """Test creating a new itinerary."""
        response = client.post(
            "/api/v1/itineraries",
            json={
                "traveler_id": "user_123",
                "original_query": "Plan a trip to Paris"
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        
        assert data["traveler_id"] == "user_123"
        assert data["original_query"] == "Plan a trip to Paris"
        assert data["status"] == "draft"
        assert data["version"] == 1
        assert data["id"].startswith("itin-")
    
    def test_create_itinerary_validation_error(self, client: TestClient):
        """Test validation error when traveler_id is missing."""
        response = client.post(
            "/api/v1/itineraries",
            json={"original_query": "Test"}  # Missing traveler_id
        )
        
        assert response.status_code == 422
        data = response.json()
        assert data["error"] == "VALIDATION_ERROR"
    
    def test_get_itinerary(self, client: TestClient, session: Session):
        """Test getting itinerary by ID."""
        # Create an itinerary directly in DB
        itinerary = Itinerary(
            traveler_id="user_456",
            original_query="Test query"
        )
        session.add(itinerary)
        session.commit()
        session.refresh(itinerary)
        
        response = client.get(f"/api/v1/itineraries/{itinerary.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == itinerary.id
        assert data["traveler_id"] == "user_456"
    
    def test_get_itinerary_not_found(self, client: TestClient):
        """Test 404 when itinerary doesn't exist."""
        response = client.get("/api/v1/itineraries/itin-nonexistent")
        
        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error"] == "ITINERARY_NOT_FOUND"
    
    def test_list_itineraries_empty(self, client: TestClient):
        """Test listing itineraries when empty."""
        response = client.get("/api/v1/itineraries")
        
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1
    
    def test_list_itineraries_with_data(self, client: TestClient, session: Session):
        """Test listing itineraries with data."""
        # Create multiple itineraries
        for i in range(3):
            itinerary = Itinerary(
                traveler_id=f"user_{i}",
                status="draft" if i < 2 else "confirmed"
            )
            session.add(itinerary)
        session.commit()
        
        response = client.get("/api/v1/itineraries")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3
    
    def test_list_itineraries_filter_by_status(self, client: TestClient, session: Session):
        """Test filtering itineraries by status."""
        # Create itineraries with different statuses
        for status in ["draft", "draft", "confirmed"]:
            itinerary = Itinerary(traveler_id="test_user", status=status)
            session.add(itinerary)
        session.commit()
        
        response = client.get("/api/v1/itineraries?status=draft")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
    
    def test_list_itineraries_pagination(self, client: TestClient, session: Session):
        """Test pagination of itinerary list."""
        # Create 25 itineraries
        for i in range(25):
            itinerary = Itinerary(traveler_id=f"user_{i}")
            session.add(itinerary)
        session.commit()
        
        # Get page 1
        response = client.get("/api/v1/itineraries?page=1&limit=10")
        data = response.json()
        
        assert data["total"] == 25
        assert len(data["items"]) == 10
        assert data["has_more"] is True
        
        # Get page 3
        response = client.get("/api/v1/itineraries?page=3&limit=10")
        data = response.json()
        
        assert len(data["items"]) == 5
        assert data["has_more"] is False
    
    def test_update_itinerary(self, client: TestClient, session: Session):
        """Test updating an itinerary with optimistic locking."""
        # Create itinerary
        itinerary = Itinerary(traveler_id="user_123")
        session.add(itinerary)
        session.commit()
        session.refresh(itinerary)
        
        response = client.put(
            f"/api/v1/itineraries/{itinerary.id}",
            json={
                "version": 1,
                "flight_reservation": {"airline": "Test Air", "price": 500}
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == 2
        assert data["flight_reservation"]["airline"] == "Test Air"
        assert data["total_cost"] == 500
    
    def test_update_itinerary_version_conflict(self, client: TestClient, session: Session):
        """Test version conflict error."""
        # Create itinerary with version 2
        itinerary = Itinerary(traveler_id="user_123", version=2)
        session.add(itinerary)
        session.commit()
        session.refresh(itinerary)
        
        # Try to update with wrong version
        response = client.put(
            f"/api/v1/itineraries/{itinerary.id}",
            json={
                "version": 1,  # Wrong version
                "flight_reservation": {"airline": "Test Air"}
            }
        )
        
        assert response.status_code == 409
        data = response.json()
        assert data["detail"]["error"] == "VERSION_CONFLICT"
    
    def test_delete_itinerary(self, client: TestClient, session: Session):
        """Test deleting a draft itinerary."""
        # Create draft itinerary
        itinerary = Itinerary(traveler_id="user_123", status="draft")
        session.add(itinerary)
        session.commit()
        session.refresh(itinerary)
        
        response = client.delete(f"/api/v1/itineraries/{itinerary.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
    
    def test_delete_confirmed_itinerary_fails(self, client: TestClient, session: Session):
        """Test that confirmed itineraries cannot be deleted."""
        # Create confirmed itinerary
        itinerary = Itinerary(traveler_id="user_123", status="confirmed")
        session.add(itinerary)
        session.commit()
        session.refresh(itinerary)
        
        response = client.delete(f"/api/v1/itineraries/{itinerary.id}")
        
        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "INVALID_STATUS_TRANSITION"


# =============================================================================
# Status Transition Tests
# =============================================================================

class TestStatusTransitions:
    """Tests for status workflow transitions."""
    
    def test_confirm_draft(self, client: TestClient, session: Session):
        """Test confirming a draft itinerary."""
        itinerary = Itinerary(traveler_id="user_123", status="draft")
        session.add(itinerary)
        session.commit()
        session.refresh(itinerary)
        
        response = client.post(f"/api/v1/itineraries/{itinerary.id}/confirm")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "confirmed"
    
    def test_confirm_already_confirmed_fails(self, client: TestClient, session: Session):
        """Test that confirming an already confirmed itinerary fails."""
        itinerary = Itinerary(traveler_id="user_123", status="confirmed")
        session.add(itinerary)
        session.commit()
        session.refresh(itinerary)
        
        response = client.post(f"/api/v1/itineraries/{itinerary.id}/confirm")
        
        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "INVALID_STATUS_TRANSITION"
    
    def test_cancel_draft(self, client: TestClient, session: Session):
        """Test cancelling a draft itinerary."""
        itinerary = Itinerary(traveler_id="user_123", status="draft")
        session.add(itinerary)
        session.commit()
        session.refresh(itinerary)
        
        response = client.post(f"/api/v1/itineraries/{itinerary.id}/cancel")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"
        assert data["cancelled_at"] is not None
    
    def test_cancel_confirmed(self, client: TestClient, session: Session):
        """Test cancelling a confirmed itinerary."""
        itinerary = Itinerary(traveler_id="user_123", status="confirmed")
        session.add(itinerary)
        session.commit()
        session.refresh(itinerary)
        
        response = client.post(f"/api/v1/itineraries/{itinerary.id}/cancel")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"
    
    def test_cancel_already_cancelled_fails(self, client: TestClient, session: Session):
        """Test that cancelling an already cancelled itinerary fails."""
        itinerary = Itinerary(traveler_id="user_123", status="cancelled")
        session.add(itinerary)
        session.commit()
        session.refresh(itinerary)
        
        response = client.post(f"/api/v1/itineraries/{itinerary.id}/cancel")
        
        assert response.status_code == 400


# =============================================================================
# LLM Operations Tests
# =============================================================================

class TestLLMOperations:
    """Tests for LLM-powered operations (with mocked LLM)."""
    
    def test_plan_trip_no_llm(self, client: TestClient):
        """Test that plan endpoint returns 400 MISSING_INFORMATION when LLM is unavailable and rule-based fails."""
        response = client.post(
            "/api/v1/agent/plan",
            json={
                "query": "Plan a trip to Paris",
                "traveler_id": "user_123"
            }
        )
        
        # With new robust Planner, missing LLM triggers rule-based fallback.
        # "Plan a trip to Paris" misses 'from' and 'date', so it becomes needs_clarification (400)
        assert response.status_code == 400
        data = response.json()
        assert data["code"] == "MISSING_INFORMATION"

    def test_plan_trip_success(self, client_with_llm: TestClient, mock_llm: MagicMock):
        """Test successful trip planning with mocked LLM."""
        # Mock LLM response for intent parsing
        mock_llm.invoke_structured.return_value = {
            "needs": ["flight"],
            "from": "NYC",
            "to": "PAR",
            "date": "2025-06-15"
        }
        
        # Mock LLM response for summary generation (if any)
        mock_llm.invoke.return_value = "Mock summary"

        response = client_with_llm.post(
            "/api/v1/agent/plan",
            json={
                "query": "Plan a flight from NYC to Paris on 2025-06-15",
                "traveler_id": "user_123",
                "include_summary": False
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "itinerary_id" in data
        assert "flight_reservation" in data


    
    def test_modify_no_llm(self, client: TestClient, session: Session):
        """Test that modify endpoint returns 500 when model_strategy is unavailable."""
        # Create itinerary
        itinerary = Itinerary(traveler_id="user_123", status="draft")
        session.add(itinerary)
        session.commit()
        session.refresh(itinerary)
        
        response = client.post(
            f"/api/v1/itineraries/{itinerary.id}/modify",
            json={
                "instruction": "Change flight to tomorrow",
                "traveler_id": "user_123"
            }
        )
        
        # Now returns 500 because strategy is required (not 503 for unavailable LLM)
        # This is expected behavior - strategy should always be available in production
        assert response.status_code == 500
        assert "model_strategy is required" in response.json()["detail"]["message"].lower() or "strategy" in response.json()["detail"]["message"].lower()
    
    def test_modify_confirmed_fails(self, client_with_llm: TestClient, session: Session):
        """Test that modifying a confirmed itinerary fails."""
        # Need to reset the session dependency for client_with_llm
        itinerary = Itinerary(traveler_id="user_123", status="confirmed")
        session.add(itinerary)
        session.commit()
        session.refresh(itinerary)
        
        response = client_with_llm.post(
            f"/api/v1/itineraries/{itinerary.id}/modify",
            json={
                "instruction": "Change flight to tomorrow",
                "traveler_id": "user_123"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "Cannot modify itinerary" in data["message"]


# =============================================================================
# Integration Test
# =============================================================================

class TestIntegration:
    """Integration tests for complete workflows."""
    
    def test_full_draft_to_confirmed_workflow(self, client: TestClient):
        """Test complete workflow from creation to confirmation."""
        # 1. Create itinerary
        create_response = client.post(
            "/api/v1/itineraries",
            json={
                "traveler_id": "user_workflow",
                "original_query": "Trip to Paris"
            }
        )
        assert create_response.status_code == 201
        itinerary_id = create_response.json()["id"]
        
        # 2. Add flight
        update_response = client.put(
            f"/api/v1/itineraries/{itinerary_id}",
            json={
                "version": 1,
                "flight_reservation": {"airline": "Air France", "price": 500}
            }
        )
        assert update_response.status_code == 200
        assert update_response.json()["version"] == 2
        
        # 3. Add hotel
        update_response = client.put(
            f"/api/v1/itineraries/{itinerary_id}",
            json={
                "version": 2,
                "hotel_reservation": {"name": "Paris Hotel", "price": 300}
            }
        )
        assert update_response.status_code == 200
        assert update_response.json()["total_cost"] == 800
        
        # 4. Confirm itinerary
        confirm_response = client.post(f"/api/v1/itineraries/{itinerary_id}/confirm")
        assert confirm_response.status_code == 200
        assert confirm_response.json()["status"] == "confirmed"
        
        # 5. Verify updates no longer allowed
        update_response = client.put(
            f"/api/v1/itineraries/{itinerary_id}",
            json={
                "version": 3,
                "car_reservation": {"company": "Hertz", "price": 100}
            }
        )
        assert update_response.status_code == 400

