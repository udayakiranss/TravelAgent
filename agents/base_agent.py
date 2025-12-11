# base_agent.py
# Base class for all agents
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from abc import ABC, abstractmethod
from agents.llm_provider import LLMProvider
from api.config import SelectionCriteria
from utils.logger import get_logger, log_method_entry_exit

if TYPE_CHECKING:
    from api.context import TravelContext

logger = get_logger()


class BaseAgent(ABC):
    """Base class for all agents"""
    
    def __init__(self, llm: Optional[LLMProvider] = None, name: str = ""):
        """
        Initialize base agent
        
        Args:
            llm: LLM provider instance
            name: Agent name
        """
        self.llm = llm
        self.name = name
        self.tools = self._initialize_tools()
        logger.info(f"Agent '{name}' initialized with {len(self.tools)} tools: {list(self.tools.keys())}")
    
    @abstractmethod
    def _initialize_tools(self) -> Dict[str, Any]:
        """Initialize agent-specific tools"""
        pass
    
    @abstractmethod
    def execute(self, task: str, params: Dict[str, Any], ctx: Optional["TravelContext"] = None) -> Any:
        """
        Execute a task using the agent's tools
        
        Args:
            task: Task name
            params: Task parameters
            ctx: Optional TravelContext for context-aware operations
        
        Returns:
            Task result
        """
        pass
    
    def get_available_tools(self) -> List[str]:
        """Get list of available tool names"""
        return list(self.tools.keys())
    
    def _call_tool(self, tool_name: str, params: Dict[str, Any]) -> Any:
        """Call a tool by name"""
        if tool_name not in self.tools:
            logger.error(f"Tool '{tool_name}' not found in agent '{self.name}'")
            raise ValueError(f"Tool '{tool_name}' not found in agent '{self.name}'")
        
        tool = self.tools[tool_name]
        
        try:
            # Handle LangChain StructuredTool
            if hasattr(tool, 'invoke'):
                return tool.invoke({'query': params})
            # Handle regular functions
            elif callable(tool):
                return tool(params)
            else:
                logger.error(f"Tool '{tool_name}' is not callable")
                raise ValueError(f"Tool '{tool_name}' is not callable")
        except Exception as e:
            logger.error(f"Tool '{tool_name}' failed in {self.name}: {e}")
            raise
    
    def _select_best(
        self, 
        options: List[Dict[str, Any]], 
        criteria: SelectionCriteria
    ) -> Optional[Dict[str, Any]]:
        """
        Select the best option from a list based on criteria.
        
        Can be overridden by subclasses for domain-specific selection logic.
        
        Args:
            options: List of options to choose from
            criteria: Selection criteria (cheapest, best_rated, first_available)
        
        Returns:
            The best option based on criteria, or None if no options
        """
        if not options:
            return None
        
        if criteria == SelectionCriteria.FIRST_AVAILABLE:
            selected = options[0]
        elif criteria == SelectionCriteria.CHEAPEST:
            def get_price(opt: Dict[str, Any]) -> float:
                return opt.get("price") or opt.get("total_price") or float("inf")
            selected = min(options, key=get_price)
        elif criteria == SelectionCriteria.BEST_RATED:
            def get_rating(opt: Dict[str, Any]) -> float:
                return opt.get("rating") or opt.get("score") or 0
            selected = max(options, key=get_rating)
        else:
            selected = options[0]
        
        logger.debug(f"{self.name} selected {selected.get('id', '?')} from {len(options)} options ({criteria.value})")
        return selected
