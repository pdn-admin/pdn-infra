import csv
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

from .pdn_file_path import PDNFilePath

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UserMetadataHandler:
    """Optimized utility class for handling user metadata CSV operations."""

    def __init__(self):
        """Initialize CSV metadata handler with optimized configuration."""
        pdn_file_path = PDNFilePath()
        user_dir = pdn_file_path.get_base_dir()
        self.csv_filename = user_dir / "user_metadata.csv"

        self.headers = [
            "User ID",
            "Email",
            "Date",
            "PDN Code",
            "PDN Voice Code",
            "Diagnose PDN Code",
            "Diagnose Comments",
            "PDN Update Comments",
            "Referral Source"
        ]

        # Cache for frequently accessed data
        self._data_cache = None
        self._cache_timestamp = None
        self._cache_validity_seconds = 30  # Cache valid for 30 seconds

    def _generate_unique_id(self) -> str:
        """
        Generate a unique user ID.
        
        Returns:
            A unique user ID string in format UID followed by 6 characters
        """
        # Generate a UUID and take the first 6 characters
        unique_part = str(uuid.uuid4()).replace('-', '')[:6].upper()
        return f"UID{unique_part}"

    def _is_cache_valid(self) -> bool:
        """Check if the current cache is still valid."""
        if self._data_cache is None or self._cache_timestamp is None:
            return False

        current_time = datetime.now().timestamp()
        return (current_time - self._cache_timestamp) < self._cache_validity_seconds

    def _invalidate_cache(self) -> None:
        """Invalidate the current cache."""
        self._data_cache = None
        self._cache_timestamp = None

    def ensure_csv_exists(self) -> None:
        """Create CSV file with headers if it doesn't exist."""
        try:
            if not os.path.exists(self.csv_filename):
                os.makedirs(os.path.dirname(self.csv_filename), exist_ok=True)
                with open(self.csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(self.headers)
                logger.info(f"Created new CSV file: {self.csv_filename}")

        except Exception as e:
            logger.error(f"Error creating CSV file: {e}")
            raise

    def _validate_email(self, email: str) -> bool:
        """Validate email format and presence."""
        if not email or not isinstance(email, str):
            return False
        email = email.strip()
        return '@' in email and '.' in email and len(email) > 5

    def _read_csv_data(self) -> List[Dict[str, str]]:
        """Read CSV data with error handling and caching."""
        try:
            if not os.path.exists(self.csv_filename):
                return []

            # Check cache validity
            if self._is_cache_valid():
                return self._data_cache.copy()

            data = []
            with open(self.csv_filename, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                data = list(reader)

            # Update cache
            self._data_cache = data
            self._cache_timestamp = datetime.now().timestamp()

            return data

        except Exception as e:
            logger.error(f"Error reading CSV data: {e}")
            return []

    def _write_csv_data(self, data: List[Dict[str, str]]) -> bool:
        """Write data to CSV with error handling."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.csv_filename), exist_ok=True)

            with open(self.csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.headers)
                writer.writeheader()
                writer.writerows(data)

            # Invalidate cache after write
            self._invalidate_cache()
            return True

        except Exception as e:
            logger.error(f"Error writing CSV data: {e}")
            return False

    def append_user_metadata(self, user_data: Dict[str, Any]) -> bool:
        """
        Append user metadata to CSV file with improved validation.
        
        Args:
            user_data: Dictionary containing user metadata from form submission
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate input
            if not isinstance(user_data, dict):
                logger.error("Invalid user_data: must be a dictionary")
                return False

            # Validate required fields
            email = user_data.get('email', '').strip()
            if not self._validate_email(email):
                logger.error(f"Invalid email: {email}")
                return False

            # Ensure CSV file exists
            self.ensure_csv_exists()

            # Check for existing user
            existing_data = self._read_csv_data()
            if any(row.get("Email", "").strip() == email for row in existing_data):
                logger.info(f"User {email} already exists in CSV, skipping duplicate entry")
                return True

            # Prepare new row
            new_row = {
                "User ID": self._generate_unique_id(),
                "Email": email,
                "Date": datetime.now().strftime("%d/%m/%Y"),
                "PDN Code": "",
                "PDN Voice Code": "",
                "Diagnose PDN Code": "",
                "Diagnose Comments": "",
                "PDN Update Comments": "",
                "Referral Source": user_data.get('referral_source', '')
            }

            # Add new row
            existing_data.append(new_row)

            # Write back to file
            if self._write_csv_data(existing_data):
                logger.info(f"Successfully added user {email} to CSV metadata")
                return True
            else:
                logger.error(f"Failed to write data for user {email}")
                return False

        except Exception as e:
            logger.error(f"Error appending metadata to CSV: {e}")
            return False

    def get_user_by_email(self, email: str) -> Optional[Dict[str, str]]:
        """
        Get specific user metadata by email with caching.
        
        Args:
            email: User's email address
            
        Returns:
            Dictionary containing user metadata or None if not found
        """
        if not self._validate_email(email):
            return None

        try:
            data = self._read_csv_data()
            email = email.strip()

            for row in data:
                if row.get("Email", "").strip() == email:
                    return row

            return None

        except Exception as e:
            logger.error(f"Error finding user metadata: {e}")
            return None

    def get_user_files(self, email: str, file_type: str) -> Optional[Dict[str, Any]]:
        """
        Find specific user metadata by email.
        
        Args:
            email: User's email address
            file_type: Type of file to find
            
        Returns:
            Dictionary containing user metadata or None if not found
        """
        try:
            pdn_file_path = PDNFilePath()

            # Construct filename based on file type
            if file_type == "answers":
                filename = f"{email}_answers.json"
            else:
                filename = f"{email}_{file_type}.json"

            file_path = pdn_file_path.get_user_file_path(email, filename)

            if not os.path.exists(file_path):
                return None

            with open(file_path, 'r', encoding='utf-8') as jsonfile:
                data = json.load(jsonfile)

            return data

        except Exception as e:
            logger.error(f"Error finding user metadata: {e}")
            return None

    def _update_user_field(self, email: str, field_name: str, value: str) -> bool:
        """
        Generic method to update a specific field for a user.
        
        Args:
            email: User's email address
            field_name: Name of the field to update
            value: New value for the field
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self._validate_email(email):
                logger.error(f"Invalid email: {email}")
                return False

            if field_name not in self.headers:
                logger.error(f"Invalid field name: {field_name}")
                return False

            if not os.path.exists(self.csv_filename):
                logger.error("CSV file does not exist")
                return False

            # Read current data
            data = self._read_csv_data()
            email = email.strip()

            # Find and update user
            updated = False
            for row in data:
                if row.get("Email", "").strip() == email:
                    row[field_name] = value
                    updated = True
                    break

            if not updated:
                logger.warning(f"User {email} not found in CSV")
                return False

            # Write back data
            if self._write_csv_data(data):
                logger.info(f"Successfully updated {field_name} for {email}: {value}")
                return True
            else:
                logger.error(f"Failed to write updated data for {email}")
                return False

        except Exception as e:
            logger.error(f"Error updating {field_name}: {e}")
            return False

    def update_pdn_code(self, email: str, pdn_code: str) -> bool:
        """
        Update PDN Code for a specific user.
        
        Args:
            email: User's email address
            pdn_code: The calculated PDN code
            
        Returns:
            True if successful, False otherwise
        """
        return self._update_user_field(email, "PDN Code", pdn_code)

    def update_pdn_code_with_comment(self, email: str, pdn_code: str, updated_by: str) -> bool:
        """
        Update PDN Code for a specific user with comment about who updated it and when.
        
        Args:
            email: User's email address
            pdn_code: The calculated PDN code
            updated_by: Name/email of the person who updated the PDN code
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Update PDN code
            pdn_updated = self.update_pdn_code(email, pdn_code)

            if pdn_updated:
                # Create comment with timestamp and user info
                current_time = datetime.now().strftime("%d/%m/%Y %H:%M")
                comment = f"Updated on {current_time} by {updated_by}"

                # Update the comment field
                comment_updated = self._update_user_field(email, "PDN Update Comments", comment)

                return comment_updated
            else:
                return False

        except Exception as e:
            logger.error(f"Error updating PDN code with comment: {e}")
            return False

    def update_diagnose_code(self, email: str, diagnose_code: str, diagnose_comments: str = "") -> bool:
        """
        Update Diagnose PDN Code and comments for a specific user.
        
        Args:
            email: User's email address
            diagnose_code: The manual diagnosis PDN code
            diagnose_comments: Comments from the diagnostician
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self._validate_email(email):
                return False

            if not os.path.exists(self.csv_filename):
                logger.error("CSV file does not exist")
                return False

            # Read current data
            data = self._read_csv_data()
            email = email.strip()

            # Find and update user
            updated = False
            for row in data:
                if row.get("Email", "").strip() == email:
                    row["Diagnose PDN Code"] = diagnose_code
                    row["Diagnose Comments"] = diagnose_comments
                    updated = True
                    break

            if not updated:
                logger.warning(f"User {email} not found in CSV")
                return False

            # Write back data
            if self._write_csv_data(data):
                logger.info(f"Successfully updated Diagnose Code for {email}: {diagnose_code}")
                return True
            else:
                logger.error(f"Failed to write updated diagnose data for {email}")
                return False

        except Exception as e:
            logger.error(f"Error updating Diagnose Code: {e}")
            return False
