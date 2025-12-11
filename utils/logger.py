# logger.py
# Comprehensive logging system with method entry/exit tracking and performance timing
import logging
import sys
import os
import uuid
import functools
import inspect
import time
from contextvars import ContextVar
from typing import Optional, Callable, Any
from datetime import datetime
from pathlib import Path


# Context variable for async-safe per-request session tracking
_request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)


class SessionContext:
    """
    Context manager for request ID tracking.
    
    Uses contextvars for async-safe per-request correlation.
    Each HTTP request gets its own request_id that propagates through all logs.
    """
    
    @classmethod
    def get_session_id(cls) -> str:
        """Get current request ID or generate a fallback"""
        request_id = _request_id_var.get()
        if request_id is None:
            # Fallback for non-request contexts (startup, background tasks)
            return "NO-REQ-ID"
        return request_id
    
    @classmethod
    def set_session_id(cls, session_id: str):
        """Set the current request ID (called per-request)"""
        _request_id_var.set(session_id)
    
    @classmethod
    def new_session(cls) -> str:
        """Create a new request ID and return it"""
        new_id = str(uuid.uuid4())
        _request_id_var.set(new_id)
        return new_id
    
    @classmethod
    def clear_session(cls):
        """Clear the current request ID"""
        _request_id_var.set(None)
    
    @classmethod
    def get_request_id(cls) -> Optional[str]:
        """Get the raw request ID (may be None)"""
        return _request_id_var.get()


class ContextualFormatter(logging.Formatter):
    """Custom formatter that includes filename, line number, and request ID"""
    
    def format(self, record: logging.LogRecord) -> str:
        # Get request ID for correlation
        request_id = SessionContext.get_session_id()
        
        # Format request ID (first 8 chars for readability, or special names like STARTUP/SHUTDOWN)
        if request_id in ("STARTUP", "SHUTDOWN", "NO-REQ-ID"):
            request_id_short = request_id
        else:
            request_id_short = request_id[:8] if request_id else "NO-REQ-ID"
        
        # Add custom fields
        record.request_id = request_id_short
        record.filename = os.path.basename(record.pathname)
        record.line_number = record.lineno
        
        # Format timestamp
        record.timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        
        return super().format(record)


