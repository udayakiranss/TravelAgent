"""
Shared fixtures for service layer tests.
"""
import pytest
from unittest.mock import Mock, MagicMock
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool
from datetime import datetime

from database.models import Itinerary, ChatHistory, UserPreferences
from agents.orchestration import Orchestrator
from agents.planning import TravelPlanner
from agents.core import LLMProvider
from api.context import TravelContext


@pytest.fixture
def mock_session():
    """Create an in-memory SQLite database session for testing."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    
    with Session(engine) as session:
        yield session
    
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def sample_itinerary(mock_session):
    """Create a sample itinerary in the database."""
    itinerary = Itinerary(
        id="itin-test-123",
        traveler_id="user_123",
        original_query="Test query",
        status="draft",
        version=1,
    )
    mock_session.add(itinerary)
    mock_session.commit()
    mock_session.refresh(itinerary)
    return itinerary


@pytest.fixture
def sample_confirmed_itinerary(mock_session):
    """Create a sample confirmed itinerary."""
    itinerary = Itinerary(
        id="itin-confirmed-123",
        traveler_id="user_123",
        status="confirmed",
        version=2,
    )
    mock_session.add(itinerary)
    mock_session.commit()
    mock_session.refresh(itinerary)
    return itinerary


@pytest.fixture
def sample_preferences(mock_session):
    """Create sample user preferences."""
    prefs = UserPreferences(
        traveler_id="user_123",
        flight_preferences={"seat_type": "aisle"},
        hotel_preferences={"min_rating": 4},
    )
    mock_session.add(prefs)
    mock_session.commit()
    mock_session.refresh(prefs)
    return prefs


@pytest.fixture
def mock_orchestrator():
    """Create a mock orchestrator."""
    orch = Mock(spec=Orchestrator)
    return orch


@pytest.fixture
def mock_planner():
    """Create a mock planner."""
    planner = Mock(spec=TravelPlanner)
    return planner


@pytest.fixture
def mock_llm():
    """Create a mock LLM provider."""
    llm = Mock(spec=LLMProvider)
    llm.model_name = "test-model"
    llm.model_provider = "test-provider"
    return llm


@pytest.fixture
def mock_context(mock_session, mock_llm):
    """Create a mock TravelContext."""
    from unittest.mock import Mock
    from llm import ModelInvocationStrategy
    mock_strategy = Mock(spec=ModelInvocationStrategy)
    mock_strategy.get_llm_for_use_case.return_value = mock_llm
    ctx = TravelContext(
        session=mock_session,
        model_strategy=mock_strategy,
        traveler_id="user_123",
    )
    return ctx


@pytest.fixture
def sample_chat_messages(mock_session, sample_itinerary):
    """Create sample chat messages."""
    messages = [
        ChatHistory(
            itinerary_id=sample_itinerary.id,
            role="user",
            content="Plan a trip to Paris",
            timestamp=datetime.now(),
        ),
        ChatHistory(
            itinerary_id=sample_itinerary.id,
            role="assistant",
            content="I'll help you plan your trip.",
            timestamp=datetime.now(),
        ),
    ]
    for msg in messages:
        mock_session.add(msg)
    mock_session.commit()
    return messages
