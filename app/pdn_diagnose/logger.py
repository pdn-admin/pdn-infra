"""
Logger Module for PDN Diagnose

This module provides logging configuration for the PDN Diagnose system.
It sets up console logging with standardized formatting for debugging
and monitoring purposes.

Key features:
- Console-based logging output
- Standardized log format with timestamps
- Configurable log levels
- Module-specific logger instances
"""

import logging


def setup_logger(name='pdn_diagnose'):
    """Setup logger for pdn_diagnose module"""
    logger = logging.getLogger(name)

    # Only add handler if logger doesn't already have one (idempotent)
    if not logger.handlers:
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        # Create console handler only
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        # Add handler to logger
        logger.addHandler(console_handler)

    # Set log level
    logger.setLevel(logging.INFO)

    return logger
