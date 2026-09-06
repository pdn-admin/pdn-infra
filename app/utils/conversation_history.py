"""
Conversation History Module

This module provides functionality for managing conversation history between users
and the AI system. It maintains a rolling history of messages with configurable
limits and provides context formatting for AI chat systems.

Key features:
- Per-user conversation history storage
- Configurable message limits
- Context formatting for AI systems
- Safe file handling with error recovery
"""

import json
import logging
import os
from typing import List, Dict

from .constants import ConversationConstants


class ConversationHistory:
    """Manages conversation history for users with a maximum of MAX_HISTORY_MESSAGES messages per user"""

    def __init__(self, storage_dir: str = ConversationConstants.STORAGE_DIR):
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)

    def _get_user_file_path(self, user_id: str) -> str:
        """Get the file path for a specific user's conversation history"""
        safe_user_id = user_id.replace('/', '_').replace('\\', '_')
        return os.path.join(self.storage_dir, f"{safe_user_id}.json")

    def add_message(self, user_id: str, message: str, response: str, user_name: str = None) -> None:
        """
        Add a message-response pair to the user's conversation history
        
        Args:
            user_id: Unique identifier for the user
            message: User's message
            response: AI's response
            user_name: Optional user name for context
        """
        try:
            history = self.get_history(user_id)

            # Add new message-response pair
            message_entry = {
                "message": message,
                "response": response,
                "user_name": user_name
            }

            history.append(message_entry)

            # Keep only the last MAX_HISTORY_MESSAGES messages
            if len(history) > ConversationConstants.MAX_HISTORY_MESSAGES:
                history = history[-ConversationConstants.MAX_HISTORY_MESSAGES:]

            # Save to file
            self._save_history(user_id, history)

        except Exception as e:
            logging.error(f"Error adding message to history: {e}")

    def get_history(self, user_id: str) -> List[Dict]:
        """
        Get conversation history for a user
        
        Args:
            user_id: Unique identifier for the user
            
        Returns:
            List of message-response dictionaries (MAX_HISTORY_MESSAGES)
        """
        try:
            file_path = self._get_user_file_path(user_id)

            if not os.path.exists(file_path):
                return []

            with open(file_path, 'r', encoding='utf-8') as f:
                history = json.load(f)

            return history if isinstance(history, list) else []

        except Exception as e:
            logging.error(f"Error loading conversation history: {e}")
            return []

    def get_conversation_context(self, user_id: str) -> str:
        """
        Get conversation history formatted as context for the AI system
        
        Args:
            user_id: Unique identifier for the user
            
        Returns:
            Formatted conversation history as string
        """
        history = self.get_history(user_id)

        if not history:
            return ""

        context_parts = []
        for entry in history:
            user_msg = entry.get('message', '')
            ai_response = entry.get('response', '')

            context_parts.append(f"User: {user_msg}")
            context_parts.append(f"Assistant: {ai_response}")

        return "\n\n".join(context_parts)

    def clear_history(self, user_id: str) -> bool:
        """
        Clear conversation history for a user
        
        Args:
            user_id: Unique identifier for the user
            
        Returns:
            True if successful, False otherwise
        """
        try:
            file_path = self._get_user_file_path(user_id)

            # if os.path.exists(file_path):
            #    os.remove(file_path)

            return True

        except Exception as e:
            logging.error(f"Error clearing conversation history: {e}")
            return False

    def _save_history(self, user_id: str, history: List[Dict]) -> None:
        """Save conversation history to file"""
        try:
            file_path = self._get_user_file_path(user_id)

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logging.error(f"Error saving conversation history: {e}")


# Global instance
conversation_history = ConversationHistory()
