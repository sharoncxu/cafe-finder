"""Logging utilities for the Location Finding Agent."""

import logging
import sys
from typing import Optional
from ..config import config

def setup_logging(log_level: Optional[int] = None, log_format: Optional[str] = None) -> None:
    """Setup logging configuration for the application."""
    
    level = log_level or config.log_level
    format_string = log_format or (
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        format=format_string,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ],
        force=True  # Override any existing configuration
    )
    
    # Set specific loggers to appropriate levels
    logging.getLogger('googlemaps').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured at level: {logging.getLevelName(level)}")

def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name."""
    return logging.getLogger(name)

class RequestLogger:
    """Context manager for logging request/response pairs."""
    
    def __init__(self, logger: logging.Logger, operation: str, **context):
        self.logger = logger
        self.operation = operation
        self.context = context
    
    def __enter__(self):
        self.logger.info(f"[START] {self.operation}", extra=self.context)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.logger.error(
                f"[ERROR] {self.operation} failed: {exc_val}", 
                extra=self.context,
                exc_info=True
            )
        else:
            self.logger.info(f"[SUCCESS] {self.operation}", extra=self.context)
        return False  # Don't suppress exceptions