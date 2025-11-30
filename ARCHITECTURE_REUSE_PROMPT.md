# Prompt: Reusing Project Structure for New Agentic AI Projects

## Overview

This document provides a comprehensive guide for reusing the existing project structure, base files, and architectural patterns from the Travel Booking Agent System for building new agentic AI projects. The system provides a robust foundation with logging, LLM abstraction, base agent classes, orchestration, and planning capabilities.

## Project Structure to Reuse

```
project-root/
├── agents/
│   ├── base_agent.py          # Base class for all agents (REUSE)
│   ├── llm_provider.py        # LLM integration abstraction (REUSE)
│   ├── orchestrator.py        # Agent coordination pattern (ADAPT)
│   ├── planner.py             # Planning logic (ADAPT)
│   ├── memory.py              # Memory/conversation management (REUSE/ADAPT)
│   └── [your_domain]_agent.py # Your domain-specific agents (CREATE)
├── utils/
│   ├── logger.py              # Comprehensive logging system (REUSE)
│   └── __init__.py            # Utils package (REUSE)
├── tools/                     # Domain-specific tools (CREATE)
├── data/                      # Domain-specific data (CREATE)
├── main.py                    # Application entry point (ADAPT)
├── requirements.txt           # Dependencies (REUSE/EXTEND)
├── .gitignore                 # Git ignore rules (REUSE)
└── logs/                      # Log files directory (AUTO-CREATED)
```

## Core Components to Reuse

### 1. Logging System (`utils/logger.py`)

**Status: REUSE AS-IS**

The logging system provides:
- Session tracking with unique IDs
- Multiple output destinations (stdout, file, both)
- Method entry/exit decorators
- Contextual logging with filename, line number, function name
- Configurable log levels via environment variables

**How to Use:**
```python
from utils.logger import get_logger, SessionContext, log_method_entry_exit, log_critical_entry_exit

# Initialize logger
logger = get_logger()
logger.setup(level="INFO", output="both", log_file="myapp.log")

# Create session
SessionContext.new_session()

# Use decorators
@log_method_entry_exit(level="DEBUG")
def my_function():
    logger.info("Processing...")
    pass

@log_critical_entry_exit
def critical_function():
    pass
```

**Environment Variables:**
- `LOG_LEVEL`: DEBUG, INFO, WARNING, ERROR, CRITICAL (default: INFO)
- `LOG_OUTPUT`: stdout, file, or both (default: stdout)
- `LOG_FILE`: Custom log file name (optional)
- `LOG_DIR`: Log directory (default: logs/)

**Action:** Copy `utils/logger.py` and `utils/__init__.py` as-is. No modifications needed.

---

### 2. LLM Provider Abstraction (`agents/llm_provider.py`)

**Status: REUSE AS-IS**

The LLM provider provides:
- Abstract interface for multiple LLM providers
- LangChain integration supporting OpenAI, Anthropic, Google, etc.
- Structured output generation
- Flexible model switching

**How to Use:**
```python
from agents.llm_provider import create_llm_provider, LLMProvider

# Create LLM provider
llm = create_llm_provider(
    model_name="gpt-4o",        # or "gpt-3.5-turbo", "claude-3-opus", etc.
    model_provider="openai",    # or "anthropic", "google", etc.
    temperature=0
)

# Use for text generation
response = llm.invoke("Your prompt here")

# Use for structured output
structured = llm.invoke_structured(
    "Extract information from this text...",
    response_format={
        "type": "object",
        "properties": {
            "field1": {"type": "string"},
            "field2": {"type": "number"}
        }
    }
)
```

**Action:** Copy `agents/llm_provider.py` as-is. Ensure `langchain` and `langchain-openai` are in your `requirements.txt`.

---

### 3. Base Agent Class (`agents/base_agent.py`)

**Status: REUSE AS-IS**

The BaseAgent provides:
- Abstract interface for all agents
- Tool management system
- LLM integration support
- Consistent agent structure

**How to Use:**
```python
from agents.base_agent import BaseAgent
from agents.llm_provider import LLMProvider
from typing import Dict, Any

class MyDomainAgent(BaseAgent):
    """Your domain-specific agent"""
    
    def __init__(self, llm: LLMProvider = None, name: str = "MyDomainAgent"):
        super().__init__(llm=llm, name=name)
    
    def _initialize_tools(self) -> Dict[str, Any]:
        """Initialize your domain-specific tools"""
        from langchain.tools import tool
        
        @tool
        def my_tool(query: str) -> str:
            """Tool description for LLM"""
            # Your tool implementation
            return "result"
        
        return {
            "my_tool": my_tool,
            # Add more tools...
        }
    
    def execute(self, task: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a task using agent's tools"""
        if task == "my_task":
            result = self._call_tool("my_tool", params)
            return {"status": "success", "result": result}
        else:
            raise ValueError(f"Unknown task: {task}")
```

