"""
FastAPI application entry point for Travel Booking Web API.

Run with:
    uvicorn main_web:app --reload --port 8000

API Documentation available at:
    http://localhost:8000/docs (Swagger UI)
    http://localhost:8000/redoc (ReDoc)
"""
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from uuid import uuid4

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from dotenv import load_dotenv

from api.routes import router as api_router
from api.dependencies import startup_event, shutdown_event
from database.connection import create_db_and_tables
from utils.logger import get_logger, SessionContext, _format_duration

# Load environment variables
load_dotenv()

# Initialize logger
logger = get_logger()


# =============================================================================
# Request ID Middleware (P0: Per-Request Traceability)
# =============================================================================

class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware that assigns a unique request ID to every HTTP request.
    
    The request ID is:
    1. Read from X-Request-ID header if provided
    2. Auto-generated UUID if not provided
    3. Set in SessionContext for log correlation
    4. All logs within the request will include this ID
    
    Also tracks request duration for performance monitoring.
    """
    
    async def dispatch(self, request: Request, call_next):
        # Get request ID from header or generate new one
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        
        # Set in SessionContext for logging (P0: per-request traceability)
        SessionContext.set_session_id(request_id)
        
        # Start timing
        start_time = time.perf_counter()
        
        # Log request start
        logger.info(f"Request started: {request.method} {request.url.path}")
        
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000
            duration_str = _format_duration(duration_ms)
            
            # Log request completion with timing
            logger.info(f"Request completed: {request.method} {request.url.path} -> {response.status_code} in {duration_str}")
            
            # Add request ID and timing to response headers for client correlation
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
            
            return response
        except Exception as e:
            # Calculate duration even for errors
            duration_ms = (time.perf_counter() - start_time) * 1000
            duration_str = _format_duration(duration_ms)
            logger.error(f"Request failed: {request.method} {request.url.path} -> {type(e).__name__} in {duration_str}")
            raise
        finally:
            # Clear session context after request
            SessionContext.clear_session()


# =============================================================================
# Lifespan Context Manager
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    """
    # Startup - Setup logger first (reads from environment variables)
    logger.setup()
    
    # Use a special "STARTUP" session ID for application lifecycle logs
    # Per-request logs will use their own request_id (set in get_context)
    SessionContext.set_session_id("STARTUP")
    logger.info("Starting Travel Booking API...")
    startup_event()
    logger.info("Database initialized")
    logger.info("API ready at http://localhost:8000")
    logger.info("Docs available at http://localhost:8000/docs")
    
    # Clear startup session - each request will set its own
    SessionContext.clear_session()
    
    yield
    
    # Shutdown - use special session ID
    SessionContext.set_session_id("SHUTDOWN")
    logger.info("Shutting down Travel Booking API...")
    shutdown_event()
    logger.info("Cleanup complete")


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

# Add request ID middleware FIRST (processes requests before other middleware)
app.add_middleware(RequestIDMiddleware)

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

