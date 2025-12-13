# Planner rewritten to deterministic DAG builder with agent+action and schema output.
from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from uuid import uuid4
from datetime import datetime
from pydantic import ValidationError

from agents.core.llm_provider import LLMProvider, extract_token_usage
from agents.planning.schemas import ExecutionPlan, PlanMetadata
from agents.planning.deterministic_planner import DeterministicPlanner, DEFAULTS
from agents.planning.alias_resolver import AliasResolver
from utils.logger import get_logger, _format_duration
from llm import ModelInvocationStrategy, UseCase

if TYPE_CHECKING:
    from api.context import TravelContext

logger = get_logger()


class TravelPlanner:
    """
    Main planner orchestrator.
    
    Preferred path: LLM plan generation (direct ExecutionPlan from LLM)
    Fallback path: Deterministic planning (intent parsing + DAG building)
    """

    def __init__(
        self,
        llm: Optional[LLMProvider] = None,
        strategy: Optional[ModelInvocationStrategy] = None,
        alias_map_path: Optional[str] = None,
        planner_version: str = "1.0.0",
    ):
        """
        Initialize travel planner.
        
        Args:
            llm: Optional LLM provider (Legacy)
            strategy: Model Strategy (Preferred)
            alias_map_path: Path to alias map JSON file
            planner_version: Planner version string
        """
        self.llm = llm
        self.strategy = strategy
        self.planner_version = planner_version
        
        # Create deterministic planner for fallback
        self.deterministic_planner = DeterministicPlanner(
            alias_map_path=alias_map_path,
            planner_version=planner_version
        )
        
        # Create alias resolver for LLM prompt building
        self.alias_resolver = AliasResolver(alias_map_path=alias_map_path)

    # ------------------------------------------------------------------ #
    # LLM plan generation
    # ------------------------------------------------------------------ #
    
    def create_plan_from_query(
        self,
        query: str,
        ctx: "TravelContext",
    ) -> ExecutionPlan:
        """
        Single entry point: NL query → ExecutionPlan.
        
        Preferred path: ask the LLM to emit the full plan JSON (status, missing_info,
        tasks, plan_metadata) following planner schemas. Fallback: deterministic
        intent parsing + static DAG if LLM unavailable or returns invalid JSON.
        
        Args:
            query: Natural language query from user
            ctx: TravelContext with session, LLM, traveler_id, preferences
        
        Returns:
            ExecutionPlan with status 'executable' or 'needs_clarification'
        """
        logger.info(
            "Planner: Starting NL query parsing",
            extra={"query_preview": query[:100] if len(query) > 100 else query, "traveler_id": ctx.traveler_id},
        )
        start_time = time.perf_counter()
        
        # Get LLM from context strategy (preferred), planner strategy, or legacy llm
        llm = None
        if ctx.model_strategy:
            llm = ctx.model_strategy.get_llm_for_use_case(UseCase.PLANNER)
        elif self.strategy:
            llm = self.strategy.get_llm_for_use_case(UseCase.PLANNER)
        
        # Fallback: try to get LLM from planner's strategy if context strategy failed
        if not llm and self.strategy:
            try:
                llm = self.strategy.get_llm_for_use_case(UseCase.PLANNER)
            except Exception:
                llm = None
        preference_summary = getattr(ctx, "preference_summary", None) or "No preferences set"

        plan: Optional[ExecutionPlan] = None

        # Preferred path: ask LLM to produce full plan JSON
        if llm is not None:
            plan = self._plan_with_llm(query, llm, preference_summary, ctx)

        if plan is None:
            # Fallback: delegate to deterministic planner
            logger.info("Planner: Falling back to deterministic planning path")
            plan = self.deterministic_planner.create_plan_from_query(query, ctx)

        total_duration_ms = (time.perf_counter() - start_time) * 1000
        
        # Log final plan summary with all tasks in message (so it appears in logs)
        task_summary_lines = []
        for i, t in enumerate(plan.tasks, 1):
            task_summary_lines.append(
                f"  [{i}] {t.id}: {t.agent}.{t.action} | params={t.params} | deps={t.dependencies} | parallel={t.parallelizable}"
            )
        task_summary = "\n".join(task_summary_lines) if task_summary_lines else "  (no tasks)"
        
        logger.info(
            f"Planner: Plan created in {_format_duration(total_duration_ms)} | plan_id={plan.plan_metadata.plan_id} | status={plan.status} | task_count={len(plan.tasks)}\n"
            f"Final Plan Tasks:\n{task_summary}"
        )

        return plan

    # ------------------------------------------------------------------ #
    # LLM plan generation
    # ------------------------------------------------------------------ #

    def _plan_with_llm(
        self,
        query: str,
        llm: LLMProvider,
        preference_summary: str,
        ctx: "TravelContext",
    ) -> Optional[ExecutionPlan]:
        """Ask LLM to emit full ExecutionPlan JSON per design spec."""
        # Get prompt from strategy (prompts.yaml) - required per design
        # Prompts must be stored in prompts.yaml, not hardcoded
        strategy_to_use = ctx.model_strategy or self.strategy
        
        if not strategy_to_use:
            logger.warning(
                "No model_strategy available. Prompt must come from prompts.yaml. "
                "Falling back to deterministic planner."
            )
            return None
        
        try:
            plan_prompt = strategy_to_use.get_prompt_for_use_case(
                UseCase.PLANNER, 
                query=query, 
                preference_summary=preference_summary
            )
            logger.debug("Retrieved planner prompt from prompts.yaml")
        except Exception as e:
            logger.error(
                f"Failed to load prompt from prompts.yaml: {e}. "
                "Falling back to deterministic planner."
            )
            return None
        response_format = {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["executable", "needs_clarification"]},
                "missing_info": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "field": {"type": "string"},
                            "severity": {"type": "string", "enum": ["mandatory", "optional"]},
                            "question": {"type": "string"},
                            "blocks_tasks": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                },
                "tasks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "title": {"type": "string"},
                            "agent": {"type": "string"},
                            "action": {"type": "string"},
                            "description": {"type": "string"},
                            "input_schema": {"type": "object"},
                            "params": {"type": "object"},
                            "output_schema": {"type": "object"},
                            "dependencies": {"type": "array", "items": {"type": "string"}},
                            "parallelizable": {"type": "boolean"},
                        },
                    },
                },
                "plan_metadata": {
                    "type": "object",
                    "properties": {
                        "plan_id": {"type": "string"},
                        "created_at": {"type": "string"},
                        "planner_version": {"type": "string"},
                        "confidence_score": {"type": "number"},
                        "conversation_turns": {"type": "integer"},
                    },
                },
            },
        }

        try:
            # Phase 1: JSON mode is enabled in LLM provider, so no schema appended to prompt
            raw_plan = llm.invoke_structured(
                plan_prompt, 
                response_format=response_format
            )
        except Exception as e:
            logger.warning(f"Planner: LLM plan invocation failed: {e}")
            return None

        plan_dict = self._coerce_plan_dict(raw_plan)
        if plan_dict is None:
            return None

        try:
            plan = ExecutionPlan.model_validate(plan_dict)
            
            # Phase 1: Post-processing validation (moved from prompt to Python)
            plan = self._post_process_plan(plan, query, ctx)
            
            # Log detailed task information in message (so it appears in logs)
            task_summary_lines = []
            for t in plan.tasks:
                task_summary_lines.append(
                    f"  [{t.id}] {t.agent}.{t.action} | params={t.params} | deps={t.dependencies} | parallel={t.parallelizable}"
                )
            task_summary = "\n".join(task_summary_lines) if task_summary_lines else "  (no tasks)"
            
            logger.info(
                f"Planner: LLM plan validated | plan_id={plan.plan_metadata.plan_id} | status={plan.status} | task_count={len(plan.tasks)} | traveler_id={ctx.traveler_id}\n"
                f"LLM Generated Tasks:\n{task_summary}"
            )
            
            return plan
        except ValidationError as e:
            logger.warning(f"Planner: LLM plan validation failed: {e}")
            return None

    def _coerce_plan_dict(self, data: Any) -> Optional[Dict[str, Any]]:
        """
        Normalize raw LLM response into a dict suitable for ExecutionPlan.
        
        Phase 1: Fix common LLM output issues:
        - Missing status/plan_metadata fields
        - Task IDs as integers instead of strings
        - Missing required fields
        """
        if isinstance(data, dict):
            if "raw_response" in data:
                parsed = self._safe_json_loads(data["raw_response"])
                if parsed is None:
                    return None
                data = parsed
        
        if isinstance(data, str):
            data = self._safe_json_loads(data)
            if data is None:
                return None
        
        if not isinstance(data, dict):
            return None
        
        # Fix common issues in LLM output
        coerced = dict(data)
        
        # Ensure status field exists
        if "status" not in coerced:
            coerced["status"] = "executable" if coerced.get("tasks") else "needs_clarification"
        
        # Fix task IDs: convert integers to strings
        if "tasks" in coerced and isinstance(coerced["tasks"], list):
            for task in coerced["tasks"]:
                if isinstance(task, dict) and "id" in task:
                    if isinstance(task["id"], int):
                        task["id"] = f"t{task['id']}"
                    elif not isinstance(task["id"], str):
                        task["id"] = str(task["id"])
        
        # Ensure plan_metadata exists
        if "plan_metadata" not in coerced:
            from uuid import uuid4
            from datetime import datetime
            coerced["plan_metadata"] = {
                "plan_id": f"plan_{uuid4().hex[:8]}",
                "created_at": datetime.utcnow().isoformat() + "Z",
                "planner_version": self.planner_version,
                "confidence_score": 0.9,
                "conversation_turns": 1,
            }
        
        # Ensure missing_info exists
        if "missing_info" not in coerced:
            coerced["missing_info"] = []
        
        return coerced

    def _safe_json_loads(self, text: str) -> Optional[Dict[str, Any]]:
        if not text:
            return None
        try:
            if "```json" in text:
                start = text.find("```json") + 7
                end = text.find("```", start)
                text = text[start:end].strip()
            elif "```" in text:
                start = text.find("```") + 3
                end = text.find("```", start)
                text = text[start:end].strip()
            return json.loads(text)
        except Exception as e:
            logger.warning(f"Planner: Failed to parse JSON from LLM response: {e}")
            return None

    def _post_process_plan(
        self, 
        plan: ExecutionPlan, 
        query: str, 
        ctx: "TravelContext"
    ) -> ExecutionPlan:
        """
        Phase 1: Post-processing validation (moved from prompt to Python).
        
        Applies deterministic rules that were previously in the prompt:
        - Normalize city/airport names using alias map
        - Validate mandatory fields
        - Enforce DAG rules (build_itinerary depends on all search tasks)
        - Apply defaults to optional fields
        """
        from agents.planning.schemas import MissingInfo
        
        # Normalize locations in task params using alias resolver
        normalized_tasks = []
        for task in plan.tasks:
            normalized_params = dict(task.params)
            
            # Normalize origin/destination for flight tasks
            if task.agent == "FlightBookingAgent" and task.action == "search_flights":
                origin = normalized_params.get("origin") or normalized_params.get("from")
                destination = normalized_params.get("destination") or normalized_params.get("to")
                
                if origin:
                    city, airport, _ = self.deterministic_planner._resolve_location(origin, "origin")
                    if airport:
                        normalized_params["origin"] = airport
                        normalized_params["origin_city"] = city
                
                if destination:
                    city, airport, _ = self.deterministic_planner._resolve_location(destination, "destination")
                    if airport:
                        normalized_params["destination"] = airport
                        normalized_params["destination_city"] = city
            
            # Normalize city for hotel/car tasks
            if task.agent in ["HotelBookingAgent", "CarRentalAgent"]:
                city = normalized_params.get("city")
                if city:
                    city_name, _, _ = self.deterministic_planner._resolve_location(city, "city")
                    if city_name:
                        normalized_params["city"] = city_name
            
            # Apply defaults to optional fields
            if task.agent == "FlightBookingAgent":
                normalized_params.setdefault("passengers", DEFAULTS.get("passengers", 1))
                normalized_params.setdefault("cabin_class", DEFAULTS.get("cabin_class", "economy"))
                normalized_params.setdefault("selection_criteria", DEFAULTS.get("selection_criteria", "first_available"))
            elif task.agent == "HotelBookingAgent":
                normalized_params.setdefault("rooms", DEFAULTS.get("rooms", 1))
            elif task.agent == "CarRentalAgent":
                normalized_params.setdefault("car_type", DEFAULTS.get("car_type", "economy"))
            
            # Create updated task with normalized params
            normalized_task = task.model_copy(update={"params": normalized_params})
            normalized_tasks.append(normalized_task)
        
        # Enforce DAG rules: if any search tasks exist, ensure build_itinerary depends on all of them
        search_task_ids = [t.id for t in normalized_tasks if t.action in ["search_flights", "search_hotels", "search_cars"]]
        itinerary_tasks = [t for t in normalized_tasks if t.action == "build_itinerary"]
        
        if search_task_ids and itinerary_tasks:
            # Update itinerary task dependencies to include all search tasks
            for itinerary_task in itinerary_tasks:
                current_deps = set(itinerary_task.dependencies)
                current_deps.update(search_task_ids)
                if set(itinerary_task.dependencies) != current_deps:
                    idx = normalized_tasks.index(itinerary_task)
                    normalized_tasks[idx] = itinerary_task.model_copy(update={"dependencies": list(current_deps)})
        
        # Validate mandatory fields and update status if needed
        missing_info = []
        for task in normalized_tasks:
            if task.agent == "FlightBookingAgent" and task.action == "search_flights":
                if not task.params.get("origin") and not task.params.get("from"):
                    missing_info.append(MissingInfo(
                        field="origin",
                        severity="mandatory",
                        question="From which airport/city will you depart?",
                        blocks_tasks=[task.id]
                    ))
                if not task.params.get("destination") and not task.params.get("to"):
                    missing_info.append(MissingInfo(
                        field="destination",
                        severity="mandatory",
                        question="To which airport/city are you traveling?",
                        blocks_tasks=[task.id]
                    ))
                # Check for date field (accepts 'date', 'departure_date', or 'departure' for flights)
                has_date = (
                    task.params.get("date") or 
                    task.params.get("departure_date") or 
                    task.params.get("departure")
                )
                if not has_date:
                    missing_info.append(MissingInfo(
                        field="date",
                        severity="mandatory",
                        question="On what date do you want to travel?",
                        blocks_tasks=[task.id]
                    ))
            elif task.agent == "HotelBookingAgent" and task.action == "search_hotels":
                if not task.params.get("city"):
                    missing_info.append(MissingInfo(
                        field="city",
                        severity="mandatory",
                        question="Which city do you need a hotel in?",
                        blocks_tasks=[task.id]
                    ))
            elif task.agent == "CarRentalAgent" and task.action == "search_cars":
                if not task.params.get("city"):
                    missing_info.append(MissingInfo(
                        field="city",
                        severity="mandatory",
                        question="Which city do you need a car rental in?",
                        blocks_tasks=[task.id]
                    ))
        
        # Update plan with normalized tasks and missing info
        if missing_info:
            plan = plan.model_copy(update={
                "status": "needs_clarification",
                "missing_info": missing_info,
                "tasks": normalized_tasks
            })
        else:
            plan = plan.model_copy(update={"tasks": normalized_tasks})
        
        return plan



# Backward-compatible helper
def plan_trip(intent: Dict[str, Any], llm: Optional[LLMProvider] = None) -> ExecutionPlan:
    """Convenience wrapper to produce an ExecutionPlan."""
    planner = TravelPlanner(llm=llm)
    return planner.deterministic_planner.create_plan_from_intent(intent)