**Action:** Copy `agents/base_agent.py` as-is. Create your domain-specific agents by inheriting from BaseAgent.

---

### 4. Memory System (`agents/memory.py`)

**Status: REUSE/ADAPT**

Simple memory placeholder for conversation history.

**How to Use:**
```python
from agents.memory import create_memory

memory = create_memory()
# Use in orchestrator or agents as needed
```

**Action:** Copy `agents/memory.py` as-is, or extend it with more sophisticated memory management if needed.

---

### 5. Orchestrator Pattern (`agents/orchestrator.py`)

**Status: ADAPT FOR YOUR DOMAIN**

The orchestrator coordinates multiple agents to fulfill complex intents.

**Key Responsibilities:**
- Register domain-specific agents
- Coordinate agent execution
- Manage context between agents
- Handle task dependencies

**How to Adapt:**
```python
from agents.orchestrator import Orchestrator  # Use as reference
from agents.llm_provider import LLMProvider
from agents.my_domain_agent import MyDomainAgent

class MyDomainOrchestrator:
    """Orchestrator for your domain"""
    
    def __init__(self, llm: LLMProvider = None):
        self.llm = llm
        self.agents = {
            "my_domain": MyDomainAgent(llm=llm),
            # Add more agents...
        }
    
    def run_intent(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Execute user intent using appropriate agents"""
        # Your orchestration logic
        pass
```

**Action:** Use `agents/orchestrator.py` as a reference. Adapt the agent registration and execution logic for your domain.

---

### 6. Planner Pattern (`agents/planner.py`)

**Status: ADAPT FOR YOUR DOMAIN**

The planner converts user intents into structured agent task plans.

**How to Adapt:**
```python
from agents.planner import plan_trip  # Use as reference
from agents.llm_provider import LLMProvider

def plan_my_domain_task(intent: Dict[str, Any], llm: LLMProvider = None) -> List[Dict]:
    """Plan tasks for your domain"""
    if llm:
        # Use LLM-based planning
        prompt = f"Plan tasks for: {intent}"
        # ... LLM planning logic
    else:
        # Rule-based fallback
        # ... Rule-based planning logic
    return tasks
```

**Action:** Use `agents/planner.py` as a reference. Adapt the planning logic for your domain's task structure.

---

## Step-by-Step Setup Guide

### Step 1: Copy Base Files

Copy these files **as-is** (no modifications needed):
```
utils/logger.py
utils/__init__.py
agents/llm_provider.py
agents/base_agent.py
agents/memory.py
```

### Step 2: Adapt Orchestration Files

Use these as **templates** and adapt for your domain:
```
agents/orchestrator.py  → Adapt agent registration and execution
agents/planner.py       → Adapt planning logic for your domain
main.py                 → Adapt entry point and intent parsing
```

### Step 3: Create Domain-Specific Components

Create new files for your domain:
```
agents/[your_domain]_agent.py  # Your agents inheriting from BaseAgent
tools/[your_domain]_tools.py   # Your domain-specific tools
data/[your_domain]_data.py     # Your domain data (if needed)
```

### Step 4: Update Dependencies

Copy and extend `requirements.txt`:
```
langchain
langchain-openai
openai
python-dotenv
# Add your domain-specific dependencies
```

### Step 5: Configure Environment

Create `.env` file or set environment variables:
```bash
# LLM Configuration
OPENAI_API_KEY=your-api-key-here

# Logging Configuration
LOG_LEVEL=INFO
LOG_OUTPUT=both
LOG_FILE=myapp.log
LOG_DIR=logs
```

---

## Example: Creating a New E-Commerce Agent System

### 1. Create Domain Agents

```python
# agents/product_agent.py
from agents.base_agent import BaseAgent
from agents.llm_provider import LLMProvider
from typing import Dict, Any
from langchain.tools import tool

class ProductAgent(BaseAgent):
    def __init__(self, llm: LLMProvider = None):
        super().__init__(llm=llm, name="ProductAgent")
    
    def _initialize_tools(self) -> Dict[str, Any]:
        @tool
        def search_products(query: str) -> str:
            """Search for products"""
            # Implementation
            return "products"
        
        return {"search_products": search_products}
    
    def execute(self, task: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if task == "search":
            result = self._call_tool("search_products", params)
            return {"products": result}
        raise ValueError(f"Unknown task: {task}")
```

### 2. Create Orchestrator

