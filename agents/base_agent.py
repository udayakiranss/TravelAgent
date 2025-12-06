# base_agent.py
# Base class for all agents
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod
from agents.llm_provider import LLMProvider
from utils.logger import get_logger, log_method_entry_exit

logger = get_logger()


class BaseAgent(ABC):
    """Base class for all agents"""
    
    @log_method_entry_exit(level="DEBUG")
    def __init__(self, llm: Optional[LLMProvider] = None, name: str = ""):
        """
        Initialize base agent
        
        Args:
            llm: LLM provider instance
            name: Agent name
        """
        logger.debug(f"Initializing agent: {name}")
        self.llm = llm
        self.name = name
        self.tools = self._initialize_tools()
        logger.info(f"Agent '{name}' initialized with {len(self.tools)} tools: {list(self.tools.keys())}")
    
    @abstractmethod
    def _initialize_tools(self) -> Dict[str, Any]:
        """Initialize agent-specific tools"""
        pass
    
    @abstractmethod
    def execute(self, task: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a task using the agent's tools
        
        Args:
            task: Task name
            params: Task parameters
        
        Returns:
            Task result
        """
        pass
    
    def get_available_tools(self) -> List[str]:
        """Get list of available tool names"""
        return list(self.tools.keys())
    
    @log_method_entry_exit(level="DEBUG")
    def _call_tool(self, tool_name: str, params: Dict[str, Any]) -> Any:
        """Call a tool by name"""
        logger.debug(f"Agent '{self.name}' calling tool '{tool_name}' with params: {params}")
        if tool_name not in self.tools:
            logger.error(f"Tool '{tool_name}' not found in agent '{self.name}'")
            raise ValueError(f"Tool '{tool_name}' not found in agent '{self.name}'")
        
        tool = self.tools[tool_name]
        
        try:
            # Handle LangChain StructuredTool
            if hasattr(tool, 'invoke'):
                result = tool.invoke({'query': params})
                logger.debug(f"Tool '{tool_name}' executed successfully")
                return result
            # Handle regular functions
            elif callable(tool):
                result = tool(params)
                logger.debug(f"Tool '{tool_name}' executed successfully")
                return result
            else:
                logger.error(f"Tool '{tool_name}' is not callable")
                raise ValueError(f"Tool '{tool_name}' is not callable")
        except Exception as e:
            logger.error(f"Error executing tool '{tool_name}' in agent '{self.name}': {e}", exc_info=True)
            raise

