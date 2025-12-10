# Implementation Plan - Web App Conversion (v2)

This plan outlines the design to convert the existing CLI/Script-based Travel Agent application into a full-stack Web Application with persistent storage.

> **Revision Notes**: This version incorporates improvements from the design review including API versioning, optimistic locking, chat history storage, error handling standards, and LLM safeguards.

## User Review Required

> [!IMPORTANT]
> **Frontend Technology Choice**: I am proposing **React with Vite** and **TailwindCSS** for the frontend to ensure a modern, responsive, and "premium" feel. Please confirm if you have a different preference.

> [!NOTE]
> **Authentication**: The current design assumes a single-user system or simple "traveler name" identification without secure login. Let me know if full authentication is required.

---

## Proposed Architecture

```
┌─────────────────┐     ┌─────────────────┐
│   CLI (main.py) │     │  FastAPI (api/) │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     ▼
         ┌───────────────────────┐
         │  Orchestrator Layer   │
         │   (agents/...)        │
         └───────────┬───────────┘
                     ▼
         ┌───────────────────────┐
         │   SQLite Database     │
         │   (data/travel.db)    │
         └───────────────────────┘
```

### Backend (FastAPI)

- **Framework**: FastAPI for high-performance, async support (good for LLM operations), and automatic Swagger docs.
- **Database**: SQLite (as requested) using **SQLModel** (combines SQLAlchemy + Pydantic) for easy ORM and validation.
- **Structure**:
  - `api/`: New directory for web API endpoints.
  - `database/`: Database models and connection.
  - `schemas/`: Pydantic request/response models.

### Frontend (React + Vite) (in `/frontend` folder)

- **Framework**: React 18+ with Vite for fast development.
- **Styling**: TailwindCSS for modern, flexible styling.
- **State Management**: React Query (server state) + Zustand (UI state).
- **Features**:
  - **Dashboard**: List all existing itineraries with filtering/pagination.
  - **Itinerary Builder**: Form to input requirements (Natural Language or Structured).
  - **Itinerary Details**: View to see flight/hotel/car details and "Edit" individual components.
  - **Chat Interface**: Natural language modification with conversation history.
  - **Draft Mode**: Ability to save an itinerary as "Draft" and resume later.

---

## Database Schema (SQLite)

We will introduce a `itineraries.db` SQLite file with two tables.

### Table: `itinerary`

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT (PK) | UUID identifier (e.g., "itin-abc123") |
| `traveler_id` | TEXT (INDEX) | Identifier for the traveler |
| `original_query` | TEXT | Original NL query that created this itinerary |
| `status` | TEXT (INDEX) | `draft`, `confirmed`, `cancelled` |
| `flight_data` | JSON | Flight booking details |
| `hotel_data` | JSON | Hotel booking details |
| `car_data` | JSON | Car rental details |
| `total_cost` | REAL | Computed total cost (persisted) |
| `version` | INTEGER | Optimistic locking version number |
| `created_at` | TIMESTAMP | Creation timestamp |
| `updated_at` | TIMESTAMP | Last modification timestamp |
| `cancelled_at` | TIMESTAMP | Cancellation timestamp (nullable) |

### Table: `chat_history`

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT (PK) | UUID |
| `itinerary_id` | TEXT (FK, INDEX) | Links to itinerary |
| `role` | TEXT | "user" or "assistant" |
| `content` | TEXT | Message content |
| `created_at` | TIMESTAMP | Message timestamp |

*Note: We are using a Partitioned JSON strategy. This partitions data by agent (Flight vs Hotel) to prevent overwrite conflicts, while maintaining schema flexibility.*

### SQL Schema

