"""Property tests for BasePDNAgent: initialization, daily limits, token usage, input sanitization,
and conversation history summarization lifecycle.

**Validates: Requirements 1.2**
**Validates: Requirements 8.3, 8.4**
**Validates: Requirements 8.5**
**Validates: Requirements 8.8**
**Validates: Correctness Property 7**
**Validates: Correctness Property 17**
**Validates: Correctness Property 18**
**Validates: Correctness Property 20**

Verifies that RelationshipAgent (a BasePDNAgent subclass) properly initializes
with the shared LLM infrastructure: llm, conversation_history, and history_service.

Also verifies daily conversation limit enforcement:
- Non-exempt users at/above limit → True
- Exempt users → always False regardless of count

Also verifies input sanitization neutralizes injection patterns:
- XML-like tags → angle brackets replaced with full-width equivalents

Also verifies conversation history summarization lifecycle:
- When turn count or token count exceeds threshold → raw ≤ RAW_TURNS_TO_KEEP, summary non-empty
"""

import re

import pytest
from collections import defaultdict
from datetime import datetime
from unittest.mock import patch, MagicMock

import tempfile

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.pdn_relationships.agents.base_pdn_agent import BasePDNAgent, BaseAgentConfig, UserHistory
from app.pdn_relationships.agents.relationship_agent import RelationshipAgent


@pytest.fixture
def mock_config():
    """Mock Config class for LLM initialization."""
    config = MagicMock()
    config.LLM_PROVIDER = 'openai'
    config.OPENAI_API_KEY = 'test-key'
    config.ANTHROPIC_API_KEY = 'test-key'
    config.OPENAI_MODEL = 'gpt-4o-mini'
    config.ANTHROPIC_MODEL = 'claude-sonnet-4-20250514'
    return config


@pytest.fixture
def relationship_agent(tmp_path, monkeypatch, mock_config):
    """Create a RelationshipAgent with mocked LLM providers."""
    monkeypatch.setenv('SAVED_RESULTS_DIR', str(tmp_path))
    with patch('app.pdn_relationships.agents.base_pdn_agent.Config', return_value=mock_config):
        with patch('app.pdn_relationships.agents.base_pdn_agent.ChatOpenAI') as mock_openai:
            with patch('app.pdn_relationships.agents.base_pdn_agent.ChatAnthropic'):
                mock_llm = MagicMock()
                mock_openai.return_value = mock_llm
                agent = RelationshipAgent()
    return agent


# --- Provider strategy for hypothesis ---
llm_provider_strategy = st.sampled_from(['openai', 'anthropic'])


