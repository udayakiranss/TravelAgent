# logger.py
# Comprehensive logging system with method entry/exit tracking
import logging
import sys
import os
import uuid
import functools
import inspect
from typing import Optional, Callable, Any
from datetime import datetime
from pathlib import Path


class SessionContext:
    """Context manager for session ID tracking"""
    _current_session_id: Optional[str] = None
    
    @classmethod
    def get_session_id(cls) -> str:
        """Get current session ID or create a new one"""
        if cls._current_session_id is None:
            cls._current_session_id = str(uuid.uuid4())
        return cls._current_session_id
    
    @classmethod
    def set_session_id(cls, session_id: str):
        """Set the current session ID"""
        cls._current_session_id = session_id
    
    @classmethod
    def new_session(cls) -> str:
        """Create a new session and return its ID"""
        cls._current_session_id = str(uuid.uuid4())
        return cls._current_session_id
    
    @classmethod
    def clear_session(cls):
        """Clear the current session"""
        cls._current_session_id = None


class ContextualFormatter(logging.Formatter):
    """Custom formatter that includes filename, line number, and session ID"""
    
    def format(self, record: logging.LogRecord) -> str:
        # Get session ID
        session_id = SessionContext.get_session_id()
        
        # Format session ID (first 8 chars for readability)
        session_short = session_id[:8] if session_id else "NO-SESSION"
        
        # Add custom fields
        record.session_id = session_short
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
              level: str = "INFO",
              output: str = "stdout",
              log_file: Optional[str] = None,
              log_dir: str = "logs") -> None:
        """
        Setup logger configuration
        
        Args:
            level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            output: Output destination ('stdout', 'file', or 'both')
            log_file: Log file name (if None, auto-generates based on timestamp)
            log_dir: Directory for log files
        """
        # Clear existing handlers
        self._logger.handlers.clear()
        
        # Set logging level
        log_level = getattr(logging, level.upper(), logging.INFO)
        self._logger.setLevel(log_level)
        
        # Create formatter
        formatter = ContextualFormatter(
            fmt='%(timestamp)s | %(levelname)-8s | [%(session_id)s] | %(filename)s:%(line_number)d | %(funcName)s | %(message)s',
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
            # Create log directory if it doesn't exist
            log_path = Path(log_dir)
            log_path.mkdir(parents=True, exist_ok=True)
            
            # Generate log file name if not provided
            if log_file is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                log_file = f"travel_booking_{timestamp}.log"
            
            log_file_path = log_path / log_file
            
            file_handler = logging.FileHandler(log_file_path, mode='a', encoding='utf-8')
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            self._logger.addHandler(file_handler)
            
            self._logger.info(f"Logging to file: {log_file_path}")
    
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
            
            # Create a LogRecord with the correct caller information
            record = self._logger.makeRecord(
                self._logger.name,
                level,
                filename,
                lineno,
                message,
                (),
                None,
                funcname
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