class TravelBookingLogger:
    """Main logger class for the travel booking system"""
    
    _instance: Optional['TravelBookingLogger'] = None
    _logger: Optional[logging.Logger] = None
    _initialized: bool = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._logger = logging.getLogger('TravelBooking')
            self._logger.setLevel(logging.DEBUG)
            self._logger.propagate = False
            self._initialized = True
    
    def setup(self, 
              level: Optional[str] = None,
              output: Optional[str] = None,
              log_file: Optional[str] = None,
              log_dir: Optional[str] = None) -> None:
        """
        Setup logger configuration
        
        Args:
            level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL). 
                   If None, reads from LOG_LEVEL environment variable (default: INFO)
            output: Output destination ('stdout', 'file', or 'both').
                    If None, reads from LOG_OUTPUT environment variable (default: stdout)
            log_file: Log file name (if None, reads from LOG_FILE env var or auto-generates)
            log_dir: Directory for log files. If None, reads from LOG_DIR env var (default: logs)
        """
        # Read from environment variables if not provided
        if level is None:
            level = os.getenv('LOG_LEVEL', 'INFO')
        if output is None:
            output = os.getenv('LOG_OUTPUT', 'stdout')
        if log_file is None:
            log_file = os.getenv('LOG_FILE', None)
        if log_dir is None:
            log_dir = os.getenv('LOG_DIR', 'logs')
        
        # Clear existing handlers
        self._logger.handlers.clear()
        
        # Set logging level
        log_level = getattr(logging, level.upper(), logging.INFO)
        self._logger.setLevel(log_level)
        
        # Create formatter
        formatter = ContextualFormatter(
            fmt='%(timestamp)s | %(levelname)-8s | [%(request_id)s] | %(filename)s:%(line_number)d | %(funcName)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Setup stdout handler
        if output in ('stdout', 'both'):
            stdout_handler = logging.StreamHandler(sys.stdout)
            stdout_handler.setLevel(log_level)
            stdout_handler.setFormatter(formatter)
            self._logger.addHandler(stdout_handler)
        
        # Setup file handler
        if output in ('file', 'both'):
            # Create log directory if it doesn't exist (use absolute path)
            log_path = Path(log_dir).resolve()
            log_path.mkdir(parents=True, exist_ok=True)
            
            # Generate log file name if not provided
            if log_file is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                log_file = f"travel_booking_{timestamp}.log"
            
            log_file_path = log_path / log_file
            
            file_handler = logging.FileHandler(str(log_file_path), mode='a', encoding='utf-8')
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            self._logger.addHandler(file_handler)
            
            # Log to file (this will go to the file handler we just added)
            # Use the underlying logger directly to avoid our custom _log method during setup
            record = self._logger.makeRecord(
                self._logger.name,
                logging.INFO,
                os.path.basename(__file__),
                0,
                f"Logging to file: {log_file_path}",
                (),
                None,
                'setup'
            )
            self._logger.handle(record)
    
    def get_logger(self) -> logging.Logger:
        """Get the underlying logger instance"""
        return self._logger
    
    def _log(self, level: int, message: str, **kwargs):
        """Internal logging method that captures the correct caller"""
        import inspect
        # Get the caller's frame (skip this method and the wrapper method)
        frame = inspect.currentframe()
        try:
            # Go up 2 frames: skip _log and the wrapper method (debug/info/etc)
            caller_frame = frame.f_back.f_back
            filename = os.path.basename(caller_frame.f_code.co_filename)
            lineno = caller_frame.f_lineno
            funcname = caller_frame.f_code.co_name
            
            # Merge any custom fields passed via logging extra
            extra_fields = kwargs.get("extra")
            
            # Create a LogRecord with the correct caller information
            record = self._logger.makeRecord(
                self._logger.name,
                level,
                filename,
                lineno,
                message,
                (),
                None,
                funcname,
                extra=extra_fields
            )
            self._logger.handle(record)
        finally:
            del frame
    
    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self._log(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message"""
        self._log(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self._log(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message"""
        self._log(logging.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message"""
        self._log(logging.CRITICAL, message, **kwargs)
    
    def exception(self, message: str, **kwargs):
        """Log exception with traceback"""
        # For exceptions, we need to preserve the exception info
        import inspect
        frame = inspect.currentframe()
        try:
            caller_frame = frame.f_back
            filename = os.path.basename(caller_frame.f_code.co_filename)
            lineno = caller_frame.f_lineno
            funcname = caller_frame.f_code.co_name
            
            record = self._logger.makeRecord(
                self._logger.name,
                logging.ERROR,
                filename,
                lineno,
                message,
                (),
                sys.exc_info(),
                funcname
            )
            self._logger.handle(record)
        finally:
            del frame


# Global logger instance
_logger_instance = TravelBookingLogger()


def get_logger() -> TravelBookingLogger:
    """Get the global logger instance"""
    return _logger_instance


def log_method_entry_exit(level: str = "DEBUG"):
    """
    Decorator to log method entry and exit
    
    Args:
        level: Logging level for entry/exit ('DEBUG' logs all, 'INFO' logs only critical)
    """
    def decorator(func: Callable) -> Callable:
        # Determine if this should be logged based on level
        log_this = (level == "DEBUG") or (level == "INFO" and _is_critical_method(func))
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not log_this:
                return func(*args, **kwargs)
            
            logger = get_logger()
            func_name = func.__name__
            module_name = os.path.basename(inspect.getfile(func))
            func_file = inspect.getfile(func)
            func_line = inspect.getsourcelines(func)[1]
            
            # Log entry with correct file location
            _log_with_location(
                logger, 
                logging.DEBUG if level == "DEBUG" else logging.INFO,
                f"→ ENTRY: {func_name}() | args={len(args)}, kwargs={list(kwargs.keys())}",
                func_file,
                func_line,
                func_name
            )
            
            try:
                # Execute function
                result = func(*args, **kwargs)
                
                # Log exit with correct file location
                _log_with_location(
                    logger,
                    logging.DEBUG if level == "DEBUG" else logging.INFO,
                    f"← EXIT: {func_name}() | success",
                    func_file,
                    func_line,
                    func_name
                )
                
                return result
            except Exception as e:
                # Log exception exit with correct file location
                _log_with_location(
                    logger,
                    logging.ERROR,
                    f"← EXIT: {func_name}() | exception: {type(e).__name__}: {str(e)}",
                    func_file,
                    func_line,
                    func_name
                )
                raise
        
        return wrapper
    return decorator


def _log_with_location(logger_instance: TravelBookingLogger, level: int, message: str, 
                      filename: str, lineno: int, funcname: str):
    """Helper to log with specific file location"""
    logger = logger_instance.get_logger()
    record = logger.makeRecord(
        logger.name,
        level,
        filename,
        lineno,
        message,
        (),
        None,
        funcname
    )
    logger.handle(record)


def _is_critical_method(func: Callable) -> bool:
    """Determine if a method is critical (should be logged at INFO level)"""
    critical_patterns = [
        'run_intent',
        'execute',
        'plan_trip',
        'invoke',
        '__init__',
        'setup',
        'main',
    ]
    return any(pattern in func.__name__ for pattern in critical_patterns)


def log_critical_entry_exit(func: Callable) -> Callable:
    """Decorator specifically for critical methods (always logged at INFO level)"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = get_logger()
        func_name = func.__name__
        module_name = os.path.basename(inspect.getfile(func))
        func_file = inspect.getfile(func)
        func_line = inspect.getsourcelines(func)[1]
        
        # Log entry at INFO level with correct file location
        _log_with_location(
            logger,
            logging.INFO,
            f"→ ENTRY: {func_name}() | module={module_name}",
            func_file,
            func_line,
            func_name
        )
        
        try:
            result = func(*args, **kwargs)
            _log_with_location(
                logger,
                logging.INFO,
                f"← EXIT: {func_name}() | success",
                func_file,
                func_line,
                func_name
            )
            return result
        except Exception as e:
            _log_with_location(
                logger,
                logging.ERROR,
                f"← EXIT: {func_name}() | exception: {type(e).__name__}: {str(e)}",
                func_file,
                func_line,
                func_name
            )
            raise
    
    return wrapper


# Convenience function for context manager
class LogContext:
    """Context manager for logging code blocks"""
    
    def __init__(self, message: str, level: str = "DEBUG"):
        self.message = message
        self.level = level
        self.logger = get_logger()
    
    def __enter__(self):
        log_func = getattr(self.logger, self.level.lower())
        log_func(f"→ {self.message}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            log_func = getattr(self.logger, self.level.lower())
            log_func(f"← {self.message} | success")
        else:
            self.logger.error(f"← {self.message} | exception: {exc_type.__name__}: {str(exc_val)}")
        return False


# ============================================================================
# Performance Timing Utilities
# ============================================================================

def _format_duration(duration_ms: float) -> str:
    """Format duration in human-readable form"""
    if duration_ms < 1:
        return f"{duration_ms * 1000:.0f}µs"
    elif duration_ms < 1000:
        return f"{duration_ms:.1f}ms"
    elif duration_ms < 60000:
        return f"{duration_ms / 1000:.2f}s"
    else:
        minutes = int(duration_ms // 60000)
        seconds = (duration_ms % 60000) / 1000
        return f"{minutes}m {seconds:.1f}s"


class Timer:
    """
    Context manager for timing code blocks.
    
    Usage:
        with Timer("LLM call") as t:
            result = llm.invoke(prompt)
        # Logs: "LLM call completed in 1.23s"
        
        # Or access duration manually:
        with Timer("DB query", log=False) as t:
            result = db.query(...)
        print(f"Query took {t.duration_ms}ms")
    """
    
    def __init__(self, operation: str, level: str = "DEBUG", log: bool = True):
        """
        Args:
            operation: Name of the operation being timed
            level: Log level (DEBUG, INFO, WARNING)
            log: Whether to auto-log on exit (default True)
        """
        self.operation = operation
        self.level = level.upper()
        self.log = log
        self.logger = get_logger()
        self.start_time: float = 0
        self.end_time: float = 0
        self.duration_ms: float = 0
    
    def __enter__(self) -> "Timer":
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.perf_counter()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        
        if self.log:
            duration_str = _format_duration(self.duration_ms)
            if exc_type is None:
                log_func = getattr(self.logger, self.level.lower())
                log_func(f"⏱ {self.operation} completed in {duration_str}")
            else:
                self.logger.error(f"⏱ {self.operation} failed after {duration_str}: {exc_type.__name__}")
        
        return False
    
    @property
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds (can be called during execution)"""
        if self.end_time > 0:
            return self.duration_ms
        return (time.perf_counter() - self.start_time) * 1000


def timed(operation: Optional[str] = None, level: str = "DEBUG"):
    """
    Decorator to time function execution.
    
    Usage:
        @timed("search flights")
        def search_flights(params):
            ...
        # Logs: "⏱ search flights completed in 45.2ms"
        
        @timed()  # Uses function name
        def process_data():
            ...
        # Logs: "⏱ process_data completed in 123.4ms"
    """
    def decorator(func: Callable) -> Callable:
        op_name = operation or func.__name__
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            with Timer(op_name, level=level):
                return func(*args, **kwargs)
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            with Timer(op_name, level=level):
                return await func(*args, **kwargs)
        
        # Return appropriate wrapper based on function type
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


class PerformanceMetrics:
    """
    Aggregates timing metrics for a request.
    
    Usage:
        metrics = PerformanceMetrics()
        
        with metrics.time("llm_call"):
            result = llm.invoke(...)
        
        with metrics.time("db_query"):
            data = db.query(...)
        
        metrics.log_summary()
        # Logs: "Request metrics: llm_call=1234ms, db_query=45ms, total=1279ms"
    """
    
    def __init__(self):
        self.timings: dict[str, float] = {}
        self.start_time = time.perf_counter()
        self.logger = get_logger()
    
    def time(self, operation: str) -> "MetricTimer":
        """Create a timer that records to this metrics instance"""
        return MetricTimer(operation, self)
    
    def record(self, operation: str, duration_ms: float):
        """Manually record a timing"""
        if operation in self.timings:
            self.timings[operation] += duration_ms
        else:
            self.timings[operation] = duration_ms
    
    @property
    def total_ms(self) -> float:
        """Total elapsed time since metrics creation"""
        return (time.perf_counter() - self.start_time) * 1000
    
    def log_summary(self, level: str = "INFO"):
        """Log a summary of all recorded timings"""
        if not self.timings:
            return
        
        parts = [f"{op}={_format_duration(ms)}" for op, ms in self.timings.items()]
        total = _format_duration(self.total_ms)
        summary = f"⏱ Request metrics: {', '.join(parts)}, total={total}"
        
        log_func = getattr(self.logger, level.lower())
        log_func(summary)
    
    def to_dict(self) -> dict:
        """Return timings as a dictionary (for API responses)"""
        return {
            **{k: round(v, 2) for k, v in self.timings.items()},
            "total_ms": round(self.total_ms, 2)
        }


class MetricTimer:
    """Timer that records to a PerformanceMetrics instance"""
    
    def __init__(self, operation: str, metrics: PerformanceMetrics):
        self.operation = operation
        self.metrics = metrics
        self.start_time: float = 0
    
    def __enter__(self) -> "MetricTimer":
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.perf_counter() - self.start_time) * 1000
        self.metrics.record(self.operation, duration_ms)
        return False

