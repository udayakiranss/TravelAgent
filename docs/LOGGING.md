# Logging System Documentation

## Overview

The travel booking system includes a comprehensive logging system that supports:
- **Multiple output destinations**: stdout, file, or both
- **Per-request traceability**: Unique request IDs for correlating all logs within an HTTP request
- **Detailed context**: Filename, line number, function name in every log entry
- **Method entry/exit logging**: Automatic tracking of method calls
- **Configurable levels**: DEBUG (all methods) and INFO (critical methods only)

## Features

### 1. Request ID Tracking (Per-Request Traceability)
- Each HTTP request gets a unique request ID (from `X-Request-ID` header or auto-generated UUID)
- Request ID is included in all log entries for correlation
- Uses Python's `contextvars` for async-safe per-request tracking
- Request IDs are displayed in shortened format (first 8 characters) or special names (`STARTUP`, `SHUTDOWN`)

### 2. Log Format
Every log entry includes:
- **Timestamp**: Precise timestamp with milliseconds
- **Level**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Request ID**: Unique identifier for the HTTP request (enables per-request tracing)
- **Filename**: Source file name
- **Line Number**: Exact line where log was generated
- **Function Name**: Function/method that generated the log
- **Message**: Log message content

Example format:
```
2025-12-08 12:03:18.694 | INFO     | [a1b2c3d4] | orchestrator.py:52 | run_intent | Running intent: {'needs': ['flight']}
2025-12-08 12:03:18.695 | INFO     | [STARTUP]  | main_web.py:47 | lifespan | Starting Travel Booking API...
```

Special request IDs:
- `STARTUP` - Application startup logs
- `SHUTDOWN` - Application shutdown logs
- `NO-REQ-ID` - Logs outside of request context (background tasks, etc.)

### 3. Method Entry/Exit Logging

#### DEBUG Mode
All methods are logged with entry and exit:
```python
@log_method_entry_exit(level="DEBUG")
def my_function():
    # This will log:
    # → ENTRY: my_function() | args=2, kwargs=['param1']
    # ← EXIT: my_function() | success
    pass
```

#### INFO Mode
Only critical methods are logged:
```python
@log_critical_entry_exit
def run_intent():
    # This will log at INFO level:
    # → ENTRY: run_intent() | module=orchestrator.py
    # ← EXIT: run_intent() | success
    pass
```

Critical methods include:
- `run_intent`
- `execute`
- `plan_trip`
- `invoke`
- `__init__`
- `setup`
- `main`

## Configuration

### Environment Variables

Configure logging via environment variables:

```bash
# Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
export LOG_LEVEL=INFO

# Output destination: stdout, file, or both
export LOG_OUTPUT=stdout

# Log file name (optional, auto-generated if not provided)
export LOG_FILE=travel_booking.log

# Log directory (default: logs/)
export LOG_DIR=logs
```

### Programmatic Configuration

```python
from utils.logger import get_logger

logger = get_logger()
logger.setup(
    level="DEBUG",           # Logging level
    output="both",           # stdout, file, or both
    log_file="myapp.log",    # Optional log file name
    log_dir="logs"           # Log directory
)
```

## Usage Examples

### Basic Usage

```python
from utils.logger import get_logger, SessionContext

# Initialize logger
logger = get_logger()
logger.setup(level="INFO", output="stdout")

# Create new session
SessionContext.new_session()

# Log messages
logger.debug("Detailed debug information")
logger.info("General information")
logger.warning("Warning message")
logger.error("Error message")
logger.critical("Critical error")
```

### Method Decorators

```python
from utils.logger import log_method_entry_exit, log_critical_entry_exit

# Log all method calls (DEBUG mode)
@log_method_entry_exit(level="DEBUG")
def search_flights(query):
    # Entry and exit will be logged at DEBUG level
    return results

# Log only critical methods (INFO mode)
@log_critical_entry_exit
def run_intent(intent):
    # Entry and exit will be logged at INFO level
    return results
```

### Context Manager

```python
from utils.logger import LogContext

with LogContext("Processing user request", level="INFO"):
    # This block will log:
    # → Processing user request
    # ← Processing user request | success
    process_request()
```

## Log Levels

### DEBUG
- All method entry/exit points
- Detailed execution flow
- Parameter values
- Internal state changes

### INFO
- Critical method entry/exit (run_intent, execute, plan_trip, etc.)
- High-level operations
- Important state changes
- Session start/end

### WARNING
- Non-critical issues
- Fallback operations
- Missing optional configurations

### ERROR
- Exceptions and errors
- Failed operations
- Includes stack traces

### CRITICAL
- System-critical failures
- Unrecoverable errors

## File Output

When file output is enabled:
- Log files are created in the `logs/` directory (configurable)
- Files are named with timestamp: `travel_booking_YYYYMMDD_HHMMSS.log`
- Or use custom name via `LOG_FILE` environment variable
- Files are appended to (not overwritten)

## Request ID Tracking

Request IDs are automatically managed per HTTP request:
- Each request gets a unique ID from `X-Request-ID` header or auto-generated
- Request ID is set in `get_context()` FastAPI dependency
- All logs within a request share the same request ID
- Uses `contextvars` for async-safe isolation between concurrent requests

```python
from utils.logger import SessionContext

# Set request ID (done automatically in get_context dependency)
SessionContext.set_session_id("custom-request-id")

# Get current request ID
current_id = SessionContext.get_session_id()

# For CLI applications, create a session
session_id = SessionContext.new_session()
print(f"Request ID: {session_id[:8]}")
```

### How it works
1. FastAPI `get_context()` dependency extracts/generates request ID
2. `SessionContext.set_session_id(request_id)` stores it in a `ContextVar`
3. All subsequent logs in that async context include the request ID
4. Concurrent requests are isolated via Python's contextvars mechanism

## Integration Points

The logger is integrated into:
- `main.py`: Application entry point, session management
- `agents/orchestrator.py`: Agent coordination, intent execution
- `agents/planner.py`: Trip planning, agent selection
- All agent classes: Method execution tracking

## Best Practices

1. **Use appropriate log levels**:
   - DEBUG for detailed debugging
   - INFO for normal operations
   - WARNING for recoverable issues
   - ERROR for exceptions
   - CRITICAL for system failures

2. **Include context in messages**:
   ```python
   logger.info(f"Processing intent: {intent}")
   logger.debug(f"Task parameters: {params}")
   ```

3. **Use method decorators** for automatic entry/exit logging

4. **Set session IDs** at the start of request processing

5. **Use file logging** in production for persistence

6. **Rotate log files** regularly to manage disk space

## Troubleshooting

### Logs not appearing
- Check `LOG_LEVEL` environment variable
- Verify logger setup was called
- Check file permissions if using file output

### Too many logs
- Increase log level (INFO instead of DEBUG)
- Remove `@log_method_entry_exit(level="DEBUG")` decorators

### Missing request IDs (showing NO-REQ-ID)
- For web API: Logs should automatically have request IDs via `get_context()` dependency
- For CLI: Call `SessionContext.new_session()` at start
- Check that request ID is set before logging in custom code

### File not created
- Check `LOG_DIR` directory exists and is writable
- Verify `LOG_OUTPUT` includes "file" or "both"

