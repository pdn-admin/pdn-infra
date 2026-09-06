"""Property-based tests for UserHistoryService context injection.

Validates: Requirements 7, 10, 11
"""

import tempfile

import pytest
from hypothesis import given, assume, settings
from hypothesis import strategies as st

from app.utils.user_history_service import UserHistoryService, UserHistoryPayload


@pytest.fixture
def service(tmp_path):
    """Create a UserHistoryService with a temporary base directory."""
    return UserHistoryService(base_dir=str(tmp_path))


# --- Strategies ---

# Strategy for message roles
_ROLES = st.sampled_from(["system", "user", "assistant"])

# Strategy for non-system roles
_NON_SYSTEM_ROLES = st.sampled_from(["user", "assistant"])


@st.composite
def message(draw, role=None):
    """Generate a single message dict with role and content."""
    msg_role = role if role is not None else draw(_ROLES)
    content = draw(st.text(min_size=1, max_size=100))
    assume(content.strip() != "")
    return {"role": msg_role, "content": content}


@st.composite
def message_list(draw, min_size=1, max_size=10):
    """Generate a list of messages with various roles."""
    size = draw(st.integers(min_value=min_size, max_value=max_size))
    messages = []
    for _ in range(size):
        messages.append(draw(message()))
    return messages


@st.composite
def message_list_with_system_first(draw, min_size=2, max_size=10):
    """Generate a message list that starts with a system message."""
    system_msg = draw(message(role="system"))
    rest_size = draw(st.integers(min_value=min_size - 1, max_value=max_size - 1))
    rest = []
    for _ in range(rest_size):
        rest.append(draw(message()))
    return [system_msg] + rest


@st.composite
def message_list_with_multiple_system(draw, min_size=3, max_size=10):
    """Generate a message list with at least two system messages at the start."""
    sys1 = draw(message(role="system"))
    sys2 = draw(message(role="system"))
    rest_size = draw(st.integers(min_value=1, max_value=max_size - 2))
    rest = []
    for _ in range(rest_size):
        rest.append(draw(message(role=draw(_NON_SYSTEM_ROLES))))
    return [sys1, sys2] + rest


@st.composite
def message_list_no_system(draw, min_size=1, max_size=10):
    """Generate a message list with no system messages."""
    size = draw(st.integers(min_value=min_size, max_value=max_size))
    messages = []
    for _ in range(size):
        messages.append(draw(message(role=draw(_NON_SYSTEM_ROLES))))
    return messages


@st.composite
def valid_payload(draw):
    """Generate a valid UserHistoryPayload with non-empty summary."""
    summary = draw(st.text(min_size=1, max_size=200))
    assume(summary.strip() != "")
    return UserHistoryPayload(
        schema_version="1.0",
        user_id="test@example.com",
        updated_at="2024-01-01T00:00:00+00:00",
        summary=summary,
        metadata={},
    )


# --- Property 7: Context injection preserves original messages ---

class TestProperty7ContextInjectionPreservesMessages:
    """Property 7: Context injection preserves original messages — no messages removed or modified.

    **Validates: Requirements 7**
    """

    @given(payload=valid_payload(), messages=message_list(min_size=1, max_size=10))
    @settings(max_examples=200)
    def test_all_original_messages_present(self, payload, messages):
        """Injecting history never removes any original messages."""
        service = UserHistoryService(base_dir="/tmp/test_prop7")
        result = service.inject_user_history_into_context(payload, messages)

        # All original messages must still be present
        for msg in messages:
            assert msg in result

    @given(payload=valid_payload(), messages=message_list(min_size=1, max_size=10))
    @settings(max_examples=200)
    def test_exactly_one_message_added(self, payload, messages):
        """Injecting history adds exactly one message to the list."""
        service = UserHistoryService(base_dir="/tmp/test_prop7")
        result = service.inject_user_history_into_context(payload, messages)

        assert len(result) == len(messages) + 1

    @given(payload=valid_payload(), messages=message_list(min_size=1, max_size=10))
    @settings(max_examples=200)
    def test_original_message_order_preserved(self, payload, messages):
        """Original messages maintain their relative order after injection."""
        service = UserHistoryService(base_dir="/tmp/test_prop7")
        result = service.inject_user_history_into_context(payload, messages)

        # Extract original messages from result (filter out the injected one)
        original_in_result = [
            msg for msg in result
            if "[Previous Session Summary]" not in msg.get("content", "")
        ]
        assert original_in_result == messages


