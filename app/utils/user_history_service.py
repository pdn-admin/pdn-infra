"""
User History Service Module

This module provides persistence for per-user conversation history summaries.
It stores an encrypted JSON payload in each user's saved_results directory,
enabling conversation context to survive across sessions.

Key features:
- Structured payload with schema versioning
- Base64 encryption/decryption (MVP obfuscation)
- Atomic file writes with file locking
- Graceful degradation on load failures
- Path traversal prevention
- Context injection into conversation messages
"""

import base64
import fcntl
import json
import logging
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.utils.pdn_file_path import PDNFilePath


SCHEMA_VERSION = "1.0"
HISTORY_FILENAME_SUFFIX = "_history.enc"

_HISTORY_CONTEXT_HEADER = "[Previous Session Summary]"
_HISTORY_CONTEXT_FOOTER = "[End Previous Session Summary]"

# Only allow alphanumeric, dots, hyphens, underscores, @, +
_SAFE_USER_ID_PATTERN = re.compile(r"^[a-zA-Z0-9._@+\-]+$")


@dataclass
class UserHistoryPayload:
    """Structured payload persisted to disk."""

    schema_version: str
    user_id: str
    updated_at: str  # ISO 8601
    summary: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "user_id": self.user_id,
            "updated_at": self.updated_at,
            "summary": self.summary,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserHistoryPayload":
        return cls(
            schema_version=data["schema_version"],
            user_id=data["user_id"],
            updated_at=data["updated_at"],
            summary=data["summary"],
            metadata=data.get("metadata", {}),
        )


