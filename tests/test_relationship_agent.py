"""Tests for RelationshipAgent logic.

Tests prompt composition, caching, daily limit enforcement,
code data loading, and chat flow with mocked LLM.
Requirements: Agent logic correctness.
"""

import tempfile
from unittest.mock import patch, MagicMock

import pytest

from app.pdn_relationships.agents.relationship_agent import (
    RelationshipAgent,
    RELATIONSHIP_LABELS,
    DAILY_LIMIT_MESSAGE,
    PROMPTS_DIR,
    PDN_CODE_DIR,
    GUARDRAILS_PATH,
)
from app.pdn_relationships.constants import PDN_CODES


def _create_agent(tmp_dir: str) -> RelationshipAgent:
    """Helper to create a RelationshipAgent with mocked LLM providers."""
    mock_cfg = MagicMock()
    mock_cfg.LLM_PROVIDER = "openai"
    mock_cfg.OPENAI_API_KEY = "test-key"
    mock_cfg.ANTHROPIC_API_KEY = "test-key"
    mock_cfg.OPENAI_MODEL = "gpt-4o-mini"
    mock_cfg.ANTHROPIC_MODEL = "claude-sonnet-4-20250514"

    with patch("app.pdn_relationships.agents.base_pdn_agent.Config", return_value=mock_cfg):
        with patch("app.pdn_relationships.agents.base_pdn_agent.ChatOpenAI") as mock_openai:
            with patch("app.pdn_relationships.agents.base_pdn_agent.ChatAnthropic"):
                mock_llm = MagicMock()
                mock_openai.return_value = mock_llm
                with patch.dict("os.environ", {"SAVED_RESULTS_DIR": tmp_dir}):
                    agent = RelationshipAgent()
    return agent


class TestLoadRelationshipPrompt:
    """Tests for _load_relationship_prompt composing all four prompt sections."""

    def test_prompt_composes_all_four_sections(self):
        """Prompt should include base prompt, user code data, partner code data, and guardrails."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            agent = _create_agent(tmp_dir)

            fake_base = "Base relationship instructions"
            fake_user_code = "User code A3 data"
            fake_partner_code = "Partner code E5 data"
            fake_guardrails = "Safety guardrails content"

            def mock_read_text(self, encoding="utf-8"):
                path_str = str(self)
                if "relationship_agent.prompt" in path_str:
                    return fake_base
                elif "guardrails.prompt" in path_str:
                    return fake_guardrails
                elif "/a3.prompt" in path_str:
                    return fake_user_code
                elif "/e5.prompt" in path_str:
                    return fake_partner_code
                return ""

            def mock_exists(self):
                return True

            with patch("pathlib.Path.read_text", mock_read_text):
                with patch("pathlib.Path.exists", mock_exists):
                    prompt = agent._load_relationship_prompt("a3", "e5", "partner")

            assert fake_base in prompt, "Prompt should contain base relationship instructions"
            assert fake_user_code in prompt, "Prompt should contain user code data"
            assert fake_partner_code in prompt, "Prompt should contain partner code data"
            assert fake_guardrails in prompt, "Prompt should contain guardrails"
            assert "בן/בת זוג" in prompt, "Prompt should contain Hebrew relationship label"


class TestPromptCaching:
    """Tests for prompt caching behavior."""

    def test_prompt_caching_returns_cached_result(self):
        """Second call with same params should return cached prompt without re-reading files."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            agent = _create_agent(tmp_dir)

            fake_prompt = "Cached prompt content"
            cache_key = "rel_a3_e5_partner"
            agent._prompt_cache[cache_key] = fake_prompt

            # Should return cached value without touching the filesystem
            result = agent._load_relationship_prompt("a3", "e5", "partner")
            assert result == fake_prompt

    def test_different_params_produce_different_cache_keys(self):
        """Different (user_code, partner_code, relationship_type) should use different cache keys."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            agent = _create_agent(tmp_dir)

            agent._prompt_cache["rel_a3_e5_partner"] = "prompt_1"
            agent._prompt_cache["rel_a3_e5_friend"] = "prompt_2"

            assert agent._load_relationship_prompt("a3", "e5", "partner") == "prompt_1"
            assert agent._load_relationship_prompt("a3", "e5", "friend") == "prompt_2"


class TestDailyLimitEnforcement:
    """Tests for daily conversation limit enforcement."""

    def test_daily_limit_blocks_after_limit_reached(self):
        """After daily_limit calls, agent should return the limit message."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            agent = _create_agent(tmp_dir)

            # Mock LLM response
            mock_response = MagicMock()
            mock_response.content = "תשובה"
            mock_response.usage_metadata = None
            agent.llm.invoke = MagicMock(return_value=mock_response)

            # Mock prompt loading
            agent._load_relationship_prompt = MagicMock(return_value="system prompt")

            daily_limit = 3

            # Make daily_limit calls - all should succeed
            for i in range(daily_limit):
                response = agent.chat(
                    message=f"msg_{i}",
                    user_name="test_user",
                    user_code="a3",
                    partner_code="e5",
                    relationship_type="partner",
                    daily_conversation_limit=daily_limit,
                )
                assert response != DAILY_LIMIT_MESSAGE

            # Next call should hit the limit
            response = agent.chat(
                message="one_more",
                user_name="test_user",
                user_code="a3",
                partner_code="e5",
                relationship_type="partner",
                daily_conversation_limit=daily_limit,
            )
            assert response == DAILY_LIMIT_MESSAGE


