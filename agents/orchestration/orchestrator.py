# orchestrator.py
# Orchestrator that coordinates agents to handle user intents
from typing import Dict, Any, Optional, List, TYPE_CHECKING
import json
import time

from agents.planning.planner import TravelPlanner
from agents.core.llm_provider import LLMProvider, create_llm_provider, extract_token_usage
from agents.domain.flight_booking_agent import FlightBookingAgent
from agents.domain.hotel_booking_agent import HotelBookingAgent
from agents.domain.car_rental_agent import CarRentalAgent
from agents.domain.itinerary_agent import ItineraryAgent
from agents.domain.payment_agent import PaymentAgent
from agents.orchestration.response_formatter import ResponseFormatter
from api.config import SelectionCriteria, PreferenceLoadingMode, PREFERENCE_LOADING_MODE
from database.repository import LLMUnavailableError
from tools.preference_tools import load_full_preferences
from utils.logger import get_logger, log_critical_entry_exit, log_method_entry_exit, _format_duration

if TYPE_CHECKING:
    from api.context import TravelContext
    from database.models import Itinerary
    from api.schemas import PlanResponse, ModifyResponse

logger = get_logger()


class Orchestrator:
    """Orchestrator that coordinates multiple agents to fulfill user intents"""
    
    def __init__(self, llm: Optional[LLMProvider] = None, memory=None, 
                 model_name: str = "gpt-4o", model_provider: str = "openai"):
        """
        Initialize orchestrator
        
        Args:
            llm: Optional LLM provider (if None, will create one)
            memory: Optional memory for conversation history
            model_name: Model name for LLM (if creating new provider)
            model_provider: Model provider (if creating new provider)
        """
        # Initialize or use provided LLM
        if llm is None:
            try:
                self.llm = create_llm_provider(
                    model_name=model_name,
                    model_provider=model_provider,
                    temperature=0
                )
            except Exception as e:
                logger.warning(f"Could not initialize LLM: {e}. Continuing without LLM.")
                self.llm = None
        else:
            self.llm = llm
        
        self.memory = memory
        
        # Initialize agents
        self.agents = {
            'FlightBookingAgent': FlightBookingAgent(llm=self.llm),
            'HotelBookingAgent': HotelBookingAgent(llm=self.llm),
            'CarRentalAgent': CarRentalAgent(llm=self.llm),
            'ItineraryAgent': ItineraryAgent(llm=self.llm),
            'PaymentAgent': PaymentAgent(llm=self.llm),
        }
        self.planner = TravelPlanner(llm=self.llm)
        logger.info(f"Orchestrator initialized with {len(self.agents)} agents")
    
    # =========================================================================
    # User Preferences Support
    # =========================================================================
    
    def _execute_preference_tool_call(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the load_full_preferences tool call.
        
        Args:
            tool_call: Tool call dict with name and args
        
        Returns:
            Full preferences dictionary
        """
        traveler_id = tool_call.get("args", {}).get("traveler_id", "")
        logger.info(f"Executing preference tool call for traveler_id={traveler_id}")
        
        # Call the tool function directly
        return load_full_preferences.invoke({"traveler_id": traveler_id})
    
    # =========================================================================
    # Context-Aware High-Level Methods (per DD-1, DD-2)
    # =========================================================================
    
    def execute_plan(
        self,
        plan: "ExecutionPlan",
        ctx: "TravelContext",
        include_summary: bool = True,
    ) -> Dict[str, Any]:
        """
        Execute an ExecutionPlan by running agents and creating itinerary.
        
        This is the pure execution method - it assumes planning is already done.
        The plan should have status='executable' before calling this method.
        
        Args:
            plan: ExecutionPlan from TravelPlanner.create_plan_from_query()
            ctx: TravelContext with session, traveler_id, criteria
            include_summary: Whether to generate LLM summary
        
        Returns:
            Dict with itinerary_id, options, reservations, and summary
        """
        from agents.planning.schemas import ExecutionPlan
        
        logger.info(
            f"Orchestrator: Executing plan",
            extra={
                "plan_id": plan.plan_metadata.plan_id,
                "task_count": len(plan.tasks),
                "criteria": ctx.criteria.value,
            },
        )
        start_time = time.perf_counter()
        
        # Execution State
        context = {}  # Map agent_name -> result (for dependency injection compatibility)
        results_map = {} # Map task_id -> result
        
        # Collectors for final response
        flight_options = []
        hotel_options = []
        car_options = []
        flight_reservation = None
        hotel_reservation = None
        car_reservation = None
        itinerary = None
        
        # Execute tasks sequentially
        for task in plan.tasks:
            agent_name = task.agent
            action = task.action
            
            logger.debug(f"Orchestrator: Processing task {task.id}: {agent_name}.{action}")
            
            # 1. Enrich parameters using context from previous tasks
            # We construct a temporary 'current_task' dict to mimic legacy run_intent structure for compatibility
            current_task_info = {"task": action} 
            params = self._enrich_params(task.params, context, current_task_info)
            
            # 2. Get Agent
            if agent_name not in self.agents:
                logger.error(f"Unknown agent in plan: {agent_name}")
                continue # Or raise error? Continue ensures partial failure handling.
            
            agent = self.agents[agent_name]
            
            # 3. Execute with Context
            try:
                # Pass ctx to allow agent to handle selection logic ("Smart Agent")
                result = agent.execute(action, params, ctx)
                
                # 4. Store Result
                results_map[task.id] = result
                context[agent_name] = result # Update context for subsequent tasks
                
                # 5. Extract specific data for API response
                if agent_name == "FlightBookingAgent":
                    if isinstance(result, dict):
                        flight_options = result.get("options", []) or []
                        flight_reservation = result.get("reservation")
                        # If result was just a list (legacy), treat as options
                        if not flight_options and isinstance(result, list):
                            flight_options = result
                
                elif agent_name == "HotelBookingAgent":
                    if isinstance(result, dict):
                        hotel_options = result.get("options", []) or []
                        hotel_reservation = result.get("reservation")
                        if not hotel_options and isinstance(result, list):
                            hotel_options = result
                            
                elif agent_name == "CarRentalAgent":
                    if isinstance(result, dict):
                        car_options = result.get("options", []) or []
                        car_reservation = result.get("reservation")
                        if not car_options and isinstance(result, list):
                            car_options = result
                
                elif agent_name == "ItineraryAgent" and action == "build_itinerary":
                    # ItineraryAgent.build returns the Itinerary object directly
                    itinerary = result
                    if hasattr(itinerary, 'id'):
                        ctx.itinerary_id = itinerary.id
                        ctx.itinerary = itinerary
            
            except Exception as e:
                logger.error(f"Task execution failed: {agent_name}.{action}: {e}")
                # We continue execution if possible, but plan might be compromised.
        
        execution_duration_ms = (time.perf_counter() - start_time) * 1000
        
        # Safety fallback: If searches completed but no itinerary was built, try to build one automatically
        has_searches = (flight_reservation or flight_options) or (hotel_reservation or hotel_options) or (car_reservation or car_options)
        if not itinerary and has_searches:
            logger.warning("Plan execution finished without building itinerary, but searches completed. Attempting automatic itinerary build...")
            try:
                itinerary_agent = self.agents.get("ItineraryAgent")
                if itinerary_agent:
                    # Build itinerary from available reservations (prefer reservations, fallback to first option)
                    build_params = {}
                    if flight_reservation:
                        build_params["flight_reservation"] = flight_reservation
                    elif flight_options:
                        # Use first option if no reservation was selected
                        build_params["flight_reservation"] = flight_options[0]
                        logger.debug("Using first flight option for auto-build")
                    
                    if hotel_reservation:
                        build_params["hotel_reservation"] = hotel_reservation
                    elif hotel_options:
                        build_params["hotel_reservation"] = hotel_options[0]
                        logger.debug("Using first hotel option for auto-build")
                    
                    if car_reservation:
                        build_params["car_reservation"] = car_reservation
                    elif car_options:
                        build_params["car_reservation"] = car_options[0]
                        logger.debug("Using first car option for auto-build")
                    
                    if build_params:
                        itinerary = itinerary_agent.execute("build_itinerary", build_params, ctx)
                        if itinerary and hasattr(itinerary, 'id'):
                            ctx.itinerary_id = itinerary.id
                            ctx.itinerary = itinerary
                            logger.info(f"Auto-built itinerary: {itinerary.id} from {len(build_params)} reservation(s)")
            except Exception as e:
                logger.error(f"Failed to auto-build itinerary: {e}")
        
        # Handle case where itinerary still wasn't built (e.g. error or empty plan)
        if not itinerary:
             logger.warning("Plan execution finished without building itinerary")
             # Return partial results with all expected keys (None for missing values)
             preference_summary = ctx.preference_summary or ""
             return {
                "itinerary_id": None,
                "flight_options": flight_options,
                "hotel_options": hotel_options,
                "car_options": car_options,
                "flight_reservation": flight_reservation,
                "hotel_reservation": hotel_reservation,
                "car_reservation": car_reservation,
                "selection_criteria_used": ctx.criteria.value,
                "preference_summary": preference_summary,
                "summary": f"Found {len(flight_options)} flights, {len(hotel_options)} hotels, {len(car_options)} cars. Plan execution failed to produce itinerary.",
                "query": ctx.original_query or "",
             }

        logger.info(
            f"Orchestrator: Plan executed in {_format_duration(execution_duration_ms)}",
            extra={
                "itinerary_id": itinerary.id,
                "total_cost": itinerary.total_cost,
                "flights": len(flight_options),
                "hotels": len(hotel_options),
                "cars": len(car_options),
            },
        )
        
        # Generate summary
        summary = f"Found {len(flight_options)} flights, {len(hotel_options)} hotels, {len(car_options)} cars"
        preference_summary = ctx.preference_summary or ""
        
        llm = ctx.llm or self.llm
        if include_summary and llm:
            try:
                results = {
                    "flight": flight_reservation,
                    "hotel": hotel_reservation,
                    "car": car_reservation,
                    "total_cost": itinerary.total_cost,
                    "traveler_preferences": preference_summary,
                }
                
                formatter = ResponseFormatter(llm=llm)
                # We need intent for formatter. Plan doesn't strictly have 'intent' dict anymore.
                # But we have original query.
                # Or we can reconstruct intent from tasks?
                # The generic formatter expects 'intent' dict with 'needs', 'from', 'to'.
                # We can mock it or extract from context.
                # Let's use metadata from valid tasks or ctx.original_query.
                # For now, pass empty intent or reconstruct basic structure.
                intent_stub = {
                    "query": ctx.original_query,
                    "needs": [t.agent.replace("BookingAgent", "").replace("RentalAgent", "").lower() for t in plan.tasks] 
                }
                summary = formatter.format_results(results, intent_stub)
            except Exception as e:
                logger.warning(f"Orchestrator: Failed to generate LLM summary: {e}")
        
        return {
            "itinerary_id": itinerary.id,
            "flight_options": flight_options,
            "hotel_options": hotel_options,
            "car_options": car_options,
            "flight_reservation": flight_reservation,
            "hotel_reservation": hotel_reservation,
            "car_reservation": car_reservation,
            "selection_criteria_used": ctx.criteria.value,
            "preference_summary": preference_summary,
            "summary": summary,
            "query": ctx.original_query or "",
        }
    def modify_itinerary(self, instruction: str, ctx: "TravelContext") -> Dict[str, Any]:
        """
        Modify an existing itinerary via natural language instruction.
        """
        logger.info(f"Modifying itinerary {ctx.itinerary_id}: {instruction[:50]}...")
        
        if not ctx.itinerary_id or not ctx.itinerary:
            raise ValueError("Context must have itinerary_id and itinerary loaded")
        
        if ctx.itinerary.status != "draft":
            return {
                "success": False,
                "updated_itinerary": None,
                "message": f"Cannot modify itinerary in '{ctx.itinerary.status}' status",
                "partial": False,
            }
        
        llm = ctx.llm or self.llm
        if llm is None:
            raise LLMUnavailableError("LLM is required for natural language modification")
        
        # Build modification prompt with context
        current_state = {
            "flight": ctx.itinerary.flight_reservation,
            "hotel": ctx.itinerary.hotel_reservation,
            "car": ctx.itinerary.car_reservation,
            "total_cost": ctx.itinerary.total_cost,
        }
        
        history_text = ctx.get_chat_history_text(limit=10)
        
        modification_prompt = f"""You are a travel agent assistant. Based on the current itinerary state and user instruction, determine what needs to be modified.

Current Itinerary State:
{json.dumps(current_state, indent=2)}

Previous Conversation:
{history_text}

User Instruction: {instruction}

Analyze the instruction and respond with a JSON object containing:
- "component": which component to modify ("flight", "hotel", or "car")
- "action": what action to take ("search_new", "remove", "update")
- "parameters": any search parameters extracted from the instruction

Respond with ONLY the JSON object."""

        # Get LLM response for modification analysis
        try:
            llm_response = llm.invoke(modification_prompt)
            
            # TODO: Parse response and execute appropriate agent actions
            # For now, return partial implementation message
            
            return {
                "success": True,
                "updated_itinerary": ctx.itinerary,
                "message": f"Modification request received: {instruction}. Full implementation pending.",
                "partial": False,
            }
        
        except Exception as e:
            logger.error(f"Modification failed: {e}")
            return {
                "success": False,
                "updated_itinerary": None,
                "message": f"Error during modification: {str(e)}",
                "partial": False,
            }
    
    def get_itinerary(self, ctx: "TravelContext") -> Optional["Itinerary"]:
        """Get itinerary from context."""
        return self.agents['ItineraryAgent'].get(ctx)
    
    def confirm_itinerary(self, ctx: "TravelContext") -> "Itinerary":
        """Confirm a draft itinerary."""
        return self.agents['ItineraryAgent'].confirm(ctx)
    
    def cancel_itinerary(self, ctx: "TravelContext") -> "Itinerary":
        """Cancel an itinerary."""
        return self.agents['ItineraryAgent'].cancel(ctx)
    

    
    # =========================================================================
    # Legacy Methods (for backward compatibility)
    # =========================================================================
    
    def run_intent(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute user intent by planning and coordinating agents.
        
        .. deprecated::
            This is a legacy method for non-context-aware execution.
            Used primarily in tests. For production code, use:
            - PlanningService.plan_trip() for NL queries
            - Orchestrator.execute_plan() for executing ExecutionPlan objects
        """
        logger.info(f"Running intent: needs={intent.get('needs', [])}")

        # Build plan via deterministic planner
        plan = self.planner.create_plan(intent, traveler_id=intent.get("traveler_id", ""))

        if plan.status == "needs_clarification":
            logger.info("Plan requires clarification; returning missing_info.")
            return {
                "status": plan.status,
                "missing_info": [mi.model_dump() for mi in plan.missing_info],
                "plan_id": plan.plan_metadata.plan_id,
            }

        # Execute tasks respecting dependencies (simple topo by readiness)
        results: Dict[str, Any] = {}
        context: Dict[str, Any] = {}
        completed = set()
        remaining = {t.id: t for t in plan.tasks}

        while remaining:
            ready = [
                t for t_id, t in remaining.items() if all(dep in completed for dep in t.dependencies)
            ]
            if not ready:
                logger.error("Circular dependency detected in plan tasks")
                break

            for task in ready:
                agent_name = task.agent
                task_name = task.action
                params = self._enrich_params(dict(task.params), context, {"task": task_name})

                if agent_name in self.agents:
                    agent = self.agents[agent_name]
                    try:
                        result = agent.execute(task_name, params)
                        logger.debug(f"Task {agent_name}.{task_name} completed")
                        results[f"{agent_name}.{task_name}"] = result
                        context[agent_name] = result
                    except Exception as e:
                        logger.error(f"Task {agent_name}.{task_name} failed: {e}")
                        error_result = {"error": str(e), "agent": agent_name, "task": task_name}
                        results[f"{agent_name}.{task_name}"] = error_result
                        context[agent_name] = error_result
                else:
                    logger.error(f"Unknown agent: {agent_name}")
                    error_result = {"error": f"Unknown agent: {agent_name}"}
                    results[f"{agent_name}.{task_name}"] = error_result

                completed.add(task.id)
                remaining.pop(task.id, None)

        logger.info(f"Intent completed: {len(results)} tasks executed")
        return {"status": "executed", "results": results, "plan_id": plan.plan_metadata.plan_id}
    
    def _enrich_params(self, params: Dict[str, Any], context: Dict[str, Any], 
                      current_task: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich task parameters with context from previous tasks"""
        enriched = params.copy()

        def _select_booking(value):
            """Pick a single booking dict if a list was returned by a search."""
            # Handle rich result from context-aware execution
            if isinstance(value, dict) and "reservation" in value:
                return value["reservation"]
            
            # Handle legacy list result
            if isinstance(value, list) and value:
                return value[0]
            
            # Handle direct dict result
            if isinstance(value, dict):
                return value
            return None
        
        # If building itinerary, include previous booking results
        if current_task.get('task') == 'build_itinerary':
            if 'FlightBookingAgent' in context:
                enriched['flight_reservation'] = _select_booking(context['FlightBookingAgent'])
            if 'HotelBookingAgent' in context:
                enriched['hotel_reservation'] = _select_booking(context['HotelBookingAgent'])
            if 'CarRentalAgent' in context:
                enriched['car_reservation'] = _select_booking(context['CarRentalAgent'])
        
        # If processing payment, include itinerary total if available
        if current_task.get('task') == 'process_payment':
            if 'ItineraryAgent' in context:
                itinerary = context['ItineraryAgent']
                if isinstance(itinerary, dict) and 'total_cost' in itinerary:
                    enriched['amount'] = enriched.get('amount', itinerary['total_cost'])
        
        return enriched
    
    def get_agent(self, agent_name: str):
        """Get an agent by name"""
        return self.agents.get(agent_name)
    
    def list_agents(self) -> list:
        """List all available agents"""
        return list(self.agents.keys())
