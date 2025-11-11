# /ata-backend/app/core/logger.py

"""
Centralized logging configuration for the application.
Uses Python's logging module for production-ready logging.
"""

import logging
import sys
from pathlib import Path

# Create logs directory if it doesn't exist
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)

# Configure logging format
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Create formatters
formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt=DATE_FORMAT,
    handlers=[
        # Console handler - outputs to stdout
        logging.StreamHandler(sys.stdout),
        # File handler - writes to file
        logging.FileHandler(logs_dir / "app.log", encoding="utf-8")
    ]
)

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.

    Args:
        name: Usually __name__ of the calling module

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
