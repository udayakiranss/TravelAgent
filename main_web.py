"""
FastAPI application entry point for Travel Booking Web API.

Run with:
    uvicorn main_web:app --reload --port 8000

API Documentation available at:
    http://localhost:8000/docs (Swagger UI)
    http://localhost:8000/redoc (ReDoc)
"""
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from dotenv import load_dotenv

from api.routes import router as api_router
from api.dependencies import startup_event, shutdown_event
from database.connection import create_db_and_tables

# Load environment variables
load_dotenv()


# =============================================================================
# Lifespan Context Manager
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    """
    # Startup
    print("🚀 Starting Travel Booking API...")
    startup_event()
    print("✅ Database initialized")
    print("✅ API ready at http://localhost:8000")
    print("📚 Docs available at http://localhost:8000/docs")
    
    yield
    
    # Shutdown
    print("🛑 Shutting down...")
    shutdown_event()
    print("✅ Cleanup complete")


# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title="Travel Booking API",
    description="""
## Travel Booking Web API

A comprehensive API for managing travel itineraries with AI-powered natural language processing.

### Features
- **CRUD Operations**: Create, read, update, and delete travel itineraries
- **Natural Language Planning**: Use AI to plan trips from text queries
- **Optimistic Locking**: Prevent concurrent update conflicts
- **Status Workflow**: Draft → Confirmed → Cancelled workflow

### Authentication
Currently uses traveler_id for identification. Full authentication can be added later.

### Rate Limits
LLM operations have a 60-second timeout to prevent runaway requests.
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# =============================================================================
# CORS Middleware
# =============================================================================

# Configure CORS for frontend access
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Exception Handlers
# =============================================================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors with standard error format."""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "status_code": 422,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": {"validation_errors": errors}
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors with standard error format."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
            "status_code": 500,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": {"exception": str(exc)} if os.getenv("DEBUG") else None
        }
    )


# =============================================================================
# Include Routers
# =============================================================================

app.include_router(api_router)


# =============================================================================
# Root Endpoint
# =============================================================================

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Travel Booking API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/health",
        "status": "running"
    }


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    
    uvicorn.run(
        "main_web:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )

