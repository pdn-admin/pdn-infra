"""
PDN File Path Module

This module provides utilities for managing file paths and directories
for the PDN (Personality Development Number) system. It handles user-specific
directory creation, file path generation, and safe filename handling.

Key features:
- User directory management based on email addresses
- Safe filename generation (removing special characters)
- File path resolution with automatic directory creation
- File discovery utilities for different file types
"""

import os
from pathlib import Path
from typing import Optional


class PDNFilePath:
    """Utility class for handling PDN file paths and user directories."""

    def __init__(self, base_dir: Optional[str] = None):
        """
        Initialize PDNFilePath utility.
        
        Args:
            base_dir: Base directory for saved results. Defaults to 'saved_results'
        """
        self.base_dir = Path(base_dir or os.getenv('SAVED_RESULTS_DIR', 'saved_results'))

    def get_base_dir(self) -> Path:
        """
        Get base directory.
        
        Returns:
            Path object pointing to the base directory
        """
        return self.base_dir

    def get_user_dir(self, user_email: str) -> Path:
        """
        Get or create user directory based on email.
        
        Args:
            user_email: User's email address
            
        Returns:
            Path object pointing to the user's directory
        """
        # Create safe username from email
        safe_username = "".join(c for c in user_email if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_username = safe_username.replace(' ', '_')

        # Create user directory path
        user_dir = self.base_dir / safe_username

        # Create directory if it doesn't exist
        user_dir.mkdir(parents=True, exist_ok=True)

        return user_dir

    def get_user_file_path(self, user_email: str, filename: str) -> Path:
        """
        Get file path within user directory.
        
        Args:
            user_email: User's email address
            filename: Name of the file
            
        Returns:
            Path object pointing to the file within user directory
        """
        user_dir = self.get_user_dir(user_email)
        file_path = user_dir / filename

        return file_path

    def find_user_file(self, user_email: str, file_type: str) -> Optional[Path]:
        """
        Find user file based on email and file type.
        
        Args:
            user_email: User's email address
            file_type: Type of file to find
            
        Returns:
            Path object pointing to the file, or None if not found
        """
        # Create safe username from email
        safe_username = "".join(c for c in user_email if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_username = safe_username.replace(' ', '_')

        # Create user directory path without creating it
        user_dir = self.base_dir / safe_username

        # Only search if directory exists
        if not user_dir.exists():
            return None

        list_of_files = list(user_dir.glob(f"*{file_type}"))
        if len(list_of_files) == 0:
            return None
        return list_of_files[0]
