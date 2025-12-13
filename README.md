# Agentic Travel Booking System with LLM Integration

This system demonstrates a multi-agent architecture for travel booking with:
- **Model Invocation Strategy** - Centralized LLM configuration with use-case-specific provider/model selection
- **LLM-based intelligent planning** - Uses foundation models to select appropriate agents
- **Specialized agents** - Each agent handles a specific domain with multiple tools
- **Flexible LLM integration** - Supports any foundation model (OpenAI, Anthropic, Google, etc.)
- **Prompt Repository** - Centralized prompt management with template support
- **Agent orchestration** - Coordinates multiple agents to fulfill complex user intents
- **Service layer** - Encapsulates business logic behind the API routes
- **User Preferences** - Personalized recommendations via tiered preference loading
- **REST API** - FastAPI-based web API for building frontend applications
- **Persistent Storage** - SQLite database with filesystem caching
- **MCP Server** - Direct integration with LLMs via Model Context Protocol

## Quick Start

```bash
# Setup
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Set API key (optional, for LLM-based planning)
export OPENAI_API_KEY="your-api-key-here"
```

### Option 1: Web API

```bash
# Start the API server
python -m uvicorn main_web:app --reload --port 8000

# API Documentation
# Swagger UI: http://localhost:8000/docs
# ReDoc: http://localhost:8000/redoc
```

### Option 2: MCP Server (for Claude Desktop / Cursor)

The system includes a **Model Context Protocol (MCP)** server that allows LLMs (like Claude Desktop or Cursor Agent) to directly interact with your running API.

#### Prerequisites
- Python 3.10 or higher is required for the `mcp` package.
- The main API (`main_web.py`) must be running on port 8000.

#### Setup MCP Environment
Since the system python might be older (e.g., 3.9), create a dedicated venv with Python 3.11+:

```bash
# Install Python 3.11 (if needed)
brew install python@3.11

# Create venv
/opt/homebrew/bin/python3.11 -m venv venv311
source venv311/bin/activate

# Install dependencies
pip install "mcp[cli]" httpx fastapi uvicorn sqlmodel aiosqlite python-multipart python-dotenv
```

#### Running the Server
You can run the server manually to test:
```bash
/path/to/venv311/bin/python mcp/server.py
```

#### Configuration for Clients

**Claude Desktop App**:
Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "travel-agent": {
      "command": "/absolute/path/to/venv311/bin/python",
      "args": [
        "/absolute/path/to/project/mcp/server.py"
      ]
    }
  }
}
```

**Cursor**:
1. Go to **Settings > General > MCP Servers**.
2. Click **Add new MCP server**.
3. Name: `travel-agent`
4. Type: `stdio`
5. Command: `/absolute/path/to/venv311/bin/python`
6. Args: `/absolute/path/to/project/mcp/server.py`

---

## Architecture

### System Overview

```mermaid
graph TB
    subgraph "Client Layer"
        WEB[Web Browser]
        MCP[MCP Client<br/>Claude/Cursor]
    end
    
    subgraph "API Layer"
        FASTAPI[FastAPI Server<br/>main_web.py]
        ROUTES[Routes<br/>HTTP Controllers]
        SERVICES[Services<br/>Business Logic]
    end
    
    subgraph "LLM Layer"
        LLM_STRAT[Model Invocation Strategy<br/>llm/strategy/]
        LLM_PROV[LLM Providers<br/>llm/providers/]
        PROMPTS[Prompt Repository<br/>llm/prompts/]
    end
    
    subgraph "Agent Layer"
        ORCH[Orchestrator<br/>Agent Coordination]
        PLAN[Planner<br/>LLM-based Planning]
        AGENTS[Domain Agents<br/>Flight/Hotel/Car/Itinerary/Payment]
    end
    
    subgraph "Data Layer"
        DB[(SQLite Database)]
        CACHE[Filesystem Cache<br/>Preferences]
        TOOLS[Search Tools<br/>Mock Data]
    end
    
    WEB --> FASTAPI
    MCP --> FASTAPI
    FASTAPI --> ROUTES
    ROUTES --> SERVICES
    SERVICES --> ORCH
    SERVICES --> PLAN
    ORCH --> AGENTS
    PLAN --> ORCH
    PLAN --> LLM_STRAT
    ORCH --> LLM_STRAT
    AGENTS --> LLM_STRAT
    LLM_STRAT --> LLM_PROV
    LLM_STRAT --> PROMPTS
    AGENTS --> DB
    AGENTS --> CACHE
    AGENTS --> TOOLS