# --- Property 10: Context injection with empty messages ---

class TestProperty10ContextInjectionEdgeCases:
    """Property 10: Context injection handles edge cases correctly.

    **Validates: Requirements 10**
    """

    @given(messages=message_list(min_size=0, max_size=10))
    @settings(max_examples=100)
    def test_none_payload_returns_unchanged(self, messages):
        """When payload is None, messages are returned unchanged."""
        service = UserHistoryService(base_dir="/tmp/test_prop10")
        result = service.inject_user_history_into_context(None, messages)
        assert result == messages

    @given(messages=message_list(min_size=0, max_size=10))
    @settings(max_examples=100)
    def test_empty_summary_returns_unchanged(self, messages):
        """When payload has empty/whitespace summary, messages are returned unchanged."""
        service = UserHistoryService(base_dir="/tmp/test_prop10")
        empty_payload = UserHistoryPayload(
            schema_version="1.0",
            user_id="test@example.com",
            updated_at="2024-01-01T00:00:00+00:00",
            summary="   ",
            metadata={},
        )
        result = service.inject_user_history_into_context(empty_payload, messages)
        assert result == messages

    @given(payload=valid_payload(), messages=message_list_no_system(min_size=1, max_size=5))
    @settings(max_examples=100)
    def test_no_system_message_inserts_at_index_0(self, payload, messages):
        """When no system message exists, history is inserted at index 0."""
        service = UserHistoryService(base_dir="/tmp/test_prop10")
        result = service.inject_user_history_into_context(payload, messages)

        assert result[0]["role"] == "system"
        assert "[Previous Session Summary]" in result[0]["content"]

    @given(payload=valid_payload())
    @settings(max_examples=50)
    def test_empty_list_with_payload_inserts_at_0(self, payload):
        """When messages list is empty and payload is valid, inserts at index 0."""
        service = UserHistoryService(base_dir="/tmp/test_prop10")
        result = service.inject_user_history_into_context(payload, [])

        assert len(result) == 1
        assert result[0]["role"] == "system"
        assert "[Previous Session Summary]" in result[0]["content"]


# --- Property 11: Context injection with multiple system messages ---

class TestProperty11MultipleSystemMessages:
    """Property 11: Context injection inserts after FIRST system message only.

    **Validates: Requirements 11**
    """

    @given(messages=message_list_with_multiple_system(min_size=3, max_size=10), payload=valid_payload())
    @settings(max_examples=200)
    def test_inserts_after_first_system_message(self, messages, payload):
        """With multiple system messages, injection happens after the FIRST one only."""
        service = UserHistoryService(base_dir="/tmp/test_prop11")
        result = service.inject_user_history_into_context(payload, messages)

        # First message should be the original first system message (unchanged)
        assert result[0] == messages[0]

        # Second message should be the injected history
        assert result[1]["role"] == "system"
        assert "[Previous Session Summary]" in result[1]["content"]

        # Third message should be the original second system message
        assert result[2] == messages[1]

    @given(messages=message_list_with_system_first(min_size=2, max_size=10), payload=valid_payload())
    @settings(max_examples=200)
    def test_single_system_message_inserts_after_it(self, messages, payload):
        """With a single system message at start, injection happens right after it."""
        service = UserHistoryService(base_dir="/tmp/test_prop11")
        result = service.inject_user_history_into_context(payload, messages)

        # First message is the original system message
        assert result[0] == messages[0]

        # Second message is the injected history
        assert result[1]["role"] == "system"
        assert "[Previous Session Summary]" in result[1]["content"]

    @given(messages=message_list_with_multiple_system(min_size=3, max_size=10), payload=valid_payload())
    @settings(max_examples=100)
    def test_only_one_history_message_injected(self, messages, payload):
        """Even with multiple system messages, only one history message is injected."""
        service = UserHistoryService(base_dir="/tmp/test_prop11")
        result = service.inject_user_history_into_context(payload, messages)

        history_messages = [
            msg for msg in result
            if "[Previous Session Summary]" in msg.get("content", "")
        ]
        assert len(history_messages) == 1
