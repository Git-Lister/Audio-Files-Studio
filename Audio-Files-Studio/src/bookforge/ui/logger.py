# src/bookforge/ui/logger.py
"""Persistent error logging for the UI."""

import logging
import sys
import traceback
from pathlib import Path

# Log file inside the container (will be mounted to host)
LOG_FILE = Path("/app/error.log")

logger = logging.getLogger("bookforge_ui")
logger.setLevel(logging.DEBUG)

# File handler
file_handler = logging.FileHandler(LOG_FILE)
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Console handler (for Docker logs)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


def log_error(error: Exception, context: str = "") -> None:
    """Log an error with full traceback."""
    tb = traceback.format_exc()
    logger.error(f"Context: {context}\n{error}\n{tb}")