```

### Core Components

1. **Model Invocation Strategy** (`llm/`)
   - **Centralized LLM configuration** - YAML-based configuration for provider/model selection per use case
   - **Use case management** - Different providers/models/settings for planner, intent parsing, summaries, etc.
   - **Prompt repository** - Centralized prompt storage with template substitution
   - **Provider factory** - Creates provider instances based on configuration
   - **Fail-fast validation** - Configuration errors detected at startup
   - See `docs/MODEL_INVOCATION_STRATEGY_DESIGN.md` for detailed design

2. **LLM Provider** (`agents/core/llm_provider.py`, `llm/providers/`)
   - Flexible abstraction supporting multiple foundation models
   - Supports OpenAI, Anthropic, Google, and other providers via LangChain
   - Handles structured output generation
   - Uses Model Invocation Strategy internally for configuration

2. **Planner** (`agents/planning/planner.py`)
   - **LLM-based planning**: Uses foundation models to intelligently select agents and tasks
   - **Deterministic fallback**: Works without LLM for basic scenarios
   - Converts user intents into structured `ExecutionPlan` with task DAGs
   - Includes alias resolution for city/airport names

3. **Orchestrator** (`agents/orchestration/orchestrator.py`)
   - Coordinates multiple specialized agents
   - Executes `ExecutionPlan` tasks in dependency order
   - Manages `TravelContext` flow to agents
   - Handles preference loading and tool execution
   - Delegates status transitions to ItineraryAgent

4. **TravelContext** (`api/context.py`)
   - Shared mutable context flowing through Routes → Services → Orchestrator → Agents
   - Carries request-scoped data (session, LLM, traveler_id, criteria)
   - Carries conversation-scoped data (itinerary, chat_history, preferences)
   - **Stops at Agents** — Repositories only receive `session`

5. **Service Layer** (`api/services/`)
   - Encapsulates business logic for itineraries, preferences, search, health, conversation, and planning
   - Keeps routes thin and testable; services coordinate with Orchestrator/Repositories
   - Services: `PlanningService`, `ItineraryService`, `PreferenceService`, `SearchService`, `HealthService`, `ConversationService`

6. **Web API** (`api/`, `main_web.py`)
   - **Thin HTTP controllers** that delegate to Services
   - FastAPI-based REST API with Swagger/OpenAPI
   - SQLite persistence layer
   - Request ID middleware for traceability
   - CORS support for frontend integration

7. **MCP Server** (`mcp/server.py`)
   - Exposes API capabilities as **Tools** (actions) and **Resources** (read-only context)
   - Allows LLMs to plan trips, modify itineraries, and check status directly
   - Includes full request tracing and logging integration

### Request Flow

#### Planning Flow (Natural Language Trip Planning)

```mermaid
sequenceDiagram
    participant Client
    participant Route as Agent Route
    participant PS as PlanningService
    participant Planner as TravelPlanner
    participant Orch as Orchestrator
    participant Agents as Domain Agents
    participant Repo as Repository
    participant DB as Database

    Client->>Route: POST /agent/plan<br/>{query, traveler_id}
    Route->>PS: plan_trip(request, ctx)
    
    PS->>PS: Load preference summary
    PS->>Planner: create_plan_from_query(query, ctx)
    
    alt LLM Available
        Planner->>Planner: LLM-based plan generation
    else LLM Unavailable
        Planner->>Planner: Deterministic planning (fallback)
    end
    
    Planner-->>PS: ExecutionPlan (tasks, dependencies)
    
    alt Plan Needs Clarification
        PS-->>Client: 400 Missing Information
    else Plan Executable
        PS->>Orch: execute_plan(plan, ctx)
        
        loop For each task in plan
            Orch->>Agents: execute(action, params, ctx)
            Agents->>TOOLS: Search/Book operations
            Agents->>Repo: Persist results (via ctx.session)
            Repo->>DB: Save itinerary/bookings
        end
        
        Orch-->>PS: Result (itinerary_id, options, reservations)
        PS-->>Route: PlanResponse
        Route-->>Client: 200 Success with itinerary
    end
```

#### Non-Planning Flows (CRUD Operations)

```mermaid
sequenceDiagram
    participant Client
    participant Route as API Route
    participant Service as Service Layer
    participant Orch as Orchestrator/Repo
    participant DB as Database

    Client->>Route: HTTP Request<br/>(GET/POST/PUT/DELETE)
    Route->>Service: Service method(ctx)
    
    alt Itinerary Operations
        Service->>Orch: Orchestrator method(ctx)
        Orch->>DB: CRUD via Repository
    else Preference Operations
        Service->>Orch: Repository operations
        Orch->>DB: Save/load preferences
    else Search Operations
        Service->>Orch: Search tools
        Orch-->>Service: Search results
    end
    
    Service-->>Route: Response data
    Route-->>Client: HTTP Response