class TestLoadCodeData:
    """Tests for _load_code_data raising ValueError for invalid codes."""

    def test_invalid_code_raises_value_error(self):
        """_load_code_data should raise ValueError for a non-existent code file."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            agent = _create_agent(tmp_dir)

            with pytest.raises(ValueError, match="Unknown PDN code"):
                agent._load_code_data("zzz_invalid")

    def test_empty_code_raises_value_error(self):
        """_load_code_data should raise ValueError for empty code."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            agent = _create_agent(tmp_dir)

            with pytest.raises(ValueError, match="PDN code is required"):
                agent._load_code_data("")


class TestChatFlow:
    """Tests for the chat method with mocked LLM."""

    def test_chat_invokes_llm_and_returns_response(self):
        """Chat should invoke LLM and return the response content."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            agent = _create_agent(tmp_dir)

            # Mock LLM response
            mock_response = MagicMock()
            mock_response.content = "עצה טובה לזוגיות"
            mock_response.usage_metadata = None
            agent.llm.invoke = MagicMock(return_value=mock_response)

            # Mock prompt loading
            agent._load_relationship_prompt = MagicMock(return_value="system prompt")

            result = agent.chat(
                message="איך לשפר תקשורת?",
                user_name="יעל",
                user_code="a3",
                partner_code="e5",
                relationship_type="partner",
            )

            assert result == "עצה טובה לזוגיות"
            agent.llm.invoke.assert_called_once()

    def test_chat_adds_to_history(self):
        """Chat should add the exchange to conversation history."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            agent = _create_agent(tmp_dir)

            mock_response = MagicMock()
            mock_response.content = "תשובה"
            mock_response.usage_metadata = None
            agent.llm.invoke = MagicMock(return_value=mock_response)
            agent._load_relationship_prompt = MagicMock(return_value="system prompt")

            agent.chat(
                message="שאלה",
                user_name="user1",
                user_code="a3",
                partner_code="e5",
                relationship_type="partner",
            )

            hist = agent.conversation_history["user1"]
            assert len(hist.raw) == 1
            assert hist.raw[0]["user"] == "שאלה"
            assert hist.raw[0]["assistant"] == "תשובה"

    def test_chat_prompt_includes_user_and_partner_codes_and_relationship_type(self):
        """Chat should pass user code, partner code, and relationship type in the user message."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            agent = _create_agent(tmp_dir)

            mock_response = MagicMock()
            mock_response.content = "advice response"
            mock_response.usage_metadata = None

            # Mock _invoke_llm to capture the messages passed
            captured_messages = []

            def capture_invoke(messages, **kwargs):
                captured_messages.extend(messages)
                return mock_response

            agent._invoke_llm = MagicMock(side_effect=capture_invoke)
            agent._load_relationship_prompt = MagicMock(return_value="system prompt content")

            agent.chat(
                message="how to communicate better?",
                user_name="test_user",
                user_code="a3",
                partner_code="e5",
                relationship_type="partner",
            )

            # Verify _invoke_llm was called
            agent._invoke_llm.assert_called_once()

            # Get the HumanMessage content
            human_msg = captured_messages[1]
            user_content = human_msg.content

            # Verify user code, partner code, and relationship type are in the message
            assert "a3" in user_content, "User code should be in the prompt"
            assert "e5" in user_content, "Partner code should be in the prompt"
            assert "בן/בת זוג" in user_content, "Hebrew relationship label should be in the prompt"

    def test_chat_prompt_includes_history_when_present(self):
        """Chat should include session history in the user message when history exists."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            agent = _create_agent(tmp_dir)

            # Pre-populate history
            from app.pdn_relationships.agents.base_pdn_agent import UserHistory
            agent.conversation_history["test_user"] = UserHistory(
                raw=[{"user": "previous question", "assistant": "previous answer"}],
                summary="",
            )

            mock_response = MagicMock()
            mock_response.content = "follow-up advice"
            mock_response.usage_metadata = None

            captured_messages = []

            def capture_invoke(messages, **kwargs):
                captured_messages.extend(messages)
                return mock_response

            agent._invoke_llm = MagicMock(side_effect=capture_invoke)
            agent._load_relationship_prompt = MagicMock(return_value="system prompt")

            agent.chat(
                message="follow-up question",
                user_name="test_user",
                user_code="a3",
                partner_code="e5",
                relationship_type="partner",
            )

            human_msg = captured_messages[1]
            user_content = human_msg.content

            # Verify history is included
            assert "Session history" in user_content, "History context should be in the prompt"
            assert "previous question" in user_content, "Previous user message should be in history"
            assert "previous answer" in user_content, "Previous assistant response should be in history"