```sql
CREATE TABLE itinerary (
    id TEXT PRIMARY KEY,
    traveler_id TEXT NOT NULL,
    original_query TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    flight_data JSON,
    hotel_data JSON,
    car_data JSON,
    total_cost REAL DEFAULT 0,
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    cancelled_at TIMESTAMP
);

CREATE INDEX idx_itinerary_traveler ON itinerary(traveler_id);
CREATE INDEX idx_itinerary_status ON itinerary(status);

CREATE TABLE chat_history (
    id TEXT PRIMARY KEY,
    itinerary_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (itinerary_id) REFERENCES itinerary(id) ON DELETE CASCADE
);

CREATE INDEX idx_chat_itinerary ON chat_history(itinerary_id);
```

---

## API Endpoints

All endpoints are prefixed with `/api/v1` for versioning.

### Core CRUD Operations

#### `POST /api/v1/itineraries`
Create a new draft itinerary.

**Request:**
```json
{
  "traveler_id": "user_123",
  "original_query": "Plan a weekend trip to Paris"
}
```

**Response (201):**
```json
{
  "id": "itin-abc123",
  "traveler_id": "user_123",
  "status": "draft",
  "total_cost": 0,
  "version": 1,
  "created_at": "2025-12-06T10:30:00Z"
}
```

#### `GET /api/v1/itineraries`
List itineraries with pagination and filtering.

**Query Parameters:**
- `status` - Filter by status (draft, confirmed, cancelled)
- `traveler_id` - Filter by traveler
- `page` - Page number (default: 1)
- `limit` - Items per page (default: 20, max: 100)

**Response (200):**
```json
{
  "items": [
    {"id": "itin-abc123", "status": "draft", "total_cost": 1425, ...}
  ],
  "total": 15,
  "page": 1,
  "limit": 20,
  "has_more": false
}
```

#### `GET /api/v1/itineraries/{id}`
Get itinerary details by ID.

**Response (200):**
```json
{
  "id": "itin-abc123",
  "traveler_id": "user_123",
  "original_query": "Plan a weekend trip to Paris",
  "status": "draft",
  "flight_data": {"airline": "Air France", "price": 450},
  "hotel_data": {"name": "Le Marais Hotel", "price": 200},
  "car_data": null,
  "total_cost": 650,
  "version": 2,
  "created_at": "2025-12-06T10:30:00Z",
  "updated_at": "2025-12-06T11:00:00Z"
}
```

#### `PUT /api/v1/itineraries/{id}`
Update itinerary (with optimistic locking).

**Request:**
```json
{
  "version": 2,
  "flight_data": {"airline": "British Airways", "price": 380},
  "hotel_data": {"name": "Le Marais Hotel", "price": 200}
}
```

**Response (200):**
```json
{
  "id": "itin-abc123",
  "status": "draft",
  "version": 3,
  "total_cost": 580,
  "updated_at": "2025-12-06T12:00:00Z"
}
```

**Response (409 - Version Conflict):**
```json
{
  "error": "VERSION_CONFLICT",
  "message": "Itinerary was modified by another request. Expected version 2, found 3.",
  "status_code": 409,
  "current_version": 3
}
```

---

### Status Management

#### `POST /api/v1/itineraries/{id}/confirm`
Confirm a draft itinerary (locks from further edits).

**Response (200):**
```json
{
  "id": "itin-abc123",
  "status": "confirmed",
  "message": "Itinerary confirmed successfully"
}
```

#### `POST /api/v1/itineraries/{id}/cancel`
Cancel an itinerary (draft or confirmed).

**Response (200):**
```json
{
  "id": "itin-abc123",
  "status": "cancelled",
  "cancelled_at": "2025-12-06T14:00:00Z"
}
```

#### `DELETE /api/v1/itineraries/{id}`
Permanently delete a draft itinerary.

**Response (204):** No content

**Response (400):** Cannot delete confirmed/cancelled itineraries.

---

### LLM Operations

#### `POST /api/v1/agent/plan`
Trigger the LLM Orchestrator to generate options (ephemeral, not saved).

**Request:**
```json
{
  "query": "Plan a weekend trip to Paris from London next Friday",
  "traveler_id": "user_123"
}
```

