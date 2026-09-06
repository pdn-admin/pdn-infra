"""Tests for conversation statistics tracking."""

import json
import threading
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from datetime import datetime

from app.utils.conversation_stats import ConversationStats


@pytest.fixture
def stats_instance(tmp_path, monkeypatch):
    """Create a ConversationStats instance with tmp_path storage."""
    stats_file = tmp_path / "conversation_stats.json"
    # Patch PDNFilePath to use tmp_path
    with patch('app.utils.conversation_stats.PDNFilePath') as mock_pdn:
        mock_pdn_instance = MagicMock()
        mock_pdn_instance.get_base_dir.return_value = tmp_path
        mock_pdn.return_value = mock_pdn_instance
        stats = ConversationStats()
    # Override the stats_file to use tmp_path
    stats.stats_file = stats_file
    return stats


class TestIncrementConversation:
    """Tests for increment_conversation()."""

    def test_creates_file_on_first_increment(self, stats_instance):
        """First increment should create the stats file."""
        assert not stats_instance.stats_file.exists()
        stats_instance.increment_conversation("user@test.com")
        assert stats_instance.stats_file.exists()

    def test_increments_count(self, stats_instance):
        """Multiple increments should increase count."""
        stats_instance.increment_conversation("user@test.com")
        stats_instance.increment_conversation("user@test.com")
        stats_instance.increment_conversation("user@test.com")

        with open(stats_instance.stats_file, 'r') as f:
            data = json.load(f)
        today = datetime.now().strftime('%Y-%m-%d')
        assert data[today]["user@test.com"] == 3

    def test_multiple_users(self, stats_instance):
        """Different users should have separate counts."""
        stats_instance.increment_conversation("alice@test.com")
        stats_instance.increment_conversation("bob@test.com")
        stats_instance.increment_conversation("alice@test.com")

        with open(stats_instance.stats_file, 'r') as f:
            data = json.load(f)
        today = datetime.now().strftime('%Y-%m-%d')
        assert data[today]["alice@test.com"] == 2
        assert data[today]["bob@test.com"] == 1


class TestGetAllStats:
    """Tests for get_all_stats()."""

    def test_returns_correct_date_range(self, stats_instance):
        """Should return stats for the specified number of days."""
        stats_instance.increment_conversation("user@test.com")
        result = stats_instance.get_all_stats(days=7)
        assert len(result) == 7
        today = datetime.now().strftime('%Y-%m-%d')
        assert today in result

    def test_empty_stats_returns_empty_dicts(self, stats_instance):
        """Empty stats file should return empty dicts for each day."""
        result = stats_instance.get_all_stats(days=3)
        assert len(result) == 3
        for day_stats in result.values():
            assert day_stats == {}

    def test_returns_data_for_today(self, stats_instance):
        """Should include today's data."""
        stats_instance.increment_conversation("user@test.com")
        result = stats_instance.get_all_stats(days=1)
        today = datetime.now().strftime('%Y-%m-%d')
        assert result[today] == {"user@test.com": 1}


class TestConcurrentIncrements:
    """Tests for thread safety."""

    def test_concurrent_increments_dont_corrupt(self, stats_instance):
        """Concurrent increments should not corrupt the data file."""
        threads = []
        for i in range(10):
            t = threading.Thread(
                target=stats_instance.increment_conversation,
                args=(f"user{i % 3}@test.com",)
            )
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # File should be valid JSON
        with open(stats_instance.stats_file, 'r') as f:
            data = json.load(f)
        today = datetime.now().strftime('%Y-%m-%d')
        assert today in data


class TestCorruptedFile:
    """Tests for handling corrupted JSON."""

    def test_corrupted_json_file_handled(self, stats_instance):
        """Corrupted JSON should be handled gracefully."""
        # Write invalid JSON
        stats_instance.stats_file.parent.mkdir(parents=True, exist_ok=True)
        stats_instance.stats_file.write_text("not valid json {{{")

        # Should not raise, should recover
        stats_instance.increment_conversation("user@test.com")

        # File should now be valid
        with open(stats_instance.stats_file, 'r') as f:
            data = json.load(f)
        today = datetime.now().strftime('%Y-%m-%d')
        assert data[today]["user@test.com"] == 1

    def test_read_corrupted_returns_empty(self, stats_instance):
        """Reading corrupted file should return empty dict."""
        stats_instance.stats_file.parent.mkdir(parents=True, exist_ok=True)
        stats_instance.stats_file.write_text("corrupted content")
        result = stats_instance.get_all_stats(days=1)
        today = datetime.now().strftime('%Y-%m-%d')
        assert result[today] == {}
