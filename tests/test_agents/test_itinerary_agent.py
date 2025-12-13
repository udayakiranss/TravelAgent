import pytest
from agents.domain.itinerary_agent import ItineraryAgent, build_itinerary_tool, get_itinerary_tool
from api.context import TravelContext
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

class TestItineraryAgent:
    
    @pytest.fixture
    def session(self):
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
    def agent(self, mock_llm):
        return ItineraryAgent(llm=mock_llm)
    
    @pytest.fixture
    def ctx(self, session, mock_llm):
        """Create a TravelContext for testing."""
        from unittest.mock import Mock
        from llm import ModelInvocationStrategy
        mock_strategy = Mock(spec=ModelInvocationStrategy)
        mock_strategy.get_llm_for_use_case.return_value = mock_llm
        return TravelContext(session=session, model_strategy=mock_strategy, traveler_id="test_traveler_1")

    def test_build_itinerary(self, agent, ctx):
        """Test building an itinerary using the agent's build method."""
        flight_reservation = {"id": "FL-101", "price": 500}
        hotel_reservation = {"id": "HT-101", "price": 300}
        car_reservation = None
        
        result = agent.build(
            flight_reservation=flight_reservation,
            hotel_reservation=hotel_reservation,
            car_reservation=car_reservation,
            ctx=ctx
        )
        
        # build() returns an Itinerary object
        assert result.total_cost == 800
        assert result.flight_reservation == flight_reservation
        assert result.hotel_reservation == hotel_reservation
        assert result.id is not None

    def test_get_itinerary(self, agent, ctx):
        """Test getting an itinerary by ID."""
        # First create an itinerary
        flight_reservation = {"id": "FL-101", "price": 500}
        created = agent.build(
            flight_reservation=flight_reservation,
            hotel_reservation=None,
            car_reservation=None,
            ctx=ctx
        )
        itinerary_id = created.id
        
        # Update context with itinerary_id and get it (get() uses ctx.itinerary_id)
        from api.context import TravelContext
        ctx_with_id = TravelContext(
            session=ctx.session,
            model_strategy=ctx.model_strategy,
            traveler_id=ctx.traveler_id,
            itinerary_id=itinerary_id
        )
        result = agent.get(ctx=ctx_with_id)
        # get() returns Itinerary object or None
        assert result is not None
        assert result.id == itinerary_id
        assert result.total_cost == 500
        assert result.flight_reservation == flight_reservation

    def test_update_itinerary(self, agent, ctx):
        """Test updating an existing itinerary."""
        # Create initial itinerary
        flight_reservation = {"id": "FL-101", "price": 500}
        created = agent.build(
            flight_reservation=flight_reservation,
            hotel_reservation=None,
            car_reservation=None,
            ctx=ctx
        )
        itinerary_id = created.id
        
        # Update context with itinerary_id and itinerary for update()
        from api.context import TravelContext
        ctx_with_itinerary = TravelContext(
            session=ctx.session,
            model_strategy=ctx.model_strategy,
            traveler_id=ctx.traveler_id,
            itinerary_id=itinerary_id,
            itinerary=created
        )
        
        # Update with hotel (update() returns Itinerary object)
        hotel_reservation = {"id": "HT-101", "price": 300}
        updated = agent.update(
            ctx=ctx_with_itinerary,
            hotel_reservation=hotel_reservation
        )
        
        assert updated.total_cost == 800
        assert updated.hotel_reservation == hotel_reservation
        assert updated.flight_reservation == flight_reservation

    def test_build_itinerary_tool_info(self):
        """Test that build_itinerary_tool returns info message (tool is for LLM workflows)."""
        result = build_itinerary_tool.invoke({"query": {}})
        assert "info" in result
        assert "database operations" in result["info"].lower()

    def test_get_itinerary_tool_info(self):
        """Test that get_itinerary_tool returns info message."""
        result = get_itinerary_tool.invoke({"query": {"itinerary_id": "test"}})
        assert "info" in result
        assert "database operations" in result["info"].lower()