**Response (200):**
```json
{
  "flight_options": [
    {"flight_id": "FL-001", "airline": "Air France", "price": 450},
    {"flight_id": "FL-002", "airline": "British Airways", "price": 380}
  ],
  "hotel_options": [
    {"hotel_id": "HT-001", "name": "Le Marais Hotel", "price": 200}
  ],
  "car_options": [],
  "summary": "Found 2 flights and 1 hotel for your Paris trip."
}
```

#### `POST /api/v1/itineraries/{id}/modify`
Accept natural language instruction to modify the itinerary.

**Request:**
```json
{
  "instruction": "Change the flight to next Monday",
  "traveler_id": "user_123"
}
```

**Response (200):**
```json
{
  "success": true,
  "updated_itinerary": {
    "id": "itin-abc123",
    "flight_data": {"airline": "Air France", "date": "2025-04-08", "price": 420},
    "version": 4
  },
  "message": "Changed flight to Monday, April 8th. New price: $420.",
  "partial": false
}
```

**Response (200 - Partial/Timeout):**
```json
{
  "success": true,
  "partial": true,
  "message": "Request timed out. Flight was updated but hotel search incomplete.",
  "updated_itinerary": {...}
}
```

---

### System Endpoints

#### `GET /api/v1/health`
Health check endpoint.

**Response (200):**
```json
{
  "status": "healthy",
  "database": "connected",
  "llm": "available",
  "timestamp": "2025-12-06T10:30:00Z"
}
```

---

## Error Response Format

All errors follow a consistent format:

```json
{
  "error": "ERROR_CODE",
  "message": "Human-readable description",
  "status_code": 404,
  "timestamp": "2025-12-06T10:30:00Z",
  "details": {}
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `ITINERARY_NOT_FOUND` | 404 | Itinerary ID doesn't exist |
| `VERSION_CONFLICT` | 409 | Optimistic locking conflict |
| `INVALID_STATUS_TRANSITION` | 400 | Invalid status change (e.g., confirmed → draft) |
| `CANNOT_MODIFY_CONFIRMED` | 400 | Trying to edit a confirmed itinerary |
| `LLM_TIMEOUT` | 504 | LLM operation exceeded timeout |
| `VALIDATION_ERROR` | 422 | Request validation failed |

---

## Status Workflow

```
                        ┌───────────┐
         ┌─────────────▶│ confirmed │
         │   confirm    └─────┬─────┘
         │                    │
    ┌────┴────┐               │ cancel
    │  draft  │               ▼
    └────┬────┘          ┌───────────┐
         │               │ cancelled │
         │ cancel        └───────────┘
         └──────────────────▶ ▲