```python
# agents/orchestrator.py (adapted)
from agents.product_agent import ProductAgent
from agents.llm_provider import LLMProvider
from utils.logger import get_logger

logger = get_logger()

class ECommerceOrchestrator:
    def __init__(self, llm: LLMProvider = None):
        self.llm = llm
        self.agents = {
            "product": ProductAgent(llm=llm),
            # Add more agents...
        }
    
    def run_intent(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"Running intent: {intent}")
        # Your orchestration logic
        return results
```

### 3. Create Main Entry Point

```python
# main.py (adapted)
from agents.orchestrator import ECommerceOrchestrator
from agents.llm_provider import create_llm_provider
from utils.logger import get_logger, SessionContext
import os
from dotenv import load_dotenv

load_dotenv()

logger = get_logger()

def main():
    logger.setup()
    SessionContext.new_session()
    
    llm = create_llm_provider(model_name="gpt-4o", model_provider="openai")
    orch = ECommerceOrchestrator(llm=llm)
    
    intent = {"action": "search", "query": "laptop"}
    results = orch.run_intent(intent)
    print(results)

if __name__ == '__main__':
    main()
```

---

## Key Design Patterns

### 1. Agent Pattern
- All agents inherit from `BaseAgent`
- Each agent has multiple tools
- Agents can use LLM for internal routing
- Consistent `execute(task, params)` interface

### 2. Orchestration Pattern
- Single orchestrator coordinates multiple agents
- Agents are registered in orchestrator
- Context is passed between agents
- Results are aggregated

### 3. Planning Pattern
- LLM-based planning with rule-based fallback
- Converts intents to structured task plans
- Handles complex multi-step queries

### 4. Logging Pattern
- Session-based logging with unique IDs
- Method entry/exit decorators
- Configurable via environment variables
- Multiple output destinations

---

## Best Practices

1. **Always use the logger**: Import and use `get_logger()` in all modules
2. **Create new sessions**: Call `SessionContext.new_session()` at application start
3. **Inherit from BaseAgent**: All agents should inherit from `BaseAgent`
4. **Use LLM abstraction**: Always use `LLMProvider` interface, never direct LLM calls
5. **Handle LLM failures**: Always provide rule-based fallbacks when LLM is unavailable
6. **Follow naming conventions**: Use descriptive names like `[Domain]Agent`, `[Domain]Orchestrator`
7. **Document tools**: Provide clear docstrings for all tools (used by LLM)
8. **Test without LLM**: Ensure system works with rule-based fallbacks

---

## Migration Checklist

- [ ] Copy `utils/logger.py` and `utils/__init__.py`
- [ ] Copy `agents/llm_provider.py`
- [ ] Copy `agents/base_agent.py`
- [ ] Copy `agents/memory.py`
- [ ] Adapt `agents/orchestrator.py` for your domain
- [ ] Adapt `agents/planner.py` for your domain
- [ ] Create domain-specific agents inheriting from `BaseAgent`
- [ ] Create domain-specific tools
- [ ] Adapt `main.py` for your entry point
- [ ] Update `requirements.txt` with dependencies
- [ ] Create `.env` file with configuration
- [ ] Test logging system
- [ ] Test LLM provider initialization
- [ ] Test agent execution
- [ ] Test orchestrator coordination
- [ ] Test with and without LLM (fallback mode)

---

## Troubleshooting

### Logging Issues
- Ensure `logger.setup()` is called before logging
- Check `LOG_LEVEL` environment variable
- Verify `logs/` directory is writable

### LLM Issues
- Verify API key is set in environment
- Check LangChain installation: `pip install langchain langchain-openai`
- Test LLM provider creation separately

### Agent Issues
- Ensure all agents inherit from `BaseAgent`
- Verify `_initialize_tools()` returns a dict
- Check `execute()` method handles all tasks

### Import Issues
- Verify Python path includes project root
- Check `__init__.py` files exist in packages
- Use absolute imports: `from agents.base_agent import BaseAgent`

---

## Summary

This project structure provides a robust foundation for building agentic AI systems with:
- ✅ Comprehensive logging with session tracking
- ✅ Flexible LLM provider abstraction
- ✅ Consistent agent interface via BaseAgent
- ✅ Orchestration pattern for multi-agent coordination
- ✅ Planning pattern with LLM and rule-based fallbacks
- ✅ Memory management support

**Reuse Strategy:**
- **Copy as-is**: logger.py, llm_provider.py, base_agent.py, memory.py
- **Adapt for domain**: orchestrator.py, planner.py, main.py
- **Create new**: domain-specific agents, tools, data

By following this guide, you can quickly bootstrap a new agentic AI project while maintaining consistency with the proven architecture patterns.