```

### Agent Organization

```mermaid
graph LR
    subgraph "LLM Module"
        STRAT[ModelInvocationStrategy<br/>llm/strategy/]
        PROV[Providers<br/>llm/providers/]
        PROMPT[PromptRepository<br/>llm/prompts/]
    end
    
    subgraph "Core Agents"
        BASE[BaseAgent<br/>agents/core/base_agent.py]
        LLM[LLMProvider<br/>agents/core/llm_provider.py]
        MEM[Memory<br/>agents/core/memory.py]
    end
    
    subgraph "Domain Agents"
        FLIGHT[FlightBookingAgent<br/>agents/domain/flight_booking_agent.py]
        HOTEL[HotelBookingAgent<br/>agents/domain/hotel_booking_agent.py]
        CAR[CarRentalAgent<br/>agents/domain/car_rental_agent.py]
        ITIN[ItineraryAgent<br/>agents/domain/itinerary_agent.py]
        PAY[PaymentAgent<br/>agents/domain/payment_agent.py]
    end
    
    subgraph "Orchestration"
        ORCH[Orchestrator<br/>agents/orchestration/orchestrator.py]
        RESP[ResponseFormatter<br/>agents/orchestration/response_formatter.py]
    end
    
    subgraph "Planning"
        PLAN[TravelPlanner<br/>agents/planning/planner.py]
        DET[DeterministicPlanner<br/>agents/planning/deterministic_planner.py]
        ALIAS[AliasResolver<br/>agents/planning/alias_resolver.py]
    end
    
    BASE --> FLIGHT
    BASE --> HOTEL
    BASE --> CAR
    BASE --> ITIN
    BASE --> PAY
    LLM --> STRAT
    STRAT --> PROV
    STRAT --> PROMPT
    LLM --> ORCH
    LLM --> PLAN
    ORCH --> FLIGHT
    ORCH --> HOTEL
    ORCH --> CAR
    ORCH --> ITIN
    PLAN --> DET
    PLAN --> ALIAS
```

### Model Invocation Strategy

The system uses a centralized **Model Invocation Strategy** to manage LLM provider and model selection across different use cases. This provides:

- **Use-case-specific configuration** - Different providers/models for planning, intent parsing, summaries, etc.
- **Provider isolation** - Provider-specific settings (capabilities, API keys, JSON mode) are isolated from use cases
- **Explicit overrides** - Same provider/model can have different settings per use case (temperature, max_tokens, timeout)
- **Fallback support** - Automatic fallback to alternative providers if primary fails
- **Prompt repository** - Centralized prompt storage with template substitution
- **Fail-fast validation** - Configuration errors detected at application startup

#### Configuration Files

- **`llm/config/model_strategy.yaml`** - Defines use cases, providers, models, and settings
- **`llm/config/prompts.yaml`** - Stores all prompts with template variables

#### Use Cases

The system defines five LLM use cases:

1. **`planner`** - Main planning LLM for generating execution plans from natural language queries
2. **`intent_parsing`** - Parsing user queries into structured intent formats
3. **`summary_generation`** - Converting structured booking results into natural language summaries
4. **`task_routing`** - Routing ambiguous tasks to appropriate agent tools
5. **`modification`** - Modifying existing itineraries via natural language instructions

Each use case can specify:
- Provider (openai, anthropic, google_genai, groq, etc.)
- Model name (gpt-4o, claude-3-5-sonnet-latest, etc.)
- Prompt reference (links to prompts.yaml)
- Overrides (temperature, max_tokens, timeout, retries, enable_json_mode, etc.)
- Fallback configuration (alternative provider/model if primary fails)

#### Example: Different Settings for Same Provider/Model

```yaml
use_cases:
  planner:
    provider: openai
    model: gpt-4o
    overrides:
      temperature: 0
      enable_json_mode: true
      max_tokens: 4000
      
  summary_generation:
    provider: openai
    model: gpt-4o  # Same provider/model
    overrides:     # But different settings
      temperature: 0.3
      enable_json_mode: false
      max_tokens: 500
```

See `docs/MODEL_INVOCATION_STRATEGY_DESIGN.md` for complete design documentation.

### Specialized Agents

Each agent is a self-contained unit with multiple tools:

| Agent | Location | Tools | Purpose |
|-------|----------|-------|---------|
| **FlightBookingAgent** | `agents/domain/flight_booking_agent.py` | `search_flights`, `compare_flights`, `book_flight` | Flight operations |
| **HotelBookingAgent** | `agents/domain/hotel_booking_agent.py` | `search_hotels`, `compare_hotels`, `book_hotel` | Hotel search & booking |
| **CarRentalAgent** | `agents/domain/car_rental_agent.py` | `search_cars`, `compare_cars`, `book_car` | Car rental operations |
| **ItineraryAgent** | `agents/domain/itinerary_agent.py` | `build_itinerary`, `update_itinerary`, `get_itinerary`, `list_itineraries`, `confirm`, `cancel` | Travel itinerary management |
| **PaymentAgent** | `agents/domain/payment_agent.py` | `process_payment`, `verify_payment` | Payment processing |

### Selection Criteria

Agents automatically select the best option based on criteria passed via `TravelContext`:

| Criteria | Behavior |
|----------|----------|
| `first_available` | Returns first matching option (fastest) |
| `cheapest` | Selects option with lowest price |
| `best_rated` | Selects highest-rated option |

```bash
# Example: Request cheapest options
curl -X POST http://localhost:8000/api/v1/agent/plan \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Flight from NYC to LAX",
    "traveler_id": "user_123",
    "selection_criteria": "cheapest"
  }'
