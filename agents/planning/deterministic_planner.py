# deterministic_planner.py
# Deterministic planning fallback: Intent parsing + DAG building
from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING
from uuid import uuid4
from datetime import datetime

from agents.core.llm_provider import LLMProvider, extract_token_usage
from agents.planning.schemas import ExecutionPlan, MissingInfo, PlanMetadata, PlanTask
from agents.planning.alias_resolver import AliasResolver
from api.config import PreferenceLoadingMode, PREFERENCE_LOADING_MODE
from utils.logger import get_logger, _format_duration

if TYPE_CHECKING:
    from api.context import TravelContext

logger = get_logger()


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
MANDATORY_FIELDS = {
    "flight": ["origin", "destination", "date"],
    # Hotel and car dates can be defaulted from trip dates; require city only.
    "hotel": ["city"],
    "car": ["city"],
}

DEFAULTS = {
    "passengers": 1,
    "rooms": 1,
    "cabin_class": "economy",
    "car_type": "economy",
    "selection_criteria": "first_available",
}


class DeterministicPlanner:
    """Deterministic planner for intent parsing + DAG building (fallback path)."""
    
    def __init__(
        self,
        alias_map_path: Optional[str] = None,
        planner_version: str = "1.0.0",
    ):
        """
        Initialize deterministic planner.
        
        Args:
            alias_map_path: Path to alias map JSON file (optional)
            planner_version: Planner version string
        """
        self.planner_version = planner_version
        self.alias_resolver = AliasResolver(alias_map_path=alias_map_path)
    
    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    
    def create_plan_from_query(
        self,
        query: str,
        ctx: "TravelContext",
    ) -> ExecutionPlan:
        """
        Create plan from natural language query using intent parsing + deterministic DAG.
        
        This is the fallback path when LLM plan generation fails.
        
        Args:
            query: Natural language query from user
            ctx: TravelContext with session, LLM, traveler_id, preferences
        
        Returns:
            ExecutionPlan with status 'executable' or 'needs_clarification'
        """
        logger.info(
            "DeterministicPlanner: Starting NL query parsing",
            extra={"query_preview": query[:100] if len(query) > 100 else query, "traveler_id": ctx.traveler_id},
        )
        start_time = time.perf_counter()
        
        # Get LLM from context
        llm = ctx.llm
        preference_summary = getattr(ctx, "preference_summary", None) or "No preferences set"
        
        # Parse query to intent
        try:
            if llm is not None:
                if PREFERENCE_LOADING_MODE == PreferenceLoadingMode.TOOL_BINDING:
                    intent = self._parse_query_with_tool_binding(query, llm, preference_summary, ctx)
                else:
                    intent = self._parse_query_with_preferences(query, llm, preference_summary)
            else:
                intent = self._parse_rule_based(query)
        except Exception as e:
            logger.warning(f"DeterministicPlanner: Parsing failed, using rule-based. Error: {e}")
            intent = self._parse_rule_based(query)

        parse_duration_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            f"DeterministicPlanner: Query parsed in {_format_duration(parse_duration_ms)}",
            extra={"intent": intent},
        )

        # Build plan from intent
        plan = self.create_plan_from_intent(intent, traveler_id=ctx.traveler_id)

        total_duration_ms = (time.perf_counter() - start_time) * 1000
        
        # Log final plan summary
        task_summary_lines = []
        for i, t in enumerate(plan.tasks, 1):
            task_summary_lines.append(
                f"  [{i}] {t.id}: {t.agent}.{t.action} | params={t.params} | deps={t.dependencies} | parallel={t.parallelizable}"
            )
        task_summary = "\n".join(task_summary_lines) if task_summary_lines else "  (no tasks)"
        
        logger.info(
            f"DeterministicPlanner: Plan created in {_format_duration(total_duration_ms)} | plan_id={plan.plan_metadata.plan_id} | status={plan.status} | task_count={len(plan.tasks)}\n"
            f"Final Plan Tasks:\n{task_summary}"
        )

        return plan
    
    def create_plan_from_intent(self, intent: Dict[str, Any], traveler_id: str = "") -> ExecutionPlan:
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
                "DeterministicPlanner: Plan created (needs_clarification)",
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
        
        # Log detailed task information
        task_summary_lines = []
        for t in tasks:
            task_summary_lines.append(
                f"  [{t.id}] {t.agent}.{t.action} | params={t.params} | deps={t.dependencies} | parallel={t.parallelizable}"
            )
        task_summary = "\n".join(task_summary_lines) if task_summary_lines else "  (no tasks)"
        
        logger.info(
            f"DeterministicPlanner: Plan created (executable) | plan_id={plan.plan_metadata.plan_id} | task_count={len(tasks)} | traveler_id={traveler_id}\n"
            f"Tasks:\n{task_summary}"
        )
        
        return plan

    # ------------------------------------------------------------------ #
    # Intent Parsing
    # ------------------------------------------------------------------ #
    
    def _parse_query_with_preferences(self, text: str, llm: LLMProvider, preference_summary: str) -> dict:
        """
        Use LLM to parse natural language into structured intent, with preference context.
        
        Args:
            text: User's natural language query
            llm: LLM provider
            preference_summary: Compact preference summary (~50 tokens)
        
        Returns:
            Structured intent dict
        """
        logger.debug(f"DeterministicPlanner: Parsing query with LLM (summary mode)")
        
        prompt = (
            "Parse the following user query about travel booking into a structured intent format.\n\n"
            f'User Query: "{text}"\n\n'
            f"Traveler Preferences: {preference_summary}\n\n"
            "Extract the following information:\n"
            "- needs: List of services needed (flight, hotel, car, itinerary)\n"
            "- from: Origin airport code (3 letters, uppercase)\n"
            "- to: Destination airport code (3 letters, uppercase)\n"
            "- date: Travel date in YYYY-MM-DD format\n\n"
            "Note: Consider the traveler's preferences when interpreting ambiguous requests.\n"
            "Return ONLY a valid JSON object with these fields. Example:\n"
            '{\n'
            '  "needs": ["flight", "hotel", "car", "itinerary"],\n'
            '  "from": "NYC",\n'
            '  "to": "LON",\n'
            '  "date": "2025-08-12"\n'
            '}'
        )
        
        try:
            start_time = time.perf_counter()
            response = llm.invoke_structured(
                prompt,
                response_format={
                    "type": "object",
                    "properties": {
                        "needs": {"type": "array", "items": {"type": "string"}},
                        "from": {"type": "string"},
                        "to": {"type": "string"},
                        "date": {"type": "string"}
                    }
                }
            )
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.info(f"⏱ DeterministicPlanner LLM call: {_format_duration(duration_ms)}")
            
            # Handle response format
            if isinstance(response, dict):
                if "raw_response" in response:
                    try:
                        return json.loads(response["raw_response"])
                    except Exception:
                        logger.warning("DeterministicPlanner: Failed to parse raw_response, using rule-based fallback")
                        return self._parse_rule_based(text)
                else:
                    intent = {
                        "needs": response.get("needs", []),
                        "from": response.get("from", ""),
                        "to": response.get("to", ""),
                        "date": response.get("date", "")
                    }
                    return {k: v for k, v in intent.items() if v or k == "needs"}
            else:
                return self._parse_rule_based(text)
        
        except Exception as e:
            logger.warning(f"DeterministicPlanner: LLM parsing failed: {e}, using rule-based fallback")
            return self._parse_rule_based(text)
    
    def _parse_query_with_tool_binding(
        self, 
        text: str, 
        llm: LLMProvider, 
        preference_summary: str,
        ctx: "TravelContext"
    ) -> dict:
        """
        Use LLM with tool binding to parse query. LLM can call load_full_preferences
        if it needs detailed information (loyalty numbers, dietary restrictions, etc.).
        
        Args:
            text: User's natural language query
            llm: LLM provider
            preference_summary: Compact preference summary (~50 tokens)
            ctx: TravelContext for traveler_id
        
        Returns:
            Structured intent dict
        """
        logger.info("DeterministicPlanner: Using tool binding mode for query parsing")
        
        # Import tool here to avoid circular imports
        from tools.preference_tools import load_full_preferences
        
        # Bind the preference tool to the LLM
        try:
            llm_with_tools = llm.llm.bind_tools([load_full_preferences])
        except Exception as e:
            logger.warning(f"DeterministicPlanner: Failed to bind tools: {e}, using summary-only mode")
            return self._parse_query_with_preferences(text, llm, preference_summary)
        
        # Track LLM call timing
        start_time = time.perf_counter()
        prompt = (
            "Parse the following user query about travel booking into a structured intent format.\n\n"
            f'User Query: "{text}"\n\n'
            f"Traveler ID: {ctx.traveler_id}\n"
            f"Traveler Preferences Summary: {preference_summary}\n\n"
            "If you need detailed preferences (loyalty program numbers, dietary restrictions, "
            "accessibility needs, or past booking patterns), use the load_full_preferences tool.\n\n"
            "Extract the following information:\n"
            "- needs: List of services needed (flight, hotel, car, itinerary)\n"
            "- from: Origin airport code (3 letters, uppercase)\n"
            "- to: Destination airport code (3 letters, uppercase)\n"
            "- date: Travel date in YYYY-MM-DD format\n\n"
            "Return ONLY a valid JSON object with these fields."
        )
        
        try:
            # First LLM call with tools
            response = llm_with_tools.invoke(prompt)
            duration_ms = (time.perf_counter() - start_time) * 1000
            token_info = extract_token_usage(response)
            if token_info:
                logger.info(f"⏱ DeterministicPlanner LLM (tool-binding): {_format_duration(duration_ms)} | tokens: {token_info['input']} in, {token_info['output']} out")
            else:
                logger.info(f"⏱ DeterministicPlanner LLM (tool-binding): {_format_duration(duration_ms)}")
            
            # Check if model called the tool
            if hasattr(response, 'tool_calls') and response.tool_calls:
                logger.info(f"DeterministicPlanner: Model requested {len(response.tool_calls)} tool call(s)")
                
                for tool_call in response.tool_calls:
                    tool_name = tool_call.get('name', tool_call.get('function', {}).get('name', ''))
                    tool_args = tool_call.get('args', tool_call.get('function', {}).get('arguments', {}))
                    
                    if tool_name == 'load_full_preferences':
                        # Execute the tool
                        traveler_id = tool_args.get('traveler_id', ctx.traveler_id)
                        logger.info(f"DeterministicPlanner: Executing load_full_preferences for {traveler_id}")
                        tool_start = time.perf_counter()
                        
                        full_prefs = load_full_preferences.invoke({"traveler_id": traveler_id})
                        tool_duration_ms = (time.perf_counter() - tool_start) * 1000
                        logger.info(f"DeterministicPlanner: Tool completed in {_format_duration(tool_duration_ms)}")
                        
                        # Store full preferences in context
                        ctx.full_preferences = full_prefs
                        
                        # Continue with enriched prompt
                        enriched_prompt = (
                            f"{prompt}\n\n"
                            f"Full Preferences Loaded:\n{json.dumps(full_prefs, indent=2)}"
                        )
                        
                        # Second LLM call with full preferences
                        logger.info("DeterministicPlanner: Making enriched LLM call with full preferences")
                        second_start = time.perf_counter()
                        response = llm.llm.invoke(enriched_prompt)
                        second_duration_ms = (time.perf_counter() - second_start) * 1000
                        logger.info(f"⏱ DeterministicPlanner LLM (enriched): {_format_duration(second_duration_ms)}")
            
            # Parse the response
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Extract JSON from response
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                content = content[json_start:json_end].strip()
            elif "```" in content:
                json_start = content.find("```") + 3
                json_end = content.find("```", json_start)
                content = content[json_start:json_end].strip()
            
            intent = json.loads(content)
            return {
                "needs": intent.get("needs", []),
                "from": intent.get("from", ""),
                "to": intent.get("to", ""),
                "date": intent.get("date", "")
            }
        
        except json.JSONDecodeError as e:
            logger.warning(f"DeterministicPlanner: JSON parsing failed in tool binding mode: {e}, using rule-based fallback")
            return self._parse_rule_based(text)
        except Exception as e:
            logger.warning(f"DeterministicPlanner: Tool binding mode failed: {e}, using summary-only mode")
            return self._parse_query_with_preferences(text, llm, preference_summary)
    
    def _parse_rule_based(self, text: str) -> dict:
        """Simple rule-based NL parser (fallback when LLM unavailable)."""
        logger.debug("DeterministicPlanner: Using rule-based parsing")
        
        text_lower = text.lower()
        intent = {'needs': []}
        
        # Detect needs
        if 'flight' in text_lower or 'fly' in text_lower:
            intent['needs'].append('flight')
        if 'hotel' in text_lower or 'stay' in text_lower:
            intent['needs'].append('hotel')
        if 'car' in text_lower or 'rental' in text_lower:
            intent['needs'].append('car')
        
        # Default to flight if no needs detected
        if not intent['needs']:
            intent['needs'].append('flight')
        
        # Extract origin/destination
        m = re.search(r'from ([a-z]{3}) to ([a-z]{3})', text_lower)
        if m:
            intent['from'] = m.group(1).upper()
            intent['to'] = m.group(2).upper()
        
        # Extract date
        d = re.search(r'(\d{4}-\d{2}-\d{2})', text)
        if d:
            intent['date'] = d.group(1)
        
        logger.debug(f"DeterministicPlanner: Rule-based result: {intent}")
        return intent

    # ------------------------------------------------------------------ #
    # Normalization & validation
    # ------------------------------------------------------------------ #
    
    def _normalize_intent(self, intent: Dict[str, Any]) -> Tuple[Dict[str, Any], List[MissingInfo]]:
        """
        Normalize city/airport names to canonical forms using alias map.
        Returns updated intent and any MissingInfo produced by ambiguity/unknowns.
        """
        updated = dict(intent)
        missing: List[MissingInfo] = []

        # Normalize origin/destination if present
        origin_raw = updated.get("origin") or updated.get("from")
        destination_raw = updated.get("destination") or updated.get("to")

        if origin_raw:
            origin_city, origin_airport, miss = self._resolve_location(origin_raw, field="origin")
            if miss:
                missing.append(miss)
            else:
                updated["origin"] = origin_airport or updated.get("origin", origin_city)
                updated["origin_city"] = origin_city
        if destination_raw:
            dest_city, dest_airport, miss = self._resolve_location(destination_raw, field="destination")
            if miss:
                missing.append(miss)
            else:
                updated["destination"] = dest_airport or updated.get("destination", dest_city)
                updated["destination_city"] = dest_city

        # Propagate destination to hotel/car city if not provided
        if "destination_city" in updated:
            updated.setdefault("city", updated["destination_city"])

        return updated, missing

    def _find_missing_mandatory(self, intent: Dict[str, Any]) -> List[MissingInfo]:
        """Identify missing mandatory fields based on needs."""
        needs = intent.get("needs", [])
        missing: List[MissingInfo] = []

        for need in needs:
            for field in MANDATORY_FIELDS.get(need, []):
                if not intent.get(field):
                    missing.append(
                        MissingInfo(
                            field=field,
                            severity="mandatory",
                            question=self._question_for_field(need, field),
                            blocks_tasks=self._blocked_tasks_for_field(need, field),
                        )
                    )
        return missing

    def _apply_defaults(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Apply optional defaults."""
        enriched = dict(intent)
        for field, default in DEFAULTS.items():
            enriched.setdefault(field, default)
        return enriched

    # ------------------------------------------------------------------ #
    # Task construction
    # ------------------------------------------------------------------ #
    
    def _build_tasks(self, intent: Dict[str, Any]) -> List[PlanTask]:
        needs = intent.get("needs", [])
        tasks: List[PlanTask] = []
        tid = 1

        def next_id() -> str:
            nonlocal tid
            val = f"t{tid}"
            tid += 1
            return val

        # Flight
        if "flight" in needs:
            tasks.append(
                PlanTask(
                    id=next_id(),
                    title="Search flights",
                    agent="FlightBookingAgent",
                    action="search_flights",
                    description="Search flights for specified origin/destination/date",
                    input_schema={
                        "origin": {"type": "string"},
                        "destination": {"type": "string"},
                        "date": {"type": "string", "format": "date"},
                    },
                    params={
                        "origin": intent.get("origin"),
                        "destination": intent.get("destination"),
                        "date": intent.get("date"),
                    },
                    output_schema={"flights": {"type": "array"}},
                    dependencies=[],
                    parallelizable=True,
                )
            )

        # Hotel
        if "hotel" in needs:
            tasks.append(
                PlanTask(
                    id=next_id(),
                    title="Search hotels",
                    agent="HotelBookingAgent",
                    action="search_hotels",
                    description="Search hotels for the destination city and dates",
                    input_schema={
                        "city": {"type": "string"},
                        "check_in_date": {"type": "string", "format": "date"},
                        "check_out_date": {"type": "string", "format": "date"},
                    },
                    params={
                        "city": intent.get("city") or intent.get("destination_city"),
                        "check_in_date": intent.get("check_in_date") or intent.get("date"),
                        "check_out_date": intent.get("check_out_date") or intent.get("return_date"),
                    },
                    output_schema={"hotels": {"type": "array"}},
                    dependencies=[],
                    parallelizable=True,
                )
            )

        # Car
        if "car" in needs:
            tasks.append(
                PlanTask(
                    id=next_id(),
                    title="Search cars",
                    agent="CarRentalAgent",
                    action="search_cars",
                    description="Search rental cars for the destination city and dates",
                    input_schema={
                        "city": {"type": "string"},
                        "pickup_date": {"type": "string", "format": "date"},
                        "return_date": {"type": "string", "format": "date"},
                    },
                    params={
                        "city": intent.get("city") or intent.get("destination_city"),
                        "pickup_date": intent.get("pickup_date") or intent.get("date"),
                        "return_date": intent.get("return_date"),
                    },
                    output_schema={"cars": {"type": "array"}},
                    dependencies=[],
                    parallelizable=True,
                )
            )

        # Itinerary
        itinerary_task_id = None
        if needs:
            depends_on = [t.id for t in tasks]
            tasks.append(
                PlanTask(
                    id=next_id(),
                    title="Build itinerary",
                    agent="ItineraryAgent",
                    action="build_itinerary",
                    description="Compile selected flight/hotel/car into itinerary",
                    input_schema={
                        "flight": {"type": "object"},
                        "hotel": {"type": "object"},
                        "car": {"type": "object"},
                    },
                    params={},
                    output_schema={
                        "itinerary": {"type": "object"},
                        "total_cost": {"type": "number"},
                    },
                    dependencies=depends_on,
                    parallelizable=False,
                )
            )
            itinerary_task_id = tasks[-1].id

        # Payment (optional, depends on itinerary if present)
        if "payment" in needs:
            dependencies = [itinerary_task_id] if itinerary_task_id else [t.id for t in tasks]
            tasks.append(
                PlanTask(
                    id=next_id(),
                    title="Process payment",
                    agent="PaymentAgent",
                    action="process_payment",
                    description="Charge user for the booked itinerary",
                    input_schema={
                        "amount": {"type": "number"},
                        "payment_method": {"type": "string"},
                    },
                    params={},
                    output_schema={"payment_status": {"type": "string"}},
                    dependencies=[d for d in dependencies if d],
                    parallelizable=False,
                )
            )

        return tasks

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    
    def _build_metadata(self, confidence: float) -> PlanMetadata:
        return PlanMetadata(
            plan_id=f"plan_{uuid4().hex[:8]}",
            created_at=datetime.utcnow().isoformat() + "Z",
            planner_version=self.planner_version,
            confidence_score=confidence,
            conversation_turns=1,
        )

    def _question_for_field(self, need: str, field: str) -> str:
        q_map = {
            "origin": "From which airport/city will you depart?",
            "destination": "To which airport/city are you traveling?",
            "date": "On what date do you want to travel?",
            "check_in_date": "What is your hotel check-in date?",
            "check_out_date": "What is your hotel check-out date?",
            "pickup_date": "What is your car pickup date?",
        }
        return q_map.get(field, f"Please provide {field} for {need}.")

    def _blocked_tasks_for_field(self, need: str, field: str) -> List[str]:
        # Map missing fields to the likely blocked task(s). Conservatively block early tasks.
        mapping = {
            ("flight", "origin"): ["t1"],
            ("flight", "destination"): ["t1"],
            ("flight", "date"): ["t1"],
            ("hotel", "city"): ["t2"],
            ("car", "city"): ["t3"],
        }
        return mapping.get((need, field), [])

    def _resolve_location(
        self, raw: str, field: str
    ) -> Tuple[Optional[str], Optional[str], Optional[MissingInfo]]:
        """
        Resolve a city/airport name to canonical city and primary airport using alias map.
        Returns (city, airport_code, MissingInfo | None).
        """
        text = (raw or "").strip()
        if not text:
            return None, None, MissingInfo(
                field=field,
                severity="mandatory",
                question=f"Which {field} city or airport?",
                blocks_tasks=["t1"],
            )

        # Exact IATA code lookup
        if len(text) == 3:
            code = text.upper()
            city_entry = self.alias_resolver.find_city_by_airport(code)
            if city_entry:
                return city_entry["city"], code, None
            return (
                None,
                None,
                MissingInfo(
                    field=field,
                    severity="mandatory",
                    question=f"Please confirm a valid airport code for {field}.",
                    blocks_tasks=["t1"],
                ),
            )

        # Alias match
        city_entry = self.alias_resolver.find_by_alias(text)
        if city_entry:
            return city_entry["city"], city_entry.get("primary_airport"), None

        # Not found
        return (
            None,
            None,
            MissingInfo(
                field=field,
                severity="mandatory",
                question=f"Which city/airport do you mean for {field}?",
                blocks_tasks=["t1"],
            ),
        )
