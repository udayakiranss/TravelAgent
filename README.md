Agentic Travel Booking System with LLM Integration
====================================================

This system demonstrates a multi-agent architecture for travel booking with:
- **LLM-based intelligent planning** - Uses foundation models to select appropriate agents
- **Specialized agents** - Each agent handles a specific domain with multiple tools
- **Flexible LLM integration** - Supports any foundation model (OpenAI, Anthropic, Google, etc.)
- **Agent orchestration** - Coordinates multiple agents to fulfill complex user intents
- **REST API** - FastAPI-based web API for building frontend applications
- **Persistent Storage** - SQLite database for itinerary management

## Quick Start

### Option 1: Command Line Interface (CLI)

```bash
# Setup
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Set API key (optional, for LLM-based planning)
export OPENAI_API_KEY="your-api-key-here"

# Run CLI demo
python main.py
```

### Option 2: Web API

```bash
# Start the API server
python -m uvicorn main_web:app --reload --port 8000

# API Documentation
# Swagger UI: http://localhost:8000/docs
# ReDoc: http://localhost:8000/redoc
```

---

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

4. **Web API** (`api/`, `main_web.py`)
   - FastAPI-based REST API
   - Swagger/OpenAPI documentation
   - SQLite persistence layer

### Specialized Agents

Each agent is a self-contained unit with multiple tools:

| Agent | Tools | Purpose |
|-------|-------|---------|
| **FlightBookingAgent** | `search_flights`, `compare_flights`, `book_flight` | Flight operations |
| **HotelBookingAgent** | `search_hotels`, `compare_hotels`, `book_hotel` | Hotel search & booking |
| **CarRentalAgent** | `search_cars`, `compare_cars`, `book_car` | Car rental operations |
| **ItineraryAgent** | `build_itinerary`, `update_itinerary`, `get_itinerary`, `list_itineraries` | Travel itinerary management |
| **PaymentAgent** | `process_payment`, `verify_payment` | Payment processing |

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

```
    ┌─────────┐    confirm    ┌───────────┐
    │  draft  │──────────────▶│ confirmed │
    └────┬────┘               └─────┬─────┘
         │                          │
         │ cancel                   │ cancel
         ▼                          ▼
    ┌───────────┐             ┌───────────┐
    │ cancelled │◀────────────│ cancelled │
    └───────────┘             └───────────┘
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

The API uses SQLite with two tables:

### `itinerary` Table
| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT (PK) | UUID identifier (e.g., "itin-abc123") |
| `traveler_id` | TEXT | Traveler identifier |
| `original_query` | TEXT | Original NL query |
| `status` | TEXT | draft, confirmed, cancelled |
| `flight_data` | JSON | Flight booking details |
| `hotel_data` | JSON | Hotel booking details |
| `car_data` | JSON | Car rental details |
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

---

## Project Structure

```
travel-agents/
├── agents/
│   ├── base_agent.py           # Base class for all agents
│   ├── llm_provider.py         # LLM integration layer
│   ├── planner.py              # LLM-based planning
│   ├── orchestrator.py         # Agent coordination
│   ├── flight_booking_agent.py
│   ├── hotel_booking_agent.py
│   ├── car_rental_agent.py
│   ├── itinerary_agent.py      # Updated with DB support
│   ├── payment_agent.py
│   ├── memory.py               # Memory management
│   └── router.py               # Legacy router
├── api/                        # NEW: Web API
│   ├── __init__.py
│   ├── routes.py               # API endpoints
│   ├── schemas.py              # Pydantic models
│   └── dependencies.py         # FastAPI dependencies
├── database/                   # NEW: Persistence layer
│   ├── __init__.py
│   ├── models.py               # SQLModel ORM classes
│   ├── connection.py           # DB connection
│   └── repository.py           # CRUD operations
├── data/                       # Mock data (flights, hotels, cars)
├── tests/
│   ├── test_api.py             # NEW: API tests (23 tests)
│   └── ...
├── main.py                     # CLI demo runner
├── main_web.py                 # NEW: FastAPI entry point
├── requirements.txt
└── README.md
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | - | OpenAI API key (required for LLM features) |
| `LLM_MODEL` | `gpt-4o` | Model name |
| `LLM_PROVIDER` | `openai` | Model provider |
| `LLM_TIMEOUT` | `60` | Timeout for LLM operations (seconds) |
| `PORT` | `8000` | API server port |
| `HOST` | `0.0.0.0` | API server host |
| `ALLOWED_ORIGINS` | `http://localhost:3000,http://localhost:5173` | CORS origins |
| `DEBUG` | - | Enable debug mode (shows exception details) |
| `LOG_LEVEL` | `INFO` | Logging level |

### Example `.env` file

```env
OPENAI_API_KEY=sk-your-key-here
LLM_MODEL=gpt-4o
LLM_PROVIDER=openai
LOG_LEVEL=DEBUG
```

---

## Testing

Run the API test suite:

```bash
# Run all API tests
python -m pytest tests/test_api.py -v

# Run specific test class
python -m pytest tests/test_api.py::TestItineraryCRUD -v

# Run with coverage
python -m pytest tests/test_api.py --cov=api --cov-report=html
```

Test coverage includes:
- CRUD operations (create, read, update, delete)
- Status transitions (draft → confirmed → cancelled)
- Optimistic locking (version conflicts)
- Pagination and filtering
- LLM operations (with mocking)
- Integration tests (full workflows)

---

## Example Usage

### CLI Usage

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

---

## Notes

- The system works **with or without LLM** - falls back to rule-based planning if LLM is unavailable
- Each agent can use LLM internally for routing ambiguous tasks
- All agents follow the same `BaseAgent` interface for consistency
- Tools are implemented using LangChain's `@tool` decorator for compatibility
- The API uses optimistic locking to prevent concurrent update conflicts
- Itineraries are persisted to SQLite (file: `itineraries.db`)