```

### User Preferences (Tiered Loading)

The system uses a **tiered preference loading pattern** for personalized recommendations:

```mermaid
graph TD
    START[User Request] --> LOAD[Load Preference Summary<br/>~50 tokens]
    LOAD --> PROMPT[Include in LLM Prompt]
    PROMPT --> DECISION{LLM Needs<br/>More Details?}
    DECISION -->|90% of requests| DONE[Single LLM Call<br/>~1.6s latency]
    DECISION -->|10% of requests| TOOL[Tool Call:<br/>load_full_preferences]
    TOOL --> DETAILS[Load Full Preferences<br/>~500 tokens]
    DETAILS --> DONE2[Complete Response<br/>~2.7s latency]
    
    style LOAD fill:#e1f5ff
    style TOOL fill:#fff4e1
    style DONE fill:#e8f5e9
    style DONE2 fill:#e8f5e9
```

**Benefits:**
- **90% of requests**: Single LLM call with compact summary
- **10% of requests**: Tool call for detailed preferences
- **Average latency**: ~1.6s (vs ~2.7s for always-load approach)

---

## Web API Reference

### Base URL
```
http://localhost:8000/api/v1
```

### Endpoints

#### Itinerary Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/itineraries` | Create a new draft itinerary |
| `GET` | `/itineraries` | List itineraries (with pagination & filters) |
| `GET` | `/itineraries/{id}` | Get itinerary by ID |
| `PUT` | `/itineraries/{id}` | Update itinerary (with optimistic locking) |
| `DELETE` | `/itineraries/{id}` | Delete a draft itinerary |

#### Status Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/itineraries/{id}/confirm` | Confirm a draft (locks editing) |
| `POST` | `/itineraries/{id}/cancel` | Cancel an itinerary |

#### LLM Operations

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/agent/plan` | Generate travel options from NL query |
| `POST` | `/itineraries/{id}/modify` | Modify itinerary via natural language |

#### User Preferences

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/preferences/{traveler_id}` | Get full preferences |
| `PUT` | `/preferences/{traveler_id}` | Create/update preferences (upsert) |
| `DELETE` | `/preferences/{traveler_id}` | Delete preferences |
| `GET` | `/preferences/{traveler_id}/summary` | Get compact summary (~50 tokens) |

#### System

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check (DB & LLM status) |

### Example: Create and Confirm an Itinerary

```bash
# 1. Create a draft itinerary
curl -X POST http://localhost:8000/api/v1/itineraries \
  -H "Content-Type: application/json" \
  -d '{"traveler_id": "user_123", "original_query": "Trip to Paris"}'

# Response: {"id": "itin-abc123", "status": "draft", "version": 1, ...}

# 2. Add flight booking
curl -X PUT http://localhost:8000/api/v1/itineraries/itin-abc123 \
  -H "Content-Type: application/json" \
  -d '{"version": 1, "flight_data": {"airline": "Air France", "price": 500}}'

# 3. Confirm the itinerary
curl -X POST http://localhost:8000/api/v1/itineraries/itin-abc123/confirm

# Response: {"id": "itin-abc123", "status": "confirmed", ...}
```

### Status Workflow

```mermaid
stateDiagram-v2
    [*] --> draft: Create Itinerary
    draft --> confirmed: confirm()
    draft --> cancelled: cancel()
    confirmed --> cancelled: cancel()
    cancelled --> [*]
    
    note right of draft
        Can be modified
        (add/remove bookings,
        NL updates)
    end note
    
    note right of confirmed
        Locked state
        No modifications allowed
    end note
    
    note right of cancelled
        Terminal state
        Cannot be changed
    end note
```

- **draft**: Can be modified (add/remove bookings, NL updates)
- **confirmed**: Locked, no modifications allowed
- **cancelled**: Terminal state

### Optimistic Locking

Updates require a `version` field to prevent lost updates:

```json
PUT /api/v1/itineraries/{id}
{
  "version": 2,
  "flight_data": {...}
}
```

If the version doesn't match, you'll receive a `409 Conflict` response.

---

## Database Schema

The API uses SQLite with three main tables:

### `itinerary` Table

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT (PK) | UUID identifier (e.g., "itin-abc123") |
| `traveler_id` | TEXT | Traveler identifier |
| `original_query` | TEXT | Original NL query |
| `status` | TEXT | draft, confirmed, cancelled |
| `flight_reservation` | JSON | Flight booking details |
| `hotel_reservation` | JSON | Hotel booking details |
| `car_reservation` | JSON | Car rental details |
| `total_cost` | REAL | Computed total |
| `version` | INTEGER | Optimistic locking version |
| `created_at` | TIMESTAMP | Creation time |
| `updated_at` | TIMESTAMP | Last modification |

