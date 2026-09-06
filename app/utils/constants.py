"""
Constants Module

This module defines constants used throughout the PDN (Personality Development Number)
application. It provides centralized configuration values for conversation management,
file paths, and other system-wide settings.

Key constants:
- Conversation history limits
- Storage directory paths
- System configuration values
"""

class ConversationConstants:
    """Constants for conversation history management"""

    # Maximum number of messages to keep in conversation history per user
    MAX_HISTORY_MESSAGES = 10

    # Storage directory for conversation history files
    STORAGE_DIR = "./conversation_history"
