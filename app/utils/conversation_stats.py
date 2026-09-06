"""Conversation statistics tracking utility.

Uses fcntl file locking for multi-worker (gunicorn) safety.
Note: fcntl is Linux/macOS only — not compatible with Windows.
"""

import fcntl
import json
import logging
from datetime import datetime, timedelta
import threading

from app.utils.pdn_file_path import PDNFilePath

logger = logging.getLogger(__name__)


class ConversationStats:
    """Track daily conversation counts per user with file-level locking."""

    def __init__(self):
        pdn_file_path = PDNFilePath()
        user_dir = pdn_file_path.get_base_dir()
        self.stats_file = user_dir / "conversation_stats.json"
        logger.info("conversation stats file path: %s", self.stats_file)
        self._lock = threading.RLock()

    def _read_locked(self) -> dict:
        """Read stats from file with exclusive file lock."""
        if not self.stats_file.exists():
            return {}
        try:
            with open(self.stats_file, 'r') as f:
                fcntl.flock(f, fcntl.LOCK_SH)
                content = f.read()
                return json.loads(content) if content.strip() else {}
        except (json.JSONDecodeError, ValueError, OSError) as e:
            logger.error("Failed to load conversation stats: %s", e)
            return {}

    def increment_conversation(self, email: str):
        """Increment conversation count for user today. File-locked for multi-worker safety."""
        today = datetime.now().strftime('%Y-%m-%d')
        with self._lock:
            self.stats_file.parent.mkdir(parents=True, exist_ok=True)
            try:
                with open(self.stats_file, 'a+') as f:
                    fcntl.flock(f, fcntl.LOCK_EX)
                    f.seek(0)
                    content = f.read()
                    try:
                        stats = json.loads(content) if content.strip() else {}
                    except (json.JSONDecodeError, ValueError):
                        stats = {}

                    if today not in stats:
                        stats[today] = {}
                    stats[today][email] = stats[today].get(email, 0) + 1

                    f.seek(0)
                    f.truncate()
                    json.dump(stats, f, indent=2)
            except Exception as e:
                logger.error("Failed to increment conversation for %s: %s", email, e)

    def get_all_stats(self, days: int = 7) -> dict:
        """Get all user stats over specified days."""
        with self._lock:
            today = datetime.now().date()
            stats = self._read_locked()
            return {
                (today - timedelta(days=i)).strftime('%Y-%m-%d'):
                    stats.get((today - timedelta(days=i)).strftime('%Y-%m-%d'), {})
                for i in range(days)
            }


# Global instance
conversation_stats = ConversationStats()