### `chat_history` Table

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT (PK) | Message UUID |
| `itinerary_id` | TEXT (FK) | Associated itinerary |
| `role` | TEXT | "user" or "assistant" |
| `content` | TEXT | Message content |
| `created_at` | TIMESTAMP | Message time |

### `user_preferences` Table

| Column | Type | Description |
|--------|------|-------------|
| `traveler_id` | TEXT (PK) | Traveler identifier |
| `flight_preferences` | JSON | Seat type, cabin class, airlines |
| `hotel_preferences` | JSON | Min rating, room type, amenities |
| `car_preferences` | JSON | Car type, features, companies |
| `budget_range` | JSON | Min/max budget, currency |
| `dietary_restrictions` | JSON | List of dietary needs |
| `accessibility_needs` | JSON | List of accessibility requirements |
| `loyalty_programs` | JSON | List of program memberships |
| `past_bookings_summary` | JSON | Aggregated booking stats |
| `created_at` | TIMESTAMP | Creation time |
| `updated_at` | TIMESTAMP | Last modification |

**Filesystem Cache:** Preferences are cached at `data/user_preferences/{traveler_id}.json` for fast tool reads (~5ms).

---

## Project Structure

```
travel-agents/
├── llm/                            # Model Invocation Strategy
│   ├── __init__.py                 # Public API
│   ├── strategy/                   # Strategy implementation
│   │   ├── __init__.py
│   │   ├── model_strategy.py      # Main orchestrator
│   │   ├── use_cases.py           # UseCase enum
│   │   ├── config_loader.py       # YAML config loading
│   │   └── resolver.py            # Config resolution
│   ├── providers/                  # Provider implementations
│   │   ├── __init__.py
│   │   ├── base.py                # Abstract base class
│   │   ├── factory.py             # Provider factory
│   │   ├── openai.py              # OpenAI provider
│   │   ├── anthropic.py           # Anthropic provider
│   │   └── capabilities.py       # Capability detection
│   ├── prompts/                   # Prompt management
│   │   ├── __init__.py
│   │   ├── repository.py          # Prompt loading & caching
│   │   └── template.py            # Template substitution
│   └── config/                     # Configuration files
│       ├── model_strategy.yaml     # Use case & provider config
│       └── prompts.yaml           # Prompt repository
├── agents/
│   ├── __init__.py
│   ├── core/                      # Core agent infrastructure
│   │   ├── __init__.py
│   │   ├── base_agent.py          # Base class for all agents
│   │   ├── llm_provider.py        # Legacy bridge (uses llm/ module)
│   │   ├── memory.py              # Memory/conversation management
│   │   └── router.py              # Legacy router
│   ├── domain/                    # Domain-specific agents
│   │   ├── __init__.py
│   │   ├── flight_booking_agent.py
│   │   ├── hotel_booking_agent.py
│   │   ├── car_rental_agent.py
│   │   ├── itinerary_agent.py    # DB-aware itinerary management
│   │   └── payment_agent.py
│   ├── orchestration/             # Agent coordination
│   │   ├── __init__.py
│   │   ├── orchestrator.py        # Main orchestrator
│   │   └── response_formatter.py  # LLM response formatting
│   └── planning/                  # Planning logic
│       ├── __init__.py
│       ├── planner.py             # Main TravelPlanner
│       ├── deterministic_planner.py  # Fallback planner
│       ├── alias_resolver.py     # City/airport alias resolution
│       └── schemas.py            # ExecutionPlan schemas
├── api/
│   ├── __init__.py
│   ├── config.py                 # Configuration constants
│   ├── context.py                # TravelContext dataclass
│   ├── dependencies.py           # FastAPI DI bindings
│   ├── schemas.py                # Pydantic request/response models
│   ├── routes/                   # Modular FastAPI routers
│   │   ├── __init__.py           # Registers all sub-routers
│   │   ├── health.py             # /health
│   │   ├── search.py             # /search/*
│   │   ├── itineraries.py        # /itineraries/*
│   │   ├── preferences.py        # /preferences/*
│   │   └── agent.py             # /agent/plan, /itineraries/{id}/modify
│   ├── services/                 # Service layer (business logic)
│   │   ├── __init__.py
│   │   ├── itinerary_service.py
│   │   ├── preference_service.py
│   │   ├── search_service.py
│   │   ├── health_service.py
│   │   ├── conversation_service.py
│   │   └── planning_service.py
│   └── utils/                    # Shared helpers
│       ├── __init__.py
│       └── response_utils.py
├── database/
│   ├── __init__.py
│   ├── models.py                 # SQLModel ORM (Itinerary, UserPreferences, ChatHistory)
│   ├── connection.py             # DB connection & table creation
│   └── repository.py             # CRUD + preference cache sync
├── tools/
│   ├── search_tools.py           # Flight, hotel, car search tools
│   ├── preference_tools.py       # load_full_preferences tool
│   └── payment_tool.py           # Payment processing tool
├── data/
│   ├── flights.py                # Mock flight data
│   ├── hotels.py                 # Mock hotel data
│   ├── cars.py                   # Mock car data
│   ├── city_airport_aliases.json  # City/airport alias mapping
│   └── user_preferences/         # Filesystem cache for preferences
│       ├── user_123.json         # Sample preferences
│       └── user_456.json         # Sample preferences
├── docs/                         # Architecture documentation
│   ├── AGENTIC_REFACTOR_PLAN.md
│   ├── ARCHITECTURE_REUSE_PROMPT.md
│   ├── FEATURE_VERIFICATION.md
│   ├── LOGGING.md
│   ├── PLAN_TRIP_API_FLOW.md
│   ├── PLANNER_DAG_DESIGN.md
│   ├── MODEL_INVOCATION_STRATEGY_DESIGN.md  # Model Invocation Strategy design
│   ├── PLANNER_FALLBACK_ANALYSIS.md
│   ├── PLANNER_REFACTOR.md
│   ├── REUSING_PROJECT_STRUCTURE.md
│   ├── USER_PREFERENCES_PLAN.md
│   └── WebApp-Impl-Plan*.md
├── tests/
│   ├── conftest.py               # Pytest fixtures
│   ├── test_api.py               # API integration tests
│   ├── test_agents/               # Agent unit tests
│   │   ├── test_flight_agent.py
│   │   ├── test_hotel_agent.py
│   │   ├── test_car_agent.py
│   │   ├── test_itinerary_agent.py
│   │   └── test_payment_agent.py
│   ├── test_core/                 # Core component tests
│   │   ├── test_orchestrator.py
│   │   └── test_planner.py
│   ├── test_integration/          # End-to-end flow tests
│   │   └── test_flows.py
│   └── test_services/            # Service layer unit tests
│       ├── conftest.py
│       ├── test_itinerary_service.py
│       ├── test_preference_service.py
│       ├── test_search_service.py
│       ├── test_health_service.py
│       ├── test_conversation_service.py
│       └── test_planning_service.py
├── utils/
│   ├── __init__.py
│   └── logger.py                  # Comprehensive logging system
├── mcp/
│   └── server.py                  # MCP Server implementation
├── main_web.py                    # FastAPI entry point
├── requirements.txt              # Python dependencies
├── pyrightconfig.json            # Type checking config
└── README.md                      # This file
```

