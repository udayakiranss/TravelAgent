Agentic Travel Booking System with LLM Integration
====================================================

This system demonstrates a multi-agent architecture for travel booking with:
- **LLM-based intelligent planning** - Uses foundation models to select appropriate agents
- **Specialized agents** - Each agent handles a specific domain with multiple tools
- **Flexible LLM integration** - Supports any foundation model (OpenAI, Anthropic, Google, etc.)
- **Agent orchestration** - Coordinates multiple agents to fulfill complex user intents

## Architecture

### Core Components

1. **LLM Provider** (`agents/llm_provider.py`)
   - Flexible abstraction supporting multiple foundation models
   - Supports OpenAI, Anthropic, Google, and other providers via LangChain
   - Handles structured output generation

2. **Planner** (`agents/planner.py`)
   - **LLM-based planning**: Uses foundation models to intelligently select agents and tasks
   - **Rule-based fallback**: Works without LLM for basic scenarios
   - Converts user intents into structured agent task plans

3. **Orchestrator** (`agents/orchestrator.py`)
   - Coordinates multiple specialized agents
   - Manages context between agent tasks
   - Enriches parameters with results from previous tasks

### Specialized Agents

Each agent is a self-contained unit with multiple tools:

1. **FlightBookingAgent** (`agents/flight_booking_agent.py`)
   - Tools: `search_flights`, `compare_flights`, `book_flight`
   - Handles all flight-related operations

2. **HotelBookingAgent** (`agents/hotel_booking_agent.py`)
   - Tools: `search_hotels`, `compare_hotels`, `book_hotel`
   - Manages hotel search and booking

3. **CarRentalAgent** (`agents/car_rental_agent.py`)
   - Tools: `search_cars`, `compare_cars`, `book_car`
   - Handles car rental operations

4. **ItineraryAgent** (`agents/itinerary_agent.py`)
   - Tools: `build_itinerary`, `update_itinerary`, `get_itinerary`, `list_itineraries`
   - Manages complete travel itineraries

5. **PaymentAgent** (`agents/payment_agent.py`)
   - Tools: `process_payment`, `verify_payment`
   - Handles payment processing

## Setup

1. Create a virtual environment and install requirements:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

2. Set your OpenAI API key (optional, for LLM-based planning):
```bash
export OPENAI_API_KEY="your-api-key-here"
# Or create a .env file with: OPENAI_API_KEY=your-api-key-here
```

3. Run the demo:
```bash
python main.py
```

## Features

### LLM-Based Agent Selection
The planner uses foundation models to intelligently:
- Select appropriate agents based on user intent
- Determine the right tasks for each agent
- Handle complex, multi-step queries

### Multi-Tool Agents
Each agent has multiple specialized tools:
- **Search tools**: Find available options
- **Compare tools**: Compare multiple options
- **Booking tools**: Complete reservations
- **Management tools**: Update and retrieve information

### Context-Aware Orchestration
The orchestrator:
- Passes results between agents
- Enriches task parameters with context
- Handles dependencies (e.g., itinerary needs booking results)

### Flexible Model Support
Easily switch between foundation models:
```python
# In main.py, change:
llm = create_llm_provider(
    model_name="gpt-4o",      # or "gpt-3.5-turbo", "claude-3-opus", etc.
    model_provider="openai",   # or "anthropic", "google", etc.
    temperature=0
)
```

## Example Usage

```python
from agents.orchestrator import Orchestrator
from agents.llm_provider import create_llm_provider

# Initialize with LLM
llm = create_llm_provider(model_name="gpt-4o", model_provider="openai")
orch = Orchestrator(llm=llm)

# Execute user intent
intent = {
    'needs': ['flight', 'hotel'],
    'from': 'NYC',
    'to': 'LON',
    'date': '2025-08-12'
}

results = orch.run_intent(intent)
```

## Project Structure

```
travel-agents/
├── agents/
│   ├── base_agent.py          # Base class for all agents
│   ├── llm_provider.py        # LLM integration layer
│   ├── planner.py             # LLM-based planning
│   ├── orchestrator.py        # Agent coordination
│   ├── flight_booking_agent.py
│   ├── hotel_booking_agent.py
│   ├── car_rental_agent.py
│   ├── itinerary_agent.py
│   ├── payment_agent.py
│   ├── memory.py             # Memory management
│   └── router.py             # Legacy router (deprecated)
├── tools/                    # Legacy tools (now integrated into agents)
├── data/                     # Hard-coded data (flights, hotels, cars)
├── main.py                   # Demo runner
└── requirements.txt          # Dependencies
```

## Notes

- The system works **with or without LLM** - falls back to rule-based planning if LLM is unavailable
- Each agent can use LLM internally for routing ambiguous tasks
- All agents follow the same `BaseAgent` interface for consistency
- Tools are implemented using LangChain's `@tool` decorator for compatibility