class TestLoadRelationshipPromptCompositionOrder:
    """Tests for _load_relationship_prompt verifying composition order."""

    def test_composition_order_base_guardrails_context_user_partner(self):
        """Prompt should be composed in order: base prompt, guardrails, relationship context, user code, partner code."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            agent = _create_agent(tmp_dir)

            fake_base = "BASE_PROMPT_CONTENT"
            fake_guardrails = "GUARDRAILS_CONTENT"
            fake_user_code = "USER_CODE_DATA"
            fake_partner_code = "PARTNER_CODE_DATA"

            def mock_read_text(self, encoding="utf-8"):
                path_str = str(self)
                if "relationship_agent.prompt" in path_str:
                    return fake_base
                elif "guardrails.prompt" in path_str:
                    return fake_guardrails
                elif "/a3.prompt" in path_str:
                    return fake_user_code
                elif "/e5.prompt" in path_str:
                    return fake_partner_code
                return ""

            def mock_exists(self):
                return True

            with patch("pathlib.Path.read_text", mock_read_text):
                with patch("pathlib.Path.exists", mock_exists):
                    prompt = agent._load_relationship_prompt("a3", "e5", "partner")

            # Verify composition order: base first, then guardrails, then context, then user code, then partner code
            base_pos = prompt.index(fake_base)
            guardrails_pos = prompt.index(fake_guardrails)
            user_code_pos = prompt.index(fake_user_code)
            partner_code_pos = prompt.index(fake_partner_code)

            assert base_pos < guardrails_pos, "Base prompt should come before guardrails"
            assert guardrails_pos < user_code_pos, "Guardrails should come before user code"
            assert user_code_pos < partner_code_pos, "User code should come before partner code"

    def test_composition_includes_relationship_context_section(self):
        """Prompt should include a relationship context section between guardrails and code data."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            agent = _create_agent(tmp_dir)

            def mock_read_text(self, encoding="utf-8"):
                path_str = str(self)
                if "relationship_agent.prompt" in path_str:
                    return "base"
                elif "guardrails.prompt" in path_str:
                    return "guardrails"
                elif "/a3.prompt" in path_str:
                    return "user_code"
                elif "/e5.prompt" in path_str:
                    return "partner_code"
                return ""

            def mock_exists(self):
                return True

            with patch("pathlib.Path.read_text", mock_read_text):
                with patch("pathlib.Path.exists", mock_exists):
                    prompt = agent._load_relationship_prompt("a3", "e5", "colleague")

            # Verify relationship context section is present with correct label
            assert "## Relationship Context" in prompt
            assert "עמית/ה לעבודה" in prompt, "Should contain Hebrew label for colleague"

    def test_caching_prevents_file_reads_on_second_call(self):
        """Second call with same params should use cache and not read files again."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            agent = _create_agent(tmp_dir)

            read_count = {"calls": 0}

            def mock_read_text(self, encoding="utf-8"):
                read_count["calls"] += 1
                path_str = str(self)
                if "relationship_agent.prompt" in path_str:
                    return "base"
                elif "guardrails.prompt" in path_str:
                    return "guardrails"
                elif "/a3.prompt" in path_str:
                    return "user_code"
                elif "/e5.prompt" in path_str:
                    return "partner_code"
                return ""

            def mock_exists(self):
                return True

            with patch("pathlib.Path.read_text", mock_read_text):
                with patch("pathlib.Path.exists", mock_exists):
                    # First call — reads files
                    result1 = agent._load_relationship_prompt("a3", "e5", "partner")
                    first_call_reads = read_count["calls"]

                    # Second call — should use cache
                    result2 = agent._load_relationship_prompt("a3", "e5", "partner")

            assert result1 == result2, "Cached result should be identical"
            assert read_count["calls"] == first_call_reads, "No additional file reads on second call"


class TestLoadCodeDataSuccess:
    """Tests for _load_code_data successful file loading."""

    def test_load_code_data_returns_file_content(self):
        """_load_code_data should return the content of the code prompt file."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            agent = _create_agent(tmp_dir)

            expected_content = "PDN code A3 description content"

            def mock_read_text(self, encoding="utf-8"):
                return expected_content

            def mock_exists(self):
                return True

            with patch("pathlib.Path.read_text", mock_read_text):
                with patch("pathlib.Path.exists", mock_exists):
                    result = agent._load_code_data("a3")

            assert result == expected_content