---

## Configuration

### Model Invocation Strategy

The system uses a centralized Model Invocation Strategy for LLM configuration. Configuration is defined in YAML files:

- **`llm/config/model_strategy.yaml`** - Use case configurations, provider settings, and defaults
- **`llm/config/prompts.yaml`** - Centralized prompt repository with templates

#### Use Cases

The system supports the following LLM use cases, each with its own provider/model configuration:

| Use Case | Description | Default Provider/Model |
|----------|-------------|----------------------|
| `planner` | Main planning LLM for generating execution plans | OpenAI `gpt-4o` |
| `intent_parsing` | Parsing user queries into structured intents | OpenAI `gpt-4o-mini` |
| `summary_generation` | Generating natural language summaries | OpenAI `gpt-4o` |
| `task_routing` | Routing ambiguous tasks to appropriate tools | OpenAI `gpt-3.5-turbo` |
| `modification` | Modifying itineraries via natural language | OpenAI `gpt-4o` |

Each use case can have:
- **Provider and model selection** - Different providers/models per use case
- **Explicit overrides** - Temperature, max_tokens, timeout, retries, etc.
- **Fallback configuration** - Automatic fallback if primary provider fails
- **Prompt reference** - Links to prompts in the prompt repository

#### Example Configuration

```yaml
use_cases:
  planner:
    provider: openai
    model: gpt-4o
    prompt: planner_base
    overrides:
      temperature: 0
      enable_json_mode: true
      max_tokens: 4000
      timeout: 30
    fallback:
      provider: anthropic
      model: claude-3-5-sonnet-latest
      overrides:
        temperature: 0
        enable_json_mode: true
```

