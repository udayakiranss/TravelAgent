# Implementation Plan - Web App Conversion

This plan outlines the design to convert the existing CLI/Script-based Travel Agent application into a full-stack Web Application with persistent storage.

## User Review Required

> [!IMPORTANT]
> **Frontend Technology Choice**: I am proposing **React with Vite** and **TailwindCSS** for the frontend to ensure a modern, responsive, and "premium" feel. Please confirm if you have a different preference.

> [!NOTE]
> **Authentication**: The current design assumes a single-user system or simple "traveler name" identification without secure login. Let me know if full authentication is required.

## Proposed Architecture

### Backend (FastAPI)

- **Framework**: FastAPI for high-performance, async support (good for LLM operations), and automatic Swagger docs.
- **Database**: SQLite (as requested) using **SQLModel** (combines SQLAlchemy + Pydantic) for easy ORM and validation.
- **Structure**:
  - `api/`: New directory for web API endpoints.
  - `models/`: Database models.
  - `database.py`: DB connection management.

### Frontend (React + Vite) (in `/frontend` folder)

- **Framework**: React 18+ with Vite for fast development.
- **Styling**: TailwindCSS for modern, flexible styling.
- **Features**:
  - **Dashboard**: List all existing itineraries.
  - **Itinerary Builder**: Form to input requirements (Natural Language or Structured).
  - **Itinerary Details**: View to see flight/hotel/car details and "Edit" individual components.
  - **Draft Mode**: Ability to save an itinerary as "Draft" and resume later.

### Database Schema (SQLite)

We will introduce a `itineraries.db` SQLite file.

**Table: `itinerary`**

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer (PK) | Auto-incrementing ID |
| `uid` | String | Unique Identifier (e.g., ITIN-123) |
| `traveler_id` | String | Identifier for the traveler |
| `status` | String | `draft`, `confirmed`, `completed` |
| `flight_data` | JSON | Flight booking details |
| `hotel_data` | JSON | Hotel booking details |
| `car_data` | JSON | Car rental details |
| `created_at` | DateTime | Timestamp |
| `updated_at` | DateTime | Timestamp |

*Note: We are using a Partitioned JSON strategy (Option 3). This partitions data by agent (Flight vs Hotel) to prevent overwrite conflicts, while maintaining schema flexibility.*

## Proposed Changes

### [Backend] API Layer

#### [NEW] [main_web.py](file:///Users/udaykiranss/Technical/AgenticAI/TravelBooking/travel-agents/main_web.py)

Entry point for the FastAPI application.

#### [NEW] [api/routes.py](file:///Users/udaykiranss/Technical/AgenticAI/TravelBooking/travel-agents/api/routes.py)

- `POST /itineraries/`: Create new draft.
  - **Request**: `{"traveler_id": "user_123"}`
  - **Response**: `{"id": 1, "uid": "ITIN-1", "status": "draft", "data": {}}`

- `GET /itineraries/`: List all.
  - **Response**: `[{"id": 1, "uid": "ITIN-1", "traveler_id": "user_123", ...}]`

- `GET /itineraries/{id}`: Get details.
  - **Response**: `{"id": 1, "data": {"flight": {...}, "hotel": {...}}, ...}`

- `PUT /itineraries/{id}`: Update itinerary manually (add bookings).
  - **Request**: `{"data": {"flight": {"from": "NYC"}}}`
  - **Response**: `{"id": 1, "status": "draft", "data": {"flight": {"from": "NYC"}}}`

- `POST /itineraries/{id}/modify`: **[NEW]** Accept natural language instruction to modify the itinerary.
  - **Request**: `{"user_instruction": "Change the flight to next Monday", "user_id": "user_123"}`
  - **Process**: LLM reads current DB state -> Agent searches new flight -> DB Updated.
  - **Response**: `{"success": true, "updated_itinerary": {...}, "message": "Changed flight to 2025-04-08"}`

