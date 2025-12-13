import pytest
from unittest.mock import MagicMock, Mock
from agents.orchestration import Orchestrator
from agents.planning import ExecutionPlan, PlanMetadata, PlanTask
from api.context import TravelContext
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool
from datetime import datetime
from llm import ModelInvocationStrategy

class TestOrchestrator:
    
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
    def orchestrator(self, mock_llm):
        mock_strategy = Mock(spec=ModelInvocationStrategy)
        mock_strategy.get_llm_for_use_case.return_value = mock_llm
        return Orchestrator(strategy=mock_strategy, memory=None)

    def test_initialization(self, orchestrator):
        assert len(orchestrator.agents) == 5
        assert "FlightBookingAgent" in orchestrator.agents

    def test_enrich_params(self, orchestrator):
        # Test context enrichment
        context = {
            "FlightBookingAgent": {"total_price": 500},
            "HotelBookingAgent": {"total_price": 300}
        }
        
        # Test itinerary enrichment
        task = {"task": "build_itinerary"}
        params = {}
        enriched = orchestrator._enrich_params(params, context, task)
        # Updated to use new naming convention: flight_reservation instead of flight_booking
        assert "flight_reservation" in enriched
        assert "hotel_reservation" in enriched
        
        # Test payment enrichment
        context["ItineraryAgent"] = {"total_cost": 800}
        task = {"task": "process_payment"}
        params = {}
        enriched = orchestrator._enrich_params(params, context, task)
        assert enriched["amount"] == 800

    def test_execute_plan(self, orchestrator, mock_llm, session):
        # Test that orchestrator correctly executes a plan
        # Create a plan directly
        plan = ExecutionPlan(
            status="executable",
            missing_info=[],
            tasks=[
                PlanTask(
                    id="t1",
                    title="Search flights",
                    agent="FlightBookingAgent",
                    action="search_flights",
                    params={"from": "NYC", "to": "LON", "date": "2025-08-12"},
                    dependencies=[],
                    parallelizable=False,
                )
            ],
            plan_metadata=PlanMetadata(
                plan_id="test_plan",
                created_at=datetime.now().isoformat() + "Z",
                planner_version="1.0.0",
                confidence_score=0.9,
                conversation_turns=1,
            )
        )
        
        # Create context
        ctx = TravelContext(
            session=session,
            model_strategy=orchestrator.strategy,
            traveler_id="test_traveler"
        )
        
        # Execute plan
        result = orchestrator.execute_plan(plan, ctx)
        
        # execute_plan() returns a dict with options and reservations
        assert "flight_options" in result or "flight_reservation" in result