> **Security Note**: API keys are never stored in YAML files. The configuration references environment variable names (e.g., `OPENAI_API_KEY`), and values are loaded from the environment at runtime.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | - | OpenAI API key (required for OpenAI use cases) |
| `ANTHROPIC_API_KEY` | - | Anthropic API key (required for Anthropic use cases) |
| `GOOGLE_API_KEY` | - | Google API key (required for Google use cases) |
| `GROQ_API_KEY` | - | Groq API key (required for Groq use cases) |
| `LLM_MODEL` | - | **⚠️ Deprecated** - Use `llm/config/model_strategy.yaml` instead. This bypasses centralized configuration. |
| `LLM_PROVIDER` | - | **⚠️ Deprecated** - Use `llm/config/model_strategy.yaml` instead. This bypasses centralized configuration. |
| `LLM_TEMPERATURE` | - | **⚠️ Deprecated** - Use `llm/config/model_strategy.yaml` instead. Temperature is configured per use case. |
| `LLM_TIMEOUT` | `60` | Timeout for LLM operations (seconds) |
| `PORT` | `8000` | API server port |
| `HOST` | `0.0.0.0` | API server host |
| `ALLOWED_ORIGINS` | `http://localhost:3000,http://localhost:5173` | CORS origins |
| `DEBUG` | - | Enable debug mode (shows exception details) |
| `LOG_LEVEL` | `INFO` | Logging level |
| `PREFERENCE_LOADING_MODE` | `summary` | Preference loading: `summary` (fast) or `tool_binding` (LLM can fetch details) |

### Example `.env` file

```env
# API Keys (required based on providers in model_strategy.yaml)
OPENAI_API_KEY=sk-your-key-here
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Application Settings
LOG_LEVEL=DEBUG
PORT=8000
```

### Using the Model Invocation Strategy

```python
from llm import ModelInvocationStrategy, UseCase

# Initialize strategy (loads config at import time)
strategy = ModelInvocationStrategy()

# Get LLM for a specific use case
llm = strategy.get_llm_for_use_case(UseCase.PLANNER)

# Get formatted prompt for a use case
prompt = strategy.get_prompt_for_use_case(
    UseCase.PLANNER,
    query="Book a flight from NYC to LON",
    preference_summary="Prefers: economy class, aisle seat"
)

# Use the LLM
response = llm.invoke(prompt)
```

---

## Testing

Run the test suites:

```bash
# Run API tests
python -m pytest tests/test_api.py -v

# Run service layer tests
python -m pytest tests/test_services/ -v

# Run agent tests
python -m pytest tests/test_agents/ -v

# Run core component tests
python -m pytest tests/test_core/ -v

# Run integration tests
python -m pytest tests/test_integration/ -v

# Run everything
python -m pytest tests/ -v

# Run with coverage (API + services)
python -m pytest tests/test_api.py tests/test_services/ --cov=api --cov=api/services --cov-report=html
```

Test coverage includes:
- API flows (CRUD, status transitions, optimistic locking, pagination/filtering)
- LLM operations (with mocking)
- Service layer business logic (itineraries, preferences, search, health, conversation, planning)
- Agent unit tests (all domain agents)
- Core component tests (orchestrator, planner)
- Integration tests (full workflows)

---

## Example Usage

### CLI Usage

```python
from agents.orchestration import Orchestrator
from llm import ModelInvocationStrategy, UseCase

# Initialize orchestrator (uses Model Invocation Strategy internally)
orch = Orchestrator()

# The orchestrator automatically uses the configured LLM for each use case
# You can also manually get LLMs for specific use cases:
strategy = ModelInvocationStrategy()
planner_llm = strategy.get_llm_for_use_case(UseCase.PLANNER)

# Execute user intent
intent = {
    'needs': ['flight', 'hotel'],
    'from': 'NYC',
    'to': 'LON',
    'date': '2025-08-12'
}

results = orch.run_intent(intent)
```

### Using Model Invocation Strategy Directly

```python
from llm import ModelInvocationStrategy, UseCase

strategy = ModelInvocationStrategy()

# Get LLM for a specific use case (configured in model_strategy.yaml)
llm = strategy.get_llm_for_use_case(UseCase.PLANNER)

# Get formatted prompt with template variables
prompt = strategy.get_prompt_for_use_case(
    UseCase.PLANNER,
    query="Book a flight from NYC to LON",
    preference_summary="Prefers: economy class, aisle seat"
)

# Invoke LLM
response = llm.invoke(prompt)
structured_response = llm.invoke_structured(prompt, response_format={"status": "string"})
```

### API Usage (Python)

```python
import httpx

BASE_URL = "http://localhost:8000/api/v1"

# Create itinerary
response = httpx.post(f"{BASE_URL}/itineraries", json={
    "traveler_id": "user_123",
    "original_query": "Weekend trip to Paris"
})
itinerary = response.json()

# Add flight
httpx.put(f"{BASE_URL}/itineraries/{itinerary['id']}", json={
    "version": 1,
    "flight_data": {"airline": "Air France", "price": 450}
})

# Confirm
httpx.post(f"{BASE_URL}/itineraries/{itinerary['id']}/confirm")
```

### User Preferences API

