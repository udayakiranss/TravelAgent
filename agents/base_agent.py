# base_agent.py
# Base class for all agents
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod
from agents.llm_provider import LLMProvider


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
    
    def _call_tool(self, tool_name: str, params: Dict[str, Any]) -> Any:
        """Call a tool by name"""
        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' not found in agent '{self.name}'")
        
        tool = self.tools[tool_name]
        
        # Handle LangChain StructuredTool
        if hasattr(tool, 'invoke'):
            return tool.invoke({'query': params})
        # Handle regular functions
        elif callable(tool):
            return tool(params)
        else:
            raise ValueError(f"Tool '{tool_name}' is not callable")

