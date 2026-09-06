"""Tests for conversation history management."""

import json
import pytest
from app.utils.conversation_history import ConversationHistory


@pytest.fixture
def history(tmp_path):
    """Create a ConversationHistory instance with tmp_path storage."""
    return ConversationHistory(storage_dir=str(tmp_path))


class TestAddMessage:
    """Tests for add_message()."""

    def test_stores_message_correctly(self, history):
        """Adding a message should store it in the user's file."""
        history.add_message("user1", "Hello", "Hi there!", "TestUser")
        result = history.get_history("user1")
        assert len(result) == 1
        assert result[0]['message'] == "Hello"
        assert result[0]['response'] == "Hi there!"
        assert result[0]['user_name'] == "TestUser"

    def test_stores_multiple_messages(self, history):
        """Multiple messages should all be stored."""
        history.add_message("user1", "msg1", "resp1")
        history.add_message("user1", "msg2", "resp2")
        history.add_message("user1", "msg3", "resp3")
        result = history.get_history("user1")
        assert len(result) == 3

    def test_different_users_separate(self, history):
        """Different users should have separate histories."""
        history.add_message("user1", "msg1", "resp1")
        history.add_message("user2", "msg2", "resp2")
        assert len(history.get_history("user1")) == 1
        assert len(history.get_history("user2")) == 1


class TestGetHistory:
    """Tests for get_history()."""

    def test_returns_empty_list_for_new_user(self, history):
        """New user should have empty history."""
        result = history.get_history("nonexistent_user")
        assert result == []

    def test_returns_stored_messages(self, history):
        """Should return previously stored messages."""
        history.add_message("user1", "Hello", "World")
        result = history.get_history("user1")
        assert len(result) == 1
        assert result[0]['message'] == "Hello"


class TestGetConversationContext:
    """Tests for get_conversation_context()."""

    def test_formats_correctly(self, history):
        """Context should be formatted as User/Assistant pairs."""
        history.add_message("user1", "What is PDN?", "PDN is a personality code.")
        context = history.get_conversation_context("user1")
        assert "User: What is PDN?" in context
        assert "Assistant: PDN is a personality code." in context

    def test_empty_history_returns_empty_string(self, history):
        """No history should return empty string."""
        context = history.get_conversation_context("nonexistent")
        assert context == ""

    def test_multiple_messages_formatted(self, history):
        """Multiple messages should all appear in context."""
        history.add_message("user1", "msg1", "resp1")
        history.add_message("user1", "msg2", "resp2")
        context = history.get_conversation_context("user1")
        assert "User: msg1" in context
        assert "Assistant: resp1" in context
        assert "User: msg2" in context
        assert "Assistant: resp2" in context


class TestClearHistory:
    """Tests for clear_history()."""

    def test_clear_returns_true(self, history):
        """clear_history should return True."""
        history.add_message("user1", "msg", "resp")
        result = history.clear_history("user1")
        assert result is True

    def test_clear_nonexistent_user(self, history):
        """Clearing nonexistent user should still return True."""
        result = history.clear_history("nonexistent")
        assert result is True


class TestMaxHistoryLimit:
    """Tests for max history limit (10 messages)."""

    def test_max_history_limit(self, history):
        """Should keep only the last 10 messages."""
        for i in range(15):
            history.add_message("user1", f"msg{i}", f"resp{i}")
        result = history.get_history("user1")
        assert len(result) == 10
        # Should keep the last 10 (indices 5-14)
        assert result[0]['message'] == "msg5"
        assert result[-1]['message'] == "msg14"

    def test_exactly_at_limit(self, history):
        """Exactly 10 messages should all be kept."""
        for i in range(10):
            history.add_message("user1", f"msg{i}", f"resp{i}")
        result = history.get_history("user1")
        assert len(result) == 10
        assert result[0]['message'] == "msg0"