```bash
# 1. Create/update user preferences
curl -X PUT http://localhost:8000/api/v1/preferences/user_123 \
  -H "Content-Type: application/json" \
  -d '{
    "flight_preferences": {
      "seat_type": "aisle",
      "cabin_class": "economy_plus",
      "preferred_airlines": ["Delta", "United"]
    },
    "hotel_preferences": {
      "min_rating": 4,
      "amenities": ["wifi", "gym"]
    },
    "budget_range": {
      "min": 1000,
      "max": 3000,
      "currency": "USD"
    },
    "dietary_restrictions": ["vegetarian"],
    "loyalty_programs": [
      {"program": "Delta SkyMiles", "number": "123456789", "tier": "Gold"}
    ]
  }'

# 2. Get preference summary (fast, for prompts)
curl http://localhost:8000/api/v1/preferences/user_123/summary
# Response: {"traveler_id": "user_123", "summary": "Prefers: flights: economy_plus, aisle seat; hotels: 4+ star; budget: USD 1000-3000"}

# 3. Get full preferences
curl http://localhost:8000/api/v1/preferences/user_123

# 4. Plan trip (preferences are automatically loaded)
curl -X POST http://localhost:8000/api/v1/agent/plan \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Plan a trip from NYC to LAX next Friday",
    "traveler_id": "user_123"
  }'
# Response includes: "preference_summary": "Prefers: flights: economy_plus, aisle seat; ..."
```

---

## Domain Conventions

### Naming

The codebase uses **Reservation** terminology for booked items:

| Field | Description |
|-------|-------------|
| `flight_reservation` | Booked flight details |
| `hotel_reservation` | Booked hotel details |
| `car_reservation` | Booked car rental details |
| `traveler_id` | Identifier for the person booking |

### Error Handling

Domain exceptions are raised by Orchestrator/Agents and translated to HTTP by routes:

| Domain Exception | HTTP Status | Description |
|------------------|-------------|-------------|
| `ItineraryNotFoundError` | 404 | Itinerary doesn't exist |
| `VersionConflictError` | 409 | Optimistic locking conflict |
| `InvalidStatusTransitionError` | 400 | Invalid status change |
| `LLMUnavailableError` | 503 | LLM service not available |
| `PreferencesNotFoundError` | 404 | User preferences not found |

---

## Planning Architecture

### Execution Plan Structure

The planner generates `ExecutionPlan` objects with the following structure:

```mermaid
graph TD
    PLAN[ExecutionPlan] --> STATUS[status:<br/>executable/needs_clarification]
    PLAN --> TASKS[tasks: List[Task]]
    PLAN --> METADATA[plan_metadata:<br/>PlanMetadata]
    PLAN --> MISSING[missing_info:<br/>List[MissingInfo]]
    
    TASK[Task] --> ID[task_id: str]
    TASK --> AGENT[agent: str<br/>FlightBookingAgent]
    TASK --> ACTION[action: str<br/>search_flights]
    TASK --> PARAMS[params: Dict]
    TASK --> DEPS[dependencies: List[str]]
    TASK --> SCHEMA[output_schema: Dict]
    TASK --> PARALLEL[parallelizable: bool]
    
    TASKS --> TASK
```

### Planning Flow

```mermaid
flowchart TD
    START[NL Query] --> PLANNER[TravelPlanner]
    
    PLANNER --> LLM_CHECK{LLM<br/>Available?}
    
    LLM_CHECK -->|Yes| LLM_PLAN[LLM-based Planning]
    LLM_CHECK -->|No| DET_PLAN[Deterministic Planning]
    
    LLM_PLAN --> PARSE[Parse NL Query]
    PARSE --> EXTRACT[Extract Intent]
    EXTRACT --> BUILD[Build ExecutionPlan]
    
    DET_PLAN --> NORMALIZE[Normalize Intent<br/>Alias Resolution]
    NORMALIZE --> VALIDATE[Validate Required Fields]
    VALIDATE --> MISSING_CHECK{Missing<br/>Fields?}
    
    MISSING_CHECK -->|Yes| CLARIFY[Return needs_clarification<br/>with missing_info]
    MISSING_CHECK -->|No| BUILD
    
    BUILD --> DAG[Create Task DAG<br/>with dependencies]
    DAG --> EXECUTABLE[Return ExecutionPlan<br/>status=executable]
    
    CLARIFY --> END1[Return to Client]
    EXECUTABLE --> ORCH[Orchestrator.execute_plan]
    
    style LLM_PLAN fill:#e1f5ff
    style DET_PLAN fill:#fff4e1
    style EXECUTABLE fill:#e8f5e9
    style CLARIFY fill:#ffebee
```

---

## Logging

The system includes comprehensive logging with:
- **Request ID tracking** - Every request gets a unique ID for correlation
- **Structured logging** - JSON-formatted logs with context
- **Multiple outputs** - Console and file logging
- **Performance tracking** - Request duration and method timing
- **Session context** - Automatic context propagation

Logs are written to:
- Console (stdout) - Human-readable format
- `logs/travel_booking.log` - File with full details

See `docs/LOGGING.md` for detailed logging documentation.

---

## License

This project is provided as-is for educational and demonstration purposes.
