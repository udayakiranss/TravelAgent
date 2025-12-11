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
        alias_map_path: Optional[str] = None,
        planner_version: str = "1.0.0",
    ):
        """
        Initialize travel planner.
        
        Args:
            llm: Optional LLM provider
            alias_map_path: Path to alias map JSON file
            planner_version: Planner version string
        """
        self.llm = llm
        self.planner_version = planner_version
        
        # Create deterministic planner for fallback
        self.deterministic_planner = DeterministicPlanner(
            alias_map_path=alias_map_path,
            planner_version=planner_version
        )
        
        # Create alias resolver for LLM prompt building
        self.alias_resolver = AliasResolver(alias_map_path=alias_map_path)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    
    def create_plan(self, intent: Dict[str, Any], traveler_id: str = "") -> ExecutionPlan:
        """
        Build a deterministic ExecutionPlan from structured intent.
        
        .. deprecated::
            This method is kept for backward compatibility.
            For new code, use DeterministicPlanner.create_plan_from_intent() directly.
        """
        return self.deterministic_planner.create_plan_from_intent(intent, traveler_id=traveler_id)
        """
        Build a deterministic ExecutionPlan from structured intent.

        - Normalize city/airport fields using the alias map (with guardrails).
        - Detect missing mandatory fields (status=needs_clarification).
        - Apply defaults to optional fields.
        - Build tasks with agent+action, params, schemas, dependencies, parallelizable.
        """
        normalized_intent, missing_from_norm = self._normalize_intent(intent)
        missing_fields = missing_from_norm + self._find_missing_mandatory(normalized_intent)

        if missing_fields:
            plan = ExecutionPlan(
                status="needs_clarification",
                missing_info=missing_fields,
                tasks=[],
                plan_metadata=self._build_metadata(confidence=0.4),
            )
            logger.info(
                "Planner plan created (needs_clarification)",
                extra={
                    "plan_id": plan.plan_metadata.plan_id,
                    "missing_fields": [mi.field for mi in missing_fields],
                    "traveler_id": traveler_id,
                },
            )
            return plan

        enriched_intent = self._apply_defaults(normalized_intent)
        tasks = self._build_tasks(enriched_intent)

        plan = ExecutionPlan(
            status="executable",
            missing_info=[],
            tasks=tasks,
            plan_metadata=self._build_metadata(confidence=0.94),
        )
        
        # Log detailed task information in message (so it appears in logs)
        task_summary_lines = []
        for t in tasks:
            task_summary_lines.append(
                f"  [{t.id}] {t.agent}.{t.action} | params={t.params} | deps={t.dependencies} | parallel={t.parallelizable}"
            )
        task_summary = "\n".join(task_summary_lines) if task_summary_lines else "  (no tasks)"
        
        logger.info(
            f"Planner plan created (executable) | plan_id={plan.plan_metadata.plan_id} | task_count={len(tasks)} | traveler_id={traveler_id}\n"
            f"Tasks:\n{task_summary}"
        )
        
        return plan

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
        
        # Get LLM from context or planner instance
        llm = ctx.llm or self.llm
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
        plan_prompt = self._build_plan_prompt(query, preference_summary)
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
            raw_plan = llm.invoke_structured(plan_prompt, response_format=response_format)
        except Exception as e:
            logger.warning(f"Planner: LLM plan invocation failed: {e}")
            return None

        plan_dict = self._coerce_plan_dict(raw_plan)
        if plan_dict is None:
            return None

        try:
            plan = ExecutionPlan.model_validate(plan_dict)
            
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
        """Normalize raw LLM response into a dict suitable for ExecutionPlan."""
        if isinstance(data, dict):
            if "raw_response" in data:
                return self._safe_json_loads(data["raw_response"])
            return data
        if isinstance(data, str):
            return self._safe_json_loads(data)
        return None

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

    def _build_plan_prompt(self, query: str, preference_summary: str) -> str:
        """Construct the LLM prompt to emit ExecutionPlan JSON per design docs."""
        alias_for_prompt: List[Dict[str, Any]] = []
        alias_map = self.alias_resolver.get_alias_map()
        for entry in alias_map[:5]:
            cleaned = {k: v for k, v in entry.items() if k != "_alias_set"}
            alias_for_prompt.append(cleaned)
        alias_hint = json.dumps(alias_for_prompt, indent=2)
        defaults_hint = json.dumps(DEFAULTS, indent=2)
        return (
            "You are the Planner. You never execute tasks or call tools. "
            "You only return a strict JSON plan or a clarification request.\n\n"
            f"User Query: {query}\n"
            f"Traveler Preferences Summary: {preference_summary}\n\n"
            "Objectives (in order):\n"
            "1) Parse the user goal into intent.\n"
            "2) Normalize city/airport inputs using the alias map (Tier A hints below). "
            "Never invent airports; prefer primary airports; if ambiguous or unknown, ask for clarification.\n"
            "3) Detect missing mandatory fields; apply defaults only to optional fields.\n"
            "4) Build a deterministic task DAG with explicit agent+action per task.\n"
            "5) Return valid JSON only (no prose).\n\n"
            "Mandatory vs Optional:\n"
            "- Mandatory flight: origin (IATA), destination (IATA), date.\n"
            "- Mandatory hotel: city.\n"
            "- Mandatory car: city.\n"
            "- Optional defaults: passengers=1, rooms=1, cabin_class=economy, car_type=economy, selection_criteria=first_available.\n\n"
            "Agents and actions:\n"
            "- Agents: FlightBookingAgent, HotelBookingAgent, CarRentalAgent, ItineraryAgent, PaymentAgent.\n"
            "- Actions: search_flights, search_hotels, search_cars, build_itinerary, process_payment.\n\n"
            "CRITICAL: Task DAG Rules:\n"
            "- If the plan includes ANY search tasks (search_flights, search_hotels, search_cars), you MUST also include a build_itinerary task.\n"
            "- The build_itinerary task must depend on ALL search tasks (dependencies should list all search task IDs).\n"
            "- The build_itinerary task uses ItineraryAgent with action 'build_itinerary'.\n"
            "- Example: If you have task_1 (search_flights) and task_2 (search_hotels), you must add task_3 (build_itinerary) with dependencies=['task_1', 'task_2'].\n\n"
            "Output JSON keys (required): status, missing_info, tasks, plan_metadata.\n"
            "Each task requires: id, title, agent, action, description, input_schema, params, output_schema, dependencies, parallelizable.\n"
            'status is "executable" or "needs_clarification". If any mandatory info is missing or ambiguous, set status=needs_clarification and populate missing_info (tasks may be empty).\n'
            "Do not guess mandatory values—ask via missing_info.\n"
            "Do not include execution policies (timeouts/retries) or costs.\n\n"
            f"Tier A alias hints (use as guidance, do not invent beyond map):\n{alias_hint}\n\n"
            f"Optional default values (apply when not provided):\n{defaults_hint}\n\n"
            "Return ONLY the JSON object matching the schema; no markdown code fences unless necessary for JSON correctness."
        )


# Backward-compatible helper
def plan_trip(intent: Dict[str, Any], llm: Optional[LLMProvider] = None) -> ExecutionPlan:
    """Convenience wrapper to produce an ExecutionPlan."""
    planner = TravelPlanner(llm=llm)
    return planner.deterministic_planner.create_plan_from_intent(intent)
