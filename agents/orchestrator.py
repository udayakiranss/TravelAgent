# orchestrator.py
# Orchestrator that coordinates agents to handle user intents
from typing import Dict, Any, Optional
from agents.planner import plan_trip
from agents.llm_provider import LLMProvider, create_llm_provider
from agents.flight_booking_agent import FlightBookingAgent
from agents.hotel_booking_agent import HotelBookingAgent
from agents.car_rental_agent import CarRentalAgent
from agents.itinerary_agent import ItineraryAgent
from agents.payment_agent import PaymentAgent
from utils.logger import get_logger, log_critical_entry_exit, log_method_entry_exit

logger = get_logger()


class Orchestrator:
    """Orchestrator that coordinates multiple agents to fulfill user intents"""
    
    @log_method_entry_exit(level="INFO")
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
                logger.debug("Creating LLM provider")
                self.llm = create_llm_provider(
                    model_name=model_name,
                    model_provider=model_provider,
                    temperature=0
                )
                logger.info(f"LLM provider created: {model_name} ({model_provider})")
            except Exception as e:
                logger.warning(f"Could not initialize LLM: {e}. Continuing without LLM.")
                self.llm = None
        else:
            logger.debug(f"Using provided LLM: {llm.model_name}")
            self.llm = llm
        
        self.memory = memory
        
        # Initialize agents (each agent can optionally use LLM for internal routing)
        logger.debug("Initializing agents")
        self.agents = {
            'FlightBookingAgent': FlightBookingAgent(llm=self.llm),
            'HotelBookingAgent': HotelBookingAgent(llm=self.llm),
            'CarRentalAgent': CarRentalAgent(llm=self.llm),
            'ItineraryAgent': ItineraryAgent(llm=self.llm),
            'PaymentAgent': PaymentAgent(llm=self.llm),
        }
        logger.info(f"Initialized {len(self.agents)} agents")
    
    @log_critical_entry_exit
    def run_intent(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute user intent by planning and coordinating agents
        
        Args:
            intent: User intent dictionary
        
        Returns:
            Dictionary of results from all agents
        """
        logger.info(f"Running intent: {intent}")
        
        # Use LLM-based planner to create a plan
        logger.debug("Creating plan from intent")
        tasks = plan_trip(intent, llm=self.llm)
        
        logger.info(f"Planned {len(tasks)} tasks")
        print(f"Planned {len(tasks)} tasks:")
        for i, task in enumerate(tasks, 1):
            task_info = f"{task.get('agent')} -> {task.get('task')}"
            logger.debug(f"Task {i}: {task_info}")
            print(f"  {i}. {task_info}")
        
        results = {}
        context = {}  # Store results for context-dependent tasks
        
        # Execute tasks in order
        for task in tasks:
            agent_name = task.get('agent')
            task_name = task.get('task')
            params = task.get('params', {})
            
            logger.debug(f"Executing task: {agent_name}.{task_name} with params: {params}")
            
            # Enrich params with context from previous tasks
            params = self._enrich_params(params, context, task)
            logger.debug(f"Enriched params: {params}")
            
            # Route to appropriate agent
            if agent_name in self.agents:
                agent = self.agents[agent_name]
                try:
                    logger.debug(f"Calling agent {agent_name} with task {task_name}")
                    result = agent.execute(task_name, params)
                    logger.info(f"Task {agent_name}.{task_name} completed successfully")
                    results[f"{agent_name}.{task_name}"] = result
                    
                    # Store result in context for subsequent tasks
                    context[agent_name] = result
                except Exception as e:
                    logger.error(f"Error executing {agent_name}.{task_name}: {e}", exc_info=True)
                    error_result = {"error": str(e), "agent": agent_name, "task": task_name}
                    results[f"{agent_name}.{task_name}"] = error_result
                    context[agent_name] = error_result
            else:
                logger.error(f"Unknown agent: {agent_name}")
                error_result = {"error": f"Unknown agent: {agent_name}"}
                results[f"{agent_name}.{task_name}"] = error_result
        
        logger.info(f"Intent execution completed with {len(results)} results")
        return results
        
        return results
    
    @log_method_entry_exit(level="DEBUG")
    def _enrich_params(self, params: Dict[str, Any], context: Dict[str, Any], 
                      current_task: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich task parameters with context from previous tasks"""
        logger.debug(f"Enriching params with context: {list(context.keys())}")
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
                enriched['flight_booking'] = _select_booking(context['FlightBookingAgent'])
            if 'HotelBookingAgent' in context:
                enriched['hotel_booking'] = _select_booking(context['HotelBookingAgent'])
            if 'CarRentalAgent' in context:
                enriched['car_booking'] = _select_booking(context['CarRentalAgent'])
        
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
