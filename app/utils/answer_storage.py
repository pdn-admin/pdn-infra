import json
import fcntl
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

from .csv_metadata_handler import UserMetadataHandler
from .pdn_file_path import PDNFilePath

logger = logging.getLogger(__name__)

pdn_file_path = PDNFilePath()


def _load_json_data(file_path: Path) -> Dict[str, Any]:
    """Load JSON data from file with error handling."""
    if not file_path.exists():
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Failed to load JSON from {file_path}: {e}")
        return {}


def _save_with_lock(file_path: Path, data: Dict[str, Any]) -> None:
    """Save data to file with file locking."""
    lock_path = file_path.with_suffix('.lock')
    try:
        with open(lock_path, 'w') as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    except Exception as e:
        logger.error(f"Failed to save data to {file_path}: {e}")
        raise


def save_answer(email: str, question_number: int, answer_data: Dict[str, Any], question_text: Optional[str] = None) -> None:
    """Save a single answer to the user's JSON file."""
    try:
        file_path = pdn_file_path.get_user_file_path(email, f"{email}_answers.json")
        data = _load_json_data(file_path)
        
        filtered_data = {k: v for k, v in answer_data.items() if v is not None}
        if question_text:
            filtered_data['question_text'] = question_text
        
        data[str(question_number)] = filtered_data
        _save_with_lock(file_path, data)
    except Exception as e:
        logger.error(f"Failed to save answer for {email}, question {question_number}: {e}")
        raise


def load_answers(email: str) -> Optional[Dict[str, Any]]:
    """Load user answers from JSON file."""
    try:
        file_path = pdn_file_path.get_user_file_path(email, f"{email}_answers.json")
        return _load_json_data(file_path) or None
    except Exception as e:
        logger.error(f"Failed to load answers for {email}: {e}")
        return None


def delete_answer(email: str, question_number: int) -> bool:
    """Delete a single answer from the user's JSON file. Returns True if deleted."""
    try:
        file_path = pdn_file_path.get_user_file_path(email, f"{email}_answers.json")
        data = _load_json_data(file_path)
        key = str(question_number)
        if key in data:
            del data[key]
            _save_with_lock(file_path, data)
            return True
        return False
    except Exception as e:
        logger.error(f"Failed to delete answer for {email}, question {question_number}: {e}")
        return False


def save_user_metadata(metadata: Dict[str, Any], email: str = None) -> None:
    """Save user metadata to JSON file and CSV."""
    if not email:
        raise ValueError("Email is required")
    
    try:
        UserMetadataHandler().append_user_metadata(metadata)
        
        file_path = pdn_file_path.get_user_file_path(email, f"{email}_answers.json")
        data = _load_json_data(file_path)
        
        metadata['timestamp'] = datetime.now().strftime("%Y_%m_%d_%H_%M")
        data['metadata'] = metadata
        _save_with_lock(file_path, data)
    except Exception as e:
        logger.error(f"Failed to save metadata for {email}: {e}")
        raise