class TestBasePDNAgentSubclassInitialization:
    """Property 7: BasePDNAgent subclasses share LLM initialization."""

    def test_relationship_agent_has_llm_attribute(self, relationship_agent):
        """RelationshipAgent must have an llm attribute that is not None."""
        assert hasattr(relationship_agent, 'llm')
        assert relationship_agent.llm is not None

    def test_relationship_agent_has_conversation_history(self, relationship_agent):
        """RelationshipAgent must have conversation_history as a defaultdict."""
        assert hasattr(relationship_agent, 'conversation_history')
        assert isinstance(relationship_agent.conversation_history, defaultdict)

    def test_relationship_agent_has_history_service(self, relationship_agent):
        """RelationshipAgent must have a history_service that is not None."""
        assert hasattr(relationship_agent, 'history_service')
        assert relationship_agent.history_service is not None

    def test_relationship_agent_is_base_pdn_agent_subclass(self, relationship_agent):
        """RelationshipAgent must be an instance of BasePDNAgent."""
        assert isinstance(relationship_agent, BasePDNAgent)

    @given(provider=llm_provider_strategy)
    @settings(max_examples=10, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_initialization_works_for_any_supported_provider(self, provider):
        """Property: For any supported LLM provider, RelationshipAgent initializes
        with llm, conversation_history, and history_service attributes."""
        mock_cfg = MagicMock()
        mock_cfg.LLM_PROVIDER = provider
        mock_cfg.OPENAI_API_KEY = 'test-key'
        mock_cfg.ANTHROPIC_API_KEY = 'test-key'
        mock_cfg.OPENAI_MODEL = 'gpt-4o-mini'
        mock_cfg.ANTHROPIC_MODEL = 'claude-sonnet-4-20250514'

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch('app.pdn_relationships.agents.base_pdn_agent.Config', return_value=mock_cfg):
                with patch('app.pdn_relationships.agents.base_pdn_agent.ChatOpenAI') as mock_openai:
                    with patch('app.pdn_relationships.agents.base_pdn_agent.ChatAnthropic') as mock_anthropic:
                        mock_openai.return_value = MagicMock()
                        mock_anthropic.return_value = MagicMock()
                        with patch.dict('os.environ', {'SAVED_RESULTS_DIR': tmp_dir}):
                            agent = RelationshipAgent()

        # Property assertions
        assert hasattr(agent, 'llm')
        assert agent.llm is not None

        assert hasattr(agent, 'conversation_history')
        assert isinstance(agent.conversation_history, defaultdict)

        assert hasattr(agent, 'history_service')
        assert agent.history_service is not None

    def test_conversation_history_default_factory_produces_user_history(self, relationship_agent):
        """Accessing a new key in conversation_history should produce a UserHistory."""
        hist = relationship_agent.conversation_history["new_user"]
        assert isinstance(hist, UserHistory)
        assert hist.raw == []
        assert hist.summary == ""


class TestTokenUsageAccumulationInvariant:
    """Property 19: Token Usage Accumulation Invariant.

    **Validates: Requirements 8.6**

    For any sequence of N LLM responses tracked via _track_usage for the same user
    on the same day, stored input_tokens = sum of individual input_tokens,
    output_tokens = sum of individual output_tokens, and calls = N.
    """

    @given(
        token_entries=st.lists(
            st.fixed_dictionaries({
                'input_tokens': st.integers(min_value=0, max_value=100000),
                'output_tokens': st.integers(min_value=0, max_value=50000),
            }),
            min_size=1,
            max_size=20,
        )
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_token_accumulation_sums_correctly(self, token_entries):
        """Property: For N tracked responses, stored tokens = sum of individual tokens, calls = N."""
        mock_cfg = MagicMock()
        mock_cfg.LLM_PROVIDER = 'openai'
        mock_cfg.OPENAI_API_KEY = 'test-key'
        mock_cfg.ANTHROPIC_API_KEY = 'test-key'
        mock_cfg.OPENAI_MODEL = 'gpt-4o-mini'
        mock_cfg.ANTHROPIC_MODEL = 'claude-sonnet-4-20250514'

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch('app.pdn_relationships.agents.base_pdn_agent.Config', return_value=mock_cfg):
                with patch('app.pdn_relationships.agents.base_pdn_agent.ChatOpenAI') as mock_openai:
                    with patch('app.pdn_relationships.agents.base_pdn_agent.ChatAnthropic') as mock_anthropic:
                        mock_openai.return_value = MagicMock()
                        mock_anthropic.return_value = MagicMock()
                        with patch.dict('os.environ', {'SAVED_RESULTS_DIR': tmp_dir}):
                            agent = BasePDNAgent()

            # Clear any pre-existing usage data
            agent.token_usage = {}

            # Patch _save_usage_file to avoid file I/O during test
            with patch.object(agent, '_save_usage_file'):
                user_name = "test_user"

                # Track each response
                for entry in token_entries:
                    mock_response = MagicMock()
                    mock_response.usage_metadata = {
                        'input_tokens': entry['input_tokens'],
                        'output_tokens': entry['output_tokens'],
                        'input_token_details': {
                            'cache_creation': 0,
                            'cache_read': 0,
                        },
                    }
                    agent._track_usage(user_name, mock_response)

            # Verify accumulation invariants
            today = datetime.now().strftime('%Y-%m-%d')
            day_data = agent.token_usage[user_name][today]

            expected_input = sum(e['input_tokens'] for e in token_entries)
            expected_output = sum(e['output_tokens'] for e in token_entries)
            expected_calls = len(token_entries)

            assert day_data['input_tokens'] == expected_input, (
                f"input_tokens mismatch: got {day_data['input_tokens']}, expected {expected_input}"
            )
            assert day_data['output_tokens'] == expected_output, (
                f"output_tokens mismatch: got {day_data['output_tokens']}, expected {expected_output}"
            )
            assert day_data['calls'] == expected_calls, (
                f"calls mismatch: got {day_data['calls']}, expected {expected_calls}"
            )



class TestDailyConversationLimitEnforcement:
    """Property 17: Daily Conversation Limit Enforcement.

    **Validates: Requirements 8.5**

    For any non-exempt user whose conversation count equals or exceeds their daily limit,
    _has_exceeded_daily_limit returns True. For any exempt user (in EXEMPT_USERS),
    the function always returns False regardless of count.
    """

    @given(
        count=st.integers(min_value=0, max_value=200),
        limit=st.integers(min_value=1, max_value=100),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_non_exempt_user_at_or_above_limit_returns_true(self, count, limit):
        """Property: For any non-exempt user at or above the daily limit,
        _has_exceeded_daily_limit returns True."""
        mock_cfg = MagicMock()
        mock_cfg.LLM_PROVIDER = 'openai'
        mock_cfg.OPENAI_API_KEY = 'test-key'
        mock_cfg.ANTHROPIC_API_KEY = 'test-key'
        mock_cfg.OPENAI_MODEL = 'gpt-4o-mini'
        mock_cfg.ANTHROPIC_MODEL = 'claude-sonnet-4-20250514'

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch('app.pdn_relationships.agents.base_pdn_agent.Config', return_value=mock_cfg):
                with patch('app.pdn_relationships.agents.base_pdn_agent.ChatOpenAI') as mock_openai:
                    with patch('app.pdn_relationships.agents.base_pdn_agent.ChatAnthropic'):
                        mock_openai.return_value = MagicMock()
                        with patch.dict('os.environ', {'SAVED_RESULTS_DIR': tmp_dir}):
                            agent = RelationshipAgent()

            # Use a non-exempt user name (not in EXEMPT_USERS)
            user_name = "test_user_non_exempt"
            assert user_name not in BasePDNAgent.EXEMPT_USERS

            # Set the conversation count to the generated value
            agent.user_conversations[user_name] = {
                'count': count,
                'last_reset': datetime.now().replace(hour=0, minute=0, second=0, microsecond=0),
            }

            result = agent._has_exceeded_daily_limit(user_name, max_conversations_per_day=limit)

            if count >= limit:
                assert result is True, (
                    f"Expected True for non-exempt user with count={count} >= limit={limit}"
                )
            else:
                assert result is False, (
                    f"Expected False for non-exempt user with count={count} < limit={limit}"
                )

    @given(
        count=st.integers(min_value=0, max_value=500),
        limit=st.integers(min_value=1, max_value=100),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_exempt_user_always_returns_false(self, count, limit):
        """Property: For any exempt user (in EXEMPT_USERS), _has_exceeded_daily_limit
        always returns False regardless of conversation count."""
        mock_cfg = MagicMock()
        mock_cfg.LLM_PROVIDER = 'openai'
        mock_cfg.OPENAI_API_KEY = 'test-key'
        mock_cfg.ANTHROPIC_API_KEY = 'test-key'
        mock_cfg.OPENAI_MODEL = 'gpt-4o-mini'
        mock_cfg.ANTHROPIC_MODEL = 'claude-sonnet-4-20250514'

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch('app.pdn_relationships.agents.base_pdn_agent.Config', return_value=mock_cfg):
                with patch('app.pdn_relationships.agents.base_pdn_agent.ChatOpenAI') as mock_openai:
                    with patch('app.pdn_relationships.agents.base_pdn_agent.ChatAnthropic'):
                        mock_openai.return_value = MagicMock()
                        with patch.dict('os.environ', {'SAVED_RESULTS_DIR': tmp_dir}):
                            agent = RelationshipAgent()

            # Use an exempt user from EXEMPT_USERS
            exempt_user = list(BasePDNAgent.EXEMPT_USERS)[0]  # 'פנינה'

            # Set the conversation count to the generated value (even very high)
            agent.user_conversations[exempt_user] = {
                'count': count,
                'last_reset': datetime.now().replace(hour=0, minute=0, second=0, microsecond=0),
            }

            result = agent._has_exceeded_daily_limit(exempt_user, max_conversations_per_day=limit)

            assert result is False, (
                f"Expected False for exempt user '{exempt_user}' with count={count}, limit={limit}"
            )


class TestConversationHistorySummarizationLifecycle:
    """Property 18: Conversation History Summarization Lifecycle.

    **Validates: Requirements 8.3, 8.4**

    For any sequence of conversation exchanges added via _add_to_history, when either
    the turn count reaches MAX_TURNS_BEFORE_SUMMARY or the estimated token count exceeds
    MAX_CONTEXT_TOKENS, summarization triggers, resulting in raw history containing at
    most RAW_TURNS_TO_KEEP entries and a non-empty summary field.
    """

    @given(
        max_turns=st.integers(min_value=3, max_value=8),
        raw_to_keep=st.integers(min_value=1, max_value=3),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_turn_count_triggers_summarization(self, max_turns, raw_to_keep):
        """Property: When turn count reaches MAX_TURNS_BEFORE_SUMMARY, summarization
        triggers and raw history contains at most RAW_TURNS_TO_KEEP entries with
        a non-empty summary."""
        # Ensure raw_to_keep < max_turns so summarization actually processes turns
        if raw_to_keep >= max_turns:
            raw_to_keep = max(1, max_turns - 1)

        mock_cfg = MagicMock()
        mock_cfg.LLM_PROVIDER = 'openai'
        mock_cfg.OPENAI_API_KEY = 'test-key'
        mock_cfg.ANTHROPIC_API_KEY = 'test-key'
        mock_cfg.OPENAI_MODEL = 'gpt-4o-mini'
        mock_cfg.ANTHROPIC_MODEL = 'claude-sonnet-4-20250514'

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch('app.pdn_relationships.agents.base_pdn_agent.Config', return_value=mock_cfg):
                with patch('app.pdn_relationships.agents.base_pdn_agent.ChatOpenAI') as mock_openai:
                    with patch('app.pdn_relationships.agents.base_pdn_agent.ChatAnthropic') as mock_anthropic:
                        mock_openai.return_value = MagicMock()
                        mock_anthropic.return_value = MagicMock()
                        with patch.dict('os.environ', {'SAVED_RESULTS_DIR': tmp_dir}):
                            config = BaseAgentConfig(
                                max_turns_before_summary=max_turns,
                                raw_turns_to_keep=raw_to_keep,
                                max_context_tokens=999999,  # High token limit so only turn limit triggers
                            )
                            agent = BasePDNAgent(config=config)

            # Mock summary_llm to return a non-empty summary
            mock_summary_response = MagicMock()
            mock_summary_response.content = "Summary of previous conversation."
            agent.summary_llm = MagicMock()
            agent.summary_llm.invoke.return_value = mock_summary_response

            # Mock history_service to avoid file I/O
            agent.history_service = MagicMock()

            user_name = "test_user"

            # Add exactly max_turns to trigger summarization once
            # After max_turns entries, the last _add_to_history triggers summarization
            # which truncates raw to raw_to_keep entries
            for i in range(max_turns):
                agent._add_to_history(user_name, f"user message {i}", f"assistant response {i}")

            hist = agent.conversation_history[user_name]

            # Property assertions: immediately after summarization triggers
            assert len(hist.raw) <= raw_to_keep, (
                f"raw history has {len(hist.raw)} entries, expected at most {raw_to_keep} "
                f"(max_turns={max_turns}, raw_to_keep={raw_to_keep})"
            )
            assert hist.summary != "", (
                "summary should be non-empty after summarization triggers"
            )

    @given(
        message_length=st.integers(min_value=500, max_value=2000),
        num_turns=st.integers(min_value=4, max_value=10),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_token_count_triggers_summarization(self, message_length, num_turns):
        """Property: When estimated token count exceeds MAX_CONTEXT_TOKENS,
        summarization triggers and raw history contains at most RAW_TURNS_TO_KEEP
        entries with a non-empty summary."""
        mock_cfg = MagicMock()
        mock_cfg.LLM_PROVIDER = 'openai'
        mock_cfg.OPENAI_API_KEY = 'test-key'
        mock_cfg.ANTHROPIC_API_KEY = 'test-key'
        mock_cfg.OPENAI_MODEL = 'gpt-4o-mini'
        mock_cfg.ANTHROPIC_MODEL = 'claude-sonnet-4-20250514'

        # Use a low token limit so that the messages trigger summarization
        # Token estimation: len(text) // 3
        # Each turn has user + assistant messages, each of message_length chars
        # Tokens per turn ≈ (message_length * 2) // 3
        tokens_per_turn = (message_length * 2) // 3

        # Set max_context_tokens so that 2 turns won't trigger but num_turns will
        # We want the threshold to be exceeded when all num_turns are present
        # Set it to be exceeded after exactly 3 turns (so summarization triggers on turn 3)
        raw_to_keep = 2
        trigger_at = 3  # Summarization triggers when this many turns are present
        max_context_tokens = tokens_per_turn * trigger_at - 1

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch('app.pdn_relationships.agents.base_pdn_agent.Config', return_value=mock_cfg):
                with patch('app.pdn_relationships.agents.base_pdn_agent.ChatOpenAI') as mock_openai:
                    with patch('app.pdn_relationships.agents.base_pdn_agent.ChatAnthropic') as mock_anthropic:
                        mock_openai.return_value = MagicMock()
                        mock_anthropic.return_value = MagicMock()
                        with patch.dict('os.environ', {'SAVED_RESULTS_DIR': tmp_dir}):
                            config = BaseAgentConfig(
                                max_turns_before_summary=9999,  # High turn limit so only token limit triggers
                                raw_turns_to_keep=raw_to_keep,
                                max_context_tokens=max_context_tokens,
                            )
                            agent = BasePDNAgent(config=config)

            # Mock summary_llm to return a non-empty summary
            mock_summary_response = MagicMock()
            mock_summary_response.content = "Token-triggered summary of conversation."
            agent.summary_llm = MagicMock()
            agent.summary_llm.invoke.return_value = mock_summary_response

            # Mock history_service to avoid file I/O
            agent.history_service = MagicMock()

            user_name = "test_user_tokens"

            # Add turns with long messages to exceed token limit
            for i in range(num_turns):
                user_msg = "x" * message_length
                assistant_msg = "y" * message_length
                agent._add_to_history(user_name, user_msg, assistant_msg)

            hist = agent.conversation_history[user_name]

            # Property assertions: after token-triggered summarization
            # After summarization, raw is truncated to raw_to_keep. Then additional
            # turns may be added before the next trigger. The invariant is:
            # summarization was triggered (summary non-empty) and raw never exceeds
            # raw_to_keep + (trigger_at - 1) since at most trigger_at-1 turns can
            # accumulate after a summarization before the next trigger.
            assert len(hist.raw) <= raw_to_keep + (trigger_at - 1), (
                f"raw history has {len(hist.raw)} entries, expected at most "
                f"{raw_to_keep + trigger_at - 1} "
                f"(num_turns={num_turns}, max_context_tokens={max_context_tokens})"
            )
            assert hist.summary != "", (
                "summary should be non-empty after token-triggered summarization"
            )
            # Verify summarization was actually called
            assert agent.summary_llm.invoke.called, (
                "summary_llm.invoke should have been called for summarization"
            )


class TestInputSanitizationNeutralizesInjectionPatterns:
    """Property 20: Input Sanitization Neutralizes Injection Patterns.

    **Validates: Requirements 8.8**

    For any string containing XML-like tags matching the pattern
    </?(system|context|user_message|assistant|instruction)>,
    _sanitize_user_input produces a string where all such tags have their
    angle brackets replaced with full-width equivalents (＜, ＞),
    preventing prompt structure breakage.
    """

    # Strategy: generate strings that contain at least one injection tag
    _TAG_NAMES = ['system', 'context', 'user_message', 'assistant', 'instruction']

    @given(
        tag_name=st.sampled_from(_TAG_NAMES),
        is_closing=st.booleans(),
        prefix=st.text(min_size=0, max_size=50),
        suffix=st.text(min_size=0, max_size=50),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_injection_tags_are_neutralized(self, tag_name, is_closing, prefix, suffix):
        """Property: For any string containing XML-like injection tags,
        _sanitize_user_input replaces angle brackets with full-width equivalents.

        **Validates: Requirements 8.8**
        """
        # Build the injection tag
        if is_closing:
            tag = f"</{tag_name}>"
        else:
            tag = f"<{tag_name}>"

        # Compose input with the tag embedded
        user_input = f"{prefix}{tag}{suffix}"

        # Call the static method
        result = BasePDNAgent._sanitize_user_input(user_input)

        # The original ASCII angle-bracket tag should NOT appear in the output
        assert tag not in result, (
            f"Original tag '{tag}' should not appear in sanitized output, got: {result}"
        )

        # The full-width equivalent SHOULD appear
        if is_closing:
            expected_replacement = f"＜/{tag_name}＞"
        else:
            expected_replacement = f"＜{tag_name}＞"

        assert expected_replacement in result, (
            f"Expected full-width replacement '{expected_replacement}' in output, got: {result}"
        )

        # The non-tag prefix and suffix should be preserved unchanged
        # (only the tag's angle brackets are replaced)
        # Verify no standard angle-bracket injection tags remain
        injection_pattern = re.compile(
            r'</?(system|context|user_message|assistant|instruction)>',
            re.IGNORECASE,
        )
        assert not injection_pattern.search(result), (
            f"Sanitized output still contains injection pattern: {result}"
        )

    @given(
        tag_names=st.lists(
            st.sampled_from(_TAG_NAMES),
            min_size=1,
            max_size=5,
        ),
        closings=st.lists(st.booleans(), min_size=1, max_size=5),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_multiple_injection_tags_all_neutralized(self, tag_names, closings):
        """Property: For any string with multiple injection tags,
        ALL tags are neutralized (no injection patterns remain).

        **Validates: Requirements 8.8**
        """
        # Build input with multiple tags
        parts = []
        for i in range(min(len(tag_names), len(closings))):
            tag_name = tag_names[i]
            is_closing = closings[i]
            if is_closing:
                parts.append(f"</{tag_name}>")
            else:
                parts.append(f"<{tag_name}>")

        user_input = "some text ".join(parts)

        result = BasePDNAgent._sanitize_user_input(user_input)

        # No standard angle-bracket injection tags should remain
        injection_pattern = re.compile(
            r'</?(system|context|user_message|assistant|instruction)>',
            re.IGNORECASE,
        )
        assert not injection_pattern.search(result), (
            f"Sanitized output still contains injection pattern: {result}"
        )

        # Each original tag should have been replaced with full-width version
        for i in range(min(len(tag_names), len(closings))):
            tag_name = tag_names[i]
            is_closing = closings[i]
            if is_closing:
                original_tag = f"</{tag_name}>"
            else:
                original_tag = f"<{tag_name}>"
            assert original_tag not in result, (
                f"Original tag '{original_tag}' should not appear in sanitized output"
            )