class TestDailyLimitNoLLMCall:
    """Tests verifying daily limit enforcement prevents LLM invocation."""

    def test_daily_limit_returns_message_without_invoking_llm(self):
        """When daily limit is exceeded, DAILY_LIMIT_MESSAGE is returned without calling _invoke_llm."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            agent = _create_agent(tmp_dir)

            # Mock _invoke_llm to track if it's called
            agent._invoke_llm = MagicMock()
            agent._load_relationship_prompt = MagicMock(return_value="system prompt")

            # Set the user's conversation count to already be at the limit
            agent.user_conversations["test_user"]["count"] = 5

            response = agent.chat(
                message="one more message",
                user_name="test_user",
                user_code="a3",
                partner_code="e5",
                relationship_type="partner",
                daily_conversation_limit=5,
            )

            assert response == DAILY_LIMIT_MESSAGE, "Should return daily limit message"
            agent._invoke_llm.assert_not_called(), "LLM should NOT be invoked when limit is exceeded"

    def test_daily_limit_does_not_load_prompt(self):
        """When daily limit is exceeded, _load_relationship_prompt should not be called."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            agent = _create_agent(tmp_dir)

            agent._invoke_llm = MagicMock()
            agent._load_relationship_prompt = MagicMock(return_value="system prompt")

            # Set the user's conversation count to already be at the limit
            agent.user_conversations["test_user"]["count"] = 3

            response = agent.chat(
                message="blocked message",
                user_name="test_user",
                user_code="a3",
                partner_code="e5",
                relationship_type="partner",
                daily_conversation_limit=3,
            )

            assert response == DAILY_LIMIT_MESSAGE
            agent._load_relationship_prompt.assert_not_called(), "Prompt loading should be skipped when limit is hit"