```

- **draft**: Can be modified (swap/remove components, NL updates)
- **confirmed**: Locked, no modifications allowed
- **cancelled**: Terminal state (can be deleted)

---

## Concurrency Handling

Uses optimistic locking via `version` field:

1. Client fetches itinerary (includes `version: 3`)
2. Client sends update with `version: 3`
3. Server checks version matches, increments to 4, saves
4. If mismatch: returns 409 Conflict with current version

This prevents lost updates when multiple tabs/users modify the same itinerary.

---

## LLM Safeguards

| Safeguard | Implementation |
|-----------|----------------|
| **Timeout** | 60 second max for LLM operations |
| **Token Limit** | Truncate chat history to last 10 messages |
| **Fallback** | Return partial results on timeout with `"partial": true` |
| **State Source** | Always fetch latest from DB, never rely on LLM memory |
| **Rate Limiting** | 10 requests/minute per traveler_id (future enhancement) |

---

## Natural Language Modification Design (Hybrid Approach)

To support "changing flights/hotels" via text with high reliability:

1. **State Source (Truth)**: We will **NOT** rely on LLM memory for the itinerary state. The API will fetch the latest `Itinerary` JSON from SQLite.
2. **Conversational History**: Stored in `chat_history` table, loaded for context.
3. **Prompt Construction**:
    - **System**: "You are a travel agent helper..."
    - **Context Injection**: "Current Itinerary State: {json_from_db}" (injected dynamically every turn).
    - **Chat History**: "{recent_chat_messages}" (last 10 messages max)
    - **User Input**: "{user_query}"
4. **Execution Flow**:
    - User: "Change flight to tomorrow"
    - LLM (sees current flight is 2025-04-01): Calls `FlightBookingAgent.search(date='2025-04-02')`.
    - Tools execute.
    - **State Update**: Result is saved back to `Itinerary` in SQLite.
    - **Chat Update**: Conversation saved to `chat_history`.

---

## Workflow: Search to Save

This design separates "Searching" from "Saving" to avoid cluttering the database with abandoned queries.

1. **Step 1: Search (Ephemeral)**
    - User asks: "Trips to Paris"
    - Frontend calls `POST /api/v1/agent/plan`
    - Backend returns 3 flight options (in memory only).
2. **Step 2: User Decision**
    - User clicks "Select Option A" on the UI.
3. **Step 3: Save (Persistent)**
    - Frontend calls `POST /api/v1/itineraries` with the data from Option A.
    - Backend saves this as a new Draft Itinerary in SQLite.
    - Now the user can "Modify" the itinerary later.

---

## Proposed Changes

### [Backend] API Layer

#### [NEW] `main_web.py`
Entry point for the FastAPI application with CORS, error handlers, and router mounting.

#### [NEW] `api/__init__.py`
API package initialization.

#### [NEW] `api/routes.py`
All endpoint implementations.

#### [NEW] `api/schemas.py`
Pydantic models for request/response validation.

#### [NEW] `api/dependencies.py`
Dependency injection for DB sessions, LLM, Orchestrator.

### [Backend] Database

#### [NEW] `database/models.py`
SQLModel classes for `Itinerary` and `ChatHistory`.

#### [NEW] `database/connection.py`
SQLite database setup and session management.

#### [NEW] `database/repository.py`
Data access layer with optimistic locking support.

### [Backend] Agent Integration

#### [MODIFY] `agents/itinerary_agent.py`
Refactor `ItineraryAgent` to use Repository pattern instead of `_ITINERARIES` global dict.

### [Frontend] UI

#### [NEW] `frontend/`
New directory for the React application.

- `src/components/ItineraryList.jsx` - Dashboard with pagination
- `src/components/ItineraryBuilder.jsx` - Create new itinerary
- `src/components/ItineraryDetails.jsx` - View/edit details
- `src/components/ChatInterface.jsx` - NL modification chat
- `src/components/LoadingOverlay.jsx` - For LLM operations
- `src/components/ErrorBoundary.jsx` - Error handling
- `src/hooks/useItineraries.js` - React Query hooks
- `src/store/uiStore.js` - Zustand UI state

---

## Verification Plan

### Automated Tests

- **Backend Tests** (`tests/test_api.py`):
  - CRUD operations on Itineraries
  - Status transitions (draft → confirmed, etc.)
  - Optimistic locking (version conflict)
  - Error responses (404, 400, 409)
  - LLM mocking with `unittest.mock`

- **Agent Integration** (`tests/test_agent_db.py`):
  - Verify `ItineraryAgent` correctly reads/writes to DB.

### Manual Verification

1. Start Backend: `uvicorn main_web:app --reload --port 8000`
2. Start Frontend: `cd frontend && npm run dev`
3. Open Web Browser:
    - Create a new Itinerary (Draft).
    - Add a Flight (simulate agent response).
    - Reload page (Verify persistence).
    - Edit the Itinerary via chat.
    - Confirm the Itinerary (verify lock).
4. Test Swagger docs: `http://localhost:8000/docs`

---

## Dependencies to Add

```
# requirements.txt additions
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
sqlmodel>=0.0.14
aiosqlite>=0.19.0
python-multipart>=0.0.6
```

