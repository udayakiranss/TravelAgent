import json
import pytest

from agents.llm_provider import LLMProvider
from agents.planner import TravelPlanner
from agents.planner_schemas import ExecutionPlan
from api.context import TravelContext


class TestPlanner:
    def test_needs_clarification_when_missing_mandatory(self):
        planner = TravelPlanner(llm=None)
        intent = {
            "needs": ["flight", "hotel"],
            "origin": None,
            "destination": "LON",
            "date": None,
        }

        plan = planner.create_plan(intent)
        assert isinstance(plan, ExecutionPlan)
        assert plan.status == "needs_clarification"
        assert len(plan.missing_info) >= 1
        assert plan.tasks == []

    def test_executable_plan_with_defaults(self):
        planner = TravelPlanner(llm=None)
        intent = {
            "needs": ["flight", "hotel", "car"],
            "origin": "NYC",
            "destination": "LON",
            "date": "2025-08-12",
            "return_date": "2025-08-16",
        }

        plan = planner.create_plan(intent)
        assert plan.status == "executable"
        agents = [t.agent for t in plan.tasks]
        assert "FlightBookingAgent" in agents
        assert "HotelBookingAgent" in agents
        assert "CarRentalAgent" in agents
        assert "ItineraryAgent" in agents
        # Parallelizable hints should be present
        assert any(t.parallelizable for t in plan.tasks)

    def test_city_alias_normalization(self):
        planner = TravelPlanner(llm=None)
        intent = {
            "needs": ["flight"],
            "origin": "New York",
            "destination": "Paris",
            "date": "2025-09-01",
        }

        plan = planner.create_plan(intent)
        assert plan.status == "executable"
        flight_task = next(t for t in plan.tasks if t.agent == "FlightBookingAgent")
        assert flight_task.params["origin"] in {"JFK", "LGA", "EWR", "NYC", "JFK"} or flight_task.params["origin"] == "JFK"
        assert flight_task.params["destination"] in {"CDG", "ORY", "PAR", "CDG"} or flight_task.params["destination"] == "CDG"

    def test_llm_generated_plan_executable(self):
        class FakeLLM(LLMProvider):
            def __init__(self, payload):
                self.payload = payload

            def invoke(self, prompt: str, **kwargs):
                return json.dumps(self.payload)

            def invoke_structured(self, prompt: str, response_format, **kwargs):
                return self.payload

        llm_payload = {
            "status": "executable",
            "missing_info": [],
            "tasks": [
                {
                    "id": "t1",
                    "title": "Search outbound flights",
                    "agent": "FlightBookingAgent",
                    "action": "search_flights",
                    "description": "Search flights NYC → LON on 2025-08-12",
                    "input_schema": {"origin": {"type": "string"}, "destination": {"type": "string"}, "date": {"type": "string"}},
                    "params": {"origin": "NYC", "destination": "LON", "date": "2025-08-12"},
                    "output_schema": {"flights": {"type": "array"}},
                    "dependencies": [],
                    "parallelizable": True,
                },
                {
                    "id": "t2",
                    "title": "Build itinerary",
                    "agent": "ItineraryAgent",
                    "action": "build_itinerary",
                    "description": "Compile selections",
                    "input_schema": {"flight": {"type": "object"}},
                    "params": {},
                    "output_schema": {"itinerary": {"type": "object"}},
                    "dependencies": ["t1"],
                    "parallelizable": False,
                },
            ],
            "plan_metadata": {
                "plan_id": "plan_test",
                "created_at": "2025-12-10T10:50:00Z",
                "planner_version": "1.0.0",
                "confidence_score": 0.9,
                "conversation_turns": 1,
            },
        }

        llm = FakeLLM(llm_payload)
        planner = TravelPlanner(llm=llm)
        ctx = TravelContext(session=None, llm=llm, traveler_id="trav_1")

        plan = planner.create_plan_from_query("Book a flight NYC to LON on 2025-08-12", ctx)
        assert plan.status == "executable"
        assert len(plan.tasks) == 2
        assert plan.tasks[0].agent == "FlightBookingAgent"
        assert plan.tasks[-1].dependencies == ["t1"]

    def test_llm_plan_failure_falls_back(self):
        class FailingLLM(LLMProvider):
            def invoke(self, prompt: str, **kwargs):
                return "not-json"

            def invoke_structured(self, prompt: str, response_format, **kwargs):
                return {"raw_response": "not-json"}

        llm = FailingLLM()
        planner = TravelPlanner(llm=llm)
        ctx = TravelContext(session=None, llm=llm, traveler_id="trav_2")

        plan = planner.create_plan_from_query("Book flight from NYC to LON on 2025-08-12", ctx)
        assert plan.status == "executable"
        agents = [t.agent for t in plan.tasks]
        assert "FlightBookingAgent" in agents