class UserHistoryService:
    """Service for persisting and loading per-user conversation history summaries."""

    def __init__(self, base_dir: Optional[str] = None):
        """
        Initialize UserHistoryService.

        Args:
            base_dir: Base directory for saved results.
                      Defaults to SAVED_RESULTS_DIR env var or 'saved_results'.
        """
        self.base_dir = Path(base_dir or os.getenv("SAVED_RESULTS_DIR", "saved_results"))
        self.logger = logging.getLogger(__name__)

    def validate_user_id(self, user_id: str) -> bool:
        """Validate user_id is safe for filesystem use."""
        if not user_id or not user_id.strip():
            return False
        if ".." in user_id:
            return False
        if "/" in user_id or "\\" in user_id:
            return False
        if "\x00" in user_id:
            return False
        if not _SAFE_USER_ID_PATTERN.match(user_id):
            return False
        return True

    def _build_history_filename(self, user_id: str) -> str:
        """Build filename: email without last domain suffix + _history.enc.

        Examples:
            tomergur@gmail.com -> tomergur@gmail_history.enc
            user@domain.co.il -> user@domain.co_history.enc
            noemail -> noemail_history.enc
            user+tag@gmail.com -> user+tag@gmail_history.enc
        """
        if "@" in user_id and "." in user_id.split("@")[-1]:
            name = user_id.rsplit(".", 1)[0]
        else:
            name = user_id
        return f"{name}{HISTORY_FILENAME_SUFFIX}"

    def resolve_user_history_path(self, user_id: str) -> Path:
        """Resolve the path to <email>_history.enc within the user's folder.

        Uses PDNFilePath.get_user_dir() to match the existing folder convention
        used by diagnose answers and audio files (saved_results/<safe_email>/).
        """
        # Reuse existing PDNFilePath logic for folder resolution
        pdn_path = PDNFilePath(base_dir=str(self.base_dir))
        user_dir = pdn_path.get_user_dir(user_id)
        filename = self._build_history_filename(user_id)
        resolved = (user_dir / filename).resolve()

        # Final safety check: ensure resolved path is under base_dir
        if not str(resolved).startswith(str(self.base_dir.resolve())):
            raise ValueError("Path traversal detected")

        # Create parent directory if it does not exist
        resolved.parent.mkdir(parents=True, exist_ok=True)

        return resolved

    def encrypt_payload(self, payload_json: str) -> bytes:
        """MVP protection: base64 encode the JSON payload."""
        return base64.b64encode(payload_json.encode("utf-8"))

    def decrypt_payload(self, data: bytes) -> Optional[str]:
        """MVP protection: base64 decode back to JSON string."""
        try:
            return base64.b64decode(data).decode("utf-8")
        except Exception:
            return None

    def save_user_history(
        self,
        user_id: str,
        summary: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Persist user history summary with atomic write."""
        # Step 1: Validate inputs
        if not self.validate_user_id(user_id):
            self.logger.warning("Invalid user_id rejected")
            return False
        if not summary or not summary.strip():
            return False

        # Step 2: Build payload
        payload = UserHistoryPayload(
            schema_version=SCHEMA_VERSION,
            user_id=user_id,
            updated_at=datetime.now(timezone.utc).isoformat(),
            summary=summary,
            metadata=metadata or {},
        )

        # Step 3: Serialize and encrypt
        payload_json = json.dumps(payload.to_dict(), ensure_ascii=False)
        encrypted = self.encrypt_payload(payload_json)

        # Step 4: Resolve target path
        target_path = self.resolve_user_history_path(user_id)

        # Step 5: Atomic write with file lock
        lock_path = target_path.with_suffix(".lock")
        try:
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            with open(lock_path, "w") as lock_file:
                fcntl.flock(lock_file, fcntl.LOCK_EX)
                try:
                    # Write to temp file in same directory (same filesystem for rename)
                    fd, tmp_path = tempfile.mkstemp(
                        dir=target_path.parent, suffix=".tmp"
                    )
                    try:
                        with os.fdopen(fd, "wb") as tmp_file:
                            tmp_file.write(encrypted)
                            tmp_file.flush()
                            os.fsync(tmp_file.fileno())
                        # Atomic rename
                        Path(tmp_path).replace(target_path)
                    except Exception:
                        # Clean up temp file on failure
                        Path(tmp_path).unlink(missing_ok=True)
                        raise
                finally:
                    fcntl.flock(lock_file, fcntl.LOCK_UN)
            # Clean up lock file after successful write
            lock_path.unlink(missing_ok=True)
            return True
        except Exception as e:
            self.logger.error("Failed to save user history: %s", e)
            return False

    def load_user_history(self, user_id: str) -> Optional[UserHistoryPayload]:
        """Load and decrypt user history. Returns None on any failure."""
        if not self.validate_user_id(user_id):
            return None

        target_path = self.resolve_user_history_path(user_id)

        if not target_path.exists():
            return None

        try:
            encrypted_data = target_path.read_bytes()
            if not encrypted_data:
                return None

            payload_json = self.decrypt_payload(encrypted_data)
            if payload_json is None:
                self.logger.warning("Decryption failed for user history")
                return None

            data = json.loads(payload_json)
            return UserHistoryPayload.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            self.logger.warning("Corrupted user history file: %s", e)
            return None
        except OSError as e:
            self.logger.warning("IO error reading user history: %s", e)
            return None

    def delete_user_history(self, user_id: str) -> bool:
        """Delete user history file. Returns True on success or if file absent."""
        if not self.validate_user_id(user_id):
            self.logger.warning("Invalid user_id in delete request")
            return False

        try:
            target_path = self.resolve_user_history_path(user_id)
            target_path.unlink(missing_ok=True)
            # Also clean up lock file if present
            target_path.with_suffix(".lock").unlink(missing_ok=True)
            return True
        except OSError as e:
            self.logger.error("Failed to delete user history: %s", e)
            return False

    def inject_user_history_into_context(
        self,
        payload: Optional[UserHistoryPayload],
        messages: List[Dict[str, str]],
    ) -> List[Dict[str, str]]:
        """Insert persisted summary as a system message into the conversation context.

        Inserts after the first system message (if any), before user messages.
        Works with LangChain-style message dicts.
        """
        if payload is None or not payload.summary.strip():
            return messages

        history_message = {
            "role": "system",
            "content": (
                f"{_HISTORY_CONTEXT_HEADER}\n"
                f"{payload.summary}\n"
                f"{_HISTORY_CONTEXT_FOOTER}"
            ),
        }

        # Insert after the first system message, before user messages
        insert_idx = 0
        for i, msg in enumerate(messages):
            if msg.get("role") == "system":
                insert_idx = i + 1
                break

        result = messages.copy()
        result.insert(insert_idx, history_message)
        return result
