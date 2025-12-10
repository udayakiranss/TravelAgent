# orchestrator.py
# Orchestrator that coordinates agents to handle user intents
from typing import Dict, Any, Optional, List, TYPE_CHECKING
import json
import time

from agents.planner import plan_trip
from agents.llm_provider import LLMProvider, create_llm_provider, extract_token_usage
from agents.flight_booking_agent import FlightBookingAgent
from agents.hotel_booking_agent import HotelBookingAgent
from agents.car_rental_agent import CarRentalAgent
from agents.itinerary_agent import ItineraryAgent
from agents.payment_agent import PaymentAgent
from agents.response_formatter import ResponseFormatter
from api.config import SelectionCriteria, PreferenceLoadingMode, PREFERENCE_LOADING_MODE
from database.repository import LLMUnavailableError, UserPreferencesRepository
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
        logger.info(f"Orchestrator initialized with {len(self.agents)} agents")
    
    # =========================================================================
    # User Preferences Support
    # =========================================================================
    
    def _get_preference_summary(self, ctx: "TravelContext") -> str:
        """
        Get user preference summary for prompt inclusion (~50 tokens).
        
        Uses filesystem cache for fast reads. Returns default message if
        no preferences are set for the traveler.
        
        Args:
            ctx: TravelContext with session and traveler_id
        
        Returns:
            Compact preference summary string
        """
        if not ctx.traveler_id:
            return "No traveler ID provided"
        
        try:
            repo = UserPreferencesRepository(ctx.session)
            summary = repo.get_summary(ctx.traveler_id)
            logger.debug(f"Preference summary for {ctx.traveler_id}: {summary}")
            return summary
        except Exception as e:
            logger.warning(f"Failed to get preference summary for {ctx.traveler_id}: {e}")
            return "Unable to load preferences"
    
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
    
    def plan_trip(self, query: str, ctx: "TravelContext", include_summary: bool = True) -> Dict[str, Any]:
        """
        Plan a trip from natural language query.
        
        Parses the query, runs appropriate agents with context-aware selection,
        and creates a draft itinerary.
        
        Uses tiered preference loading:
        - Summary (~50 tokens) is always loaded for basic personalization
        - Full preferences (~500 tokens) available via tool if model needs them
        """
        # Load preference summary (always, fast ~5ms from cache)
        preference_summary = self._get_preference_summary(ctx)
        
        logger.info(f"Planning trip: traveler={ctx.traveler_id}, criteria={ctx.criteria.value}, mode={PREFERENCE_LOADING_MODE.value}, prefs={preference_summary[:50]}...")
        ctx.original_query = query
        
        # Store preference summary in context for later use
        ctx.preference_summary = preference_summary
        
        # Ensure LLM is available for NL parsing
        llm = ctx.llm or self.llm
        if llm is None:
            raise LLMUnavailableError("LLM is required for natural language trip planning")
        
        # Parse query to intent based on preference loading mode
        if PREFERENCE_LOADING_MODE == PreferenceLoadingMode.TOOL_BINDING:
            # Tool binding mode: LLM can call load_full_preferences for detailed prefs
            intent = self._interpret_query_with_tool_binding(query, llm, preference_summary, ctx)
        else:
            # Summary-only mode: just include summary in prompt (default, faster)
            intent = self._interpret_query_with_preferences(query, llm, preference_summary)
        
        # Run agents with context-aware selection (DD-3: Selection in Agents)
        flight_reservation = None
        hotel_reservation = None
        car_reservation = None
        
        flight_options = []
        hotel_options = []
        car_options = []
        
        needs = intent.get('needs', [])
        
        # Search flights if needed (search once, then select from results)
        if 'flight' in needs:
            flight_params = {
                'origin': intent.get('from', ''),
                'destination': intent.get('to', ''),
                'date': intent.get('date', '')
            }
            all_flights = self.agents['FlightBookingAgent'].execute('search_flights', flight_params)
            if isinstance(all_flights, list) and all_flights:
                flight_options = all_flights
                # Select best from existing results (no duplicate search)
                selected = self.agents['FlightBookingAgent']._select_best(all_flights, ctx.criteria)
                if selected:
                    flight_reservation = {
                        **selected,
                        "origin": selected.get("from", selected.get("origin")),
                        "destination": selected.get("to", selected.get("destination")),
                    }
        
        # Search hotels if needed (search once, then select from results)
        if 'hotel' in needs:
            hotel_params = {'city': intent.get('to', '')}
            all_hotels = self.agents['HotelBookingAgent'].execute('search_hotels', hotel_params)
            if isinstance(all_hotels, list) and all_hotels:
                hotel_options = all_hotels
                hotel_reservation = self.agents['HotelBookingAgent']._select_best(all_hotels, ctx.criteria)
        
        # Search cars if needed (search once, then select from results)
        if 'car' in needs:
            car_params = {'city': intent.get('to', '')}
            all_cars = self.agents['CarRentalAgent'].execute('search_cars', car_params)
            if isinstance(all_cars, list) and all_cars:
                car_options = all_cars
                car_reservation = self.agents['CarRentalAgent']._select_best(all_cars, ctx.criteria)
        
        # Build itinerary with selected reservations
        itinerary_agent = self.agents['ItineraryAgent']
        itinerary = itinerary_agent.build(
            flight_reservation=flight_reservation,
            hotel_reservation=hotel_reservation,
            car_reservation=car_reservation,
            ctx=ctx
        )
        
        # Update context with created itinerary
        ctx.itinerary_id = itinerary.id
        ctx.itinerary = itinerary
        
        logger.info(f"Created itinerary: id={itinerary.id}, total_cost=${itinerary.total_cost}")
        
        # Generate summary
        summary = f"Found {len(flight_options)} flights, {len(hotel_options)} hotels, {len(car_options)} cars"
        
        if include_summary and llm:
            try:
                # Prepare results for formatter (include preference context)
                results = {
                    "flight": flight_reservation,
                    "hotel": hotel_reservation,
                    "car": car_reservation,
                    "total_cost": itinerary.total_cost,
                    "traveler_preferences": preference_summary,
                }
                
                formatter = ResponseFormatter(llm=llm)
                summary = formatter.format_results(results, intent)
            except Exception as e:
                logger.warning(f"Failed to generate LLM summary: {e}")
        
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
            "query": query,
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
    # NL Interpretation (DD-1: Moved from main.py)
    # =========================================================================
    
    def _interpret_query_with_preferences(self, text: str, llm: LLMProvider, preference_summary: str) -> dict:
        """
        Use LLM to parse natural language into structured intent, with preference context.
        
        Args:
            text: User's natural language query
            llm: LLM provider
            preference_summary: Compact preference summary (~50 tokens)
        
        Returns:
            Structured intent dict
        """
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
            
            # Handle response format
            if isinstance(response, dict):
                if "raw_response" in response:
                    try:
                        return json.loads(response["raw_response"])
                    except Exception:
                        return self._interpret_rule_based(text)
                else:
                    intent = {
                        "needs": response.get("needs", []),
                        "from": response.get("from", ""),
                        "to": response.get("to", ""),
                        "date": response.get("date", "")
                    }
                    return {k: v for k, v in intent.items() if v or k == "needs"}
            else:
                return self._interpret_rule_based(text)
        
        except Exception as e:
            logger.warning(f"LLM parsing failed: {e}, falling back to rule-based parser")
            return self._interpret_rule_based(text)
    
    def _interpret_query_with_tool_binding(
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
        logger.info(f"Using tool binding mode for query interpretation")
        
        # Bind the preference tool to the LLM
        try:
            llm_with_tools = llm.llm.bind_tools([load_full_preferences])
        except Exception as e:
            logger.warning(f"Failed to bind tools: {e}, falling back to summary-only mode")
            return self._interpret_query_with_preferences(text, llm, preference_summary)
        
        # Track first LLM call timing
        start_time = time.perf_counter()
        logger.info("LLM (tool-binding) call: starting with summary + tool binding")
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
                logger.info(f"⏱ LLM (tool-binding) call: {_format_duration(duration_ms)} | tokens: {token_info['input']} in, {token_info['output']} out, {token_info['total']} total")
            else:
                logger.info(f"⏱ LLM (tool-binding) call: {_format_duration(duration_ms)}")
            logger.info(f"LLM (tool-binding) call complete in {_format_duration(duration_ms)}")
            
            # Check if model called the tool
            if hasattr(response, 'tool_calls') and response.tool_calls:
                logger.info(f"Model requested {len(response.tool_calls)} tool call(s)")
                
                for tool_call in response.tool_calls:
                    tool_name = tool_call.get('name', tool_call.get('function', {}).get('name', ''))
                    tool_args = tool_call.get('args', tool_call.get('function', {}).get('arguments', {}))
                    
                    if tool_name == 'load_full_preferences':
                        # Execute the tool
                        traveler_id = tool_args.get('traveler_id', ctx.traveler_id)
                        logger.info(f"Executing load_full_preferences for {traveler_id}")
                        tool_start = time.perf_counter()
                        
                        full_prefs = load_full_preferences.invoke({"traveler_id": traveler_id})
                        tool_duration_ms = (time.perf_counter() - tool_start) * 1000
                        logger.info(f"Tool load_full_preferences completed in {_format_duration(tool_duration_ms)}")
                        
                        # Store full preferences in context
                        ctx.full_preferences = full_prefs
                        
                        # Continue with enriched prompt
                        enriched_prompt = (
                            f"{prompt}\n\n"
                            f"Full Preferences Loaded:\n{json.dumps(full_prefs, indent=2)}"
                        )
                        
                        # Second LLM call with full preferences
                        logger.info("LLM (tool-binding) enriched call: starting with full preferences")
                        second_start = time.perf_counter()
                        response = llm.llm.invoke(enriched_prompt)
                        second_duration_ms = (time.perf_counter() - second_start) * 1000
                        token_info = extract_token_usage(response)
                        if token_info:
                            logger.info(f"⏱ LLM (tool-binding, enriched) call: {_format_duration(second_duration_ms)} | tokens: {token_info['input']} in, {token_info['output']} out, {token_info['total']} total")
                        else:
                            logger.info(f"⏱ LLM (tool-binding, enriched) call: {_format_duration(second_duration_ms)}")
                        logger.info(f"LLM (tool-binding, enriched) call complete in {_format_duration(second_duration_ms)}")
            
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
            logger.warning(f"JSON parsing failed in tool binding mode: {e}, falling back to rule-based")
            return self._interpret_rule_based(text)
        except Exception as e:
            logger.warning(f"Tool binding mode failed: {e}, falling back to summary-only mode")
            return self._interpret_query_with_preferences(text, llm, preference_summary)
    
    def _interpret_query(self, text: str, llm: LLMProvider) -> dict:
        """Use LLM to parse natural language into structured intent (legacy, no preferences)."""
        
        prompt = (
            "Parse the following user query about travel booking into a structured intent format.\n\n"
            f'User Query: "{text}"\n\n'
            "Extract the following information:\n"
            "- needs: List of services needed (flight, hotel, car, itinerary)\n"
            "- from: Origin airport code (3 letters, uppercase)\n"
            "- to: Destination airport code (3 letters, uppercase)\n"
            "- date: Travel date in YYYY-MM-DD format\n\n"
            "Return ONLY a valid JSON object with these fields. Example:\n"
            '{\n'
            '  "needs": ["flight", "hotel", "car", "itinerary"],\n'
            '  "from": "NYC",\n'
            '  "to": "LON",\n'
            '  "date": "2025-08-12"\n'
            '}'
        )

        try:
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
            
            # Handle response format
            if isinstance(response, dict):
                if "raw_response" in response:
                    try:
                        return json.loads(response["raw_response"])
                    except Exception:
                        return self._interpret_rule_based(text)
                else:
                    intent = {
                        "needs": response.get("needs", []),
                        "from": response.get("from", ""),
                        "to": response.get("to", ""),
                        "date": response.get("date", "")
                    }
                    return {k: v for k, v in intent.items() if v or k == "needs"}
            else:
                return self._interpret_rule_based(text)
        
        except Exception as e:
            logger.warning(f"LLM parsing failed: {e}, falling back to rule-based parser")
            return self._interpret_rule_based(text)
    
    def _interpret_rule_based(self, text: str) -> dict:
        """Simple rule-based NL parser (fallback when LLM fails)."""
        import re
        
        text_lower = text.lower()
        intent = {'needs': []}
        
        if 'flight' in text_lower or 'fly' in text_lower:
            intent['needs'].append('flight')
        if 'hotel' in text_lower or 'stay' in text_lower:
            intent['needs'].append('hotel')
        if 'car' in text_lower or 'rental' in text_lower:
            intent['needs'].append('car')
        
        m = re.search(r'from ([a-z]{3}) to ([a-z]{3})', text_lower)
        if m:
            intent['from'] = m.group(1).upper()
            intent['to'] = m.group(2).upper()
        
        d = re.search(r'(\d{4}-\d{2}-\d{2})', text)
        if d:
            intent['date'] = d.group(1)
        
        return intent
    
    # =========================================================================
    # Legacy Methods (for backward compatibility)
    # =========================================================================
    
    def run_intent(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute user intent by planning and coordinating agents.
        
        This is the legacy method for non-context-aware execution.
        For new code, use plan_trip() with TravelContext.
        """
        logger.info(f"Running intent: needs={intent.get('needs', [])}")
        
        # Use LLM-based planner to create a plan
        tasks = plan_trip(intent, llm=self.llm)
        
        logger.info(f"Planned {len(tasks)} tasks")
        print(f"Planned {len(tasks)} tasks:")
        for i, task in enumerate(tasks, 1):
            task_info = f"{task.get('agent')} -> {task.get('task')}"
            print(f"  {i}. {task_info}")
        
        results = {}
        context = {}  # Store results for context-dependent tasks
        
        # Execute tasks in order
        for task in tasks:
            agent_name = task.get('agent')
            task_name = task.get('task')
            params = task.get('params', {})
            
            # Enrich params with context from previous tasks
            params = self._enrich_params(params, context, task)
            
            # Route to appropriate agent
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
        
        logger.info(f"Intent completed: {len(results)} tasks executed")
        return results
    
    def _enrich_params(self, params: Dict[str, Any], context: Dict[str, Any], 
                      current_task: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich task parameters with context from previous tasks"""
        enriched = params.copy()

        def _select_booking(value):
            """Pick a single booking dict if a list was returned by a search."""
            if isinstance(value, list) and value:
                return value[0]
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