- `POST /agent/plan`: Endpoint to trigger the LLM Orchestrator to generate options.
  - **Request**: `{"query": "Plan a weekend trip to Paris from London next Friday", "user_id": "123"}`
  - **Response**: `{"flight_options": [...], "hotel_options": [...], "summary": "..."}`
  - **Example Usage**:
    - **Request**: `{"query": "Plan a weekend trip to Paris from London next Friday", "user_id": "123"}`
    - **Process**: Orchestrator parses intent -> Calls Flight/Hotel Agents -> Aggregates results.
    - **Response**: Returns a JSON object with `flight_options`, `hotel_options`, and a `summary`. The Frontend uses this to display "Recommended Options" cards. User selection then calls `POST /itineraries` to save the draft.

### Natural Language Modification Design (Hybrid Approach)

To support "changing flights/hotels" via text with high reliability:

1. **State Source (Truth)**: We will **NOT** rely on LLM memory for the itinerary state. The API will fetch the latest `Itinerary` JSON from SQLite.
2. **Conversational History**: We will use `LangChain RunnableWithMessageHistory` to track *chat* context (clarifications, previous questions).
3. **Prompt Construction**:
    - **System**: "You are a travel agent helper..."
    - **Context Injection**: "Current Itinerary State: {json_from_db}" (injected dynamically every turn).
    - **Chat History**: "{recent_chat_messages}"
    - **User Input**: "{user_query}"
4. **Execution Flow**:
    - User: "Change flight to tomorrow"
    - LLM (sees current flight is 2025-04-01): Calls `FlightBookingAgent.search(date='2025-04-02')`.
    - Tools execute.
    - **State Update**: Result is saved back to `Itinerary.data` in SQLite.

### Workflow: Search to Save

This design separates "Searching" from "Saving" to avoid cluttering the database with abandoned queries.

1. **Step 1: Search (Ephemeral)**
    - User asks: "Trips to Paris"
    - Frontend calls `POST /agent/plan`
    - Backend returns 3 flight options (in memory only).
2. **Step 2: User Decision**
    - User clicks "Select Option A" on the UI.
3. **Step 3: Save (Persistent)**
    - Frontend calls `POST /itineraries/` with the data from Option A.
    - Backend saves this as a new Draft Itinerary in SQLite (ID: 5).
    - Now the user can "Modify" Itinerary #5 later.

### [Backend] Database

#### [NEW] [database/models.py](file:///Users/udaykiranss/Technical/AgenticAI/TravelBooking/travel-agents/database/models.py)

SQLModel classes for `Itinerary`.

#### [NEW] [database/connection.py](file:///Users/udaykiranss/Technical/AgenticAI/TravelBooking/travel-agents/database/connection.py)

SQLite database setup.

### [Backend] Agent Integration

#### [MODIFY] [agents/itinerary_agent.py](file:///Users/udaykiranss/Technical/AgenticAI/TravelBooking/travel-agents/agents/itinerary_agent.py)

- Refactor `ItineraryAgent` to accept a `db_session` or uses a Repository pattern to save to SQLite instead of `_ITINERARIES` global dict.

### [Frontend] UI

#### [NEW] [frontend/](file:///Users/udaykiranss/Technical/AgenticAI/TravelBooking/travel-agents/frontend/)

New directory for the React application.

- `src/components/ItineraryList.jsx`
- `src/components/Itinerarybuilder.jsx`
- `src/components/ItineraryDisplay.jsx`

## Verification Plan

### Automated Tests

- **Backend Tests**:
  - Create `tests/test_api.py` using `TestClient` from FastAPI.
  - Verify CRUD operations on Itineraries against a test SQLite DB.
- **Agent Integration**:
  - Verify `ItineraryAgent` correctly reads/writes to DB.

### Manual Verification

1. Start Backend: `uvicorn main_web:app --reload`
2. Start Frontend: `npm run dev`
3. Open Web Browser:
    - Create a new Itinerary (Draft).
    - Add a Flight (simulate agent response).
    - Reload page (Verify persistence).
    - Edit the Itinerary (change status).
