"""Property tests for RelationshipAgent: prompt composition and daily limit enforcement.

**Validates: Correctness Property 4** - Prompt composition includes both codes' data
**Validates: Correctness Property 3** - Daily limit is enforced identically to pdn_chat_ai
"""

import tempfile
from unittest.mock import patch, MagicMock

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.pdn_relationships.constants import PDN_CODES
from app.pdn_relationships.agents.relationship_agent import (
    RelationshipAgent,
    RELATIONSHIP_LABELS,
    DAILY_LIMIT_MESSAGE,
)


# --- Strategies ---
pdn_code_strategy = st.sampled_from(PDN_CODES)
relationship_type_strategy = st.sampled_from(["partner", "friend", "colleague"])
daily_limit_strategy = st.integers(min_value=1, max_value=10)


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


class TestPromptCompositionIncludesBothCodes:
    """Property 4: Prompt composition includes both codes' data.

    **Validates: Correctness Property 4**

    For any valid (user_code, partner_code, relationship_type) combination,
    the composed prompt contains references to both codes and the relationship
    type label in Hebrew.
    """

    @given(
        user_code=pdn_code_strategy,
        partner_code=pdn_code_strategy,
        relationship_type=relationship_type_strategy,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_prompt_contains_both_codes_and_relationship_label(
        self, user_code, partner_code, relationship_type
    ):
        """Property: For any valid (user_code, partner_code, relationship_type),
        the composed prompt contains content from both code files and the
        Hebrew relationship label."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            agent = _create_agent(tmp_dir)

            # Clear prompt cache to ensure fresh composition
            agent._prompt_cache.clear()

            # Mock the file reads: base prompt and guardrails
            fake_base_prompt = "Base relationship prompt template"
            fake_guardrails = "Guardrails content"

            # Each code gets unique content (even when user_code == partner_code,
            # the real implementation reads the same file for both, which is correct)
            fake_code_data = {code: f"PDN code data for [{code}]" for code in PDN_CODES}

            def mock_read_text(self, encoding="utf-8"):
                path_str = str(self)
                if "relationship_agent.prompt" in path_str:
                    return fake_base_prompt
                elif "guardrails.prompt" in path_str:
                    return fake_guardrails
                # Match any PDN code file
                for code in PDN_CODES:
                    if f"/{code}.prompt" in path_str:
                        return fake_code_data[code]
                return ""

            def mock_exists(self):
                return True

            with patch("pathlib.Path.read_text", mock_read_text):
                with patch("pathlib.Path.exists", mock_exists):
                    prompt = agent._load_relationship_prompt(
                        user_code, partner_code, relationship_type
                    )

            # Assert: prompt contains user code data
            assert fake_code_data[user_code] in prompt, (
                f"Prompt should contain code data for user code {user_code}"
            )

            # Assert: prompt contains partner code data
            assert fake_code_data[partner_code] in prompt, (
                f"Prompt should contain code data for partner code {partner_code}"
            )

            # Assert: prompt contains the Hebrew relationship label
            expected_label = RELATIONSHIP_LABELS[relationship_type]
            assert expected_label in prompt, (
                f"Prompt should contain Hebrew label '{expected_label}' "
                f"for relationship type '{relationship_type}'"
            )

            # Assert: prompt contains the base template
            assert fake_base_prompt in prompt, (
                "Prompt should contain the base relationship prompt template"
            )

            # Assert: prompt contains guardrails
            assert fake_guardrails in prompt, (
                "Prompt should contain guardrails content"
            )


class TestPromptLoadingCachingAndValidation:
    """Property 14: Prompt Loading Caching and Validation (relationship variant).

    **Validates: Requirements 9.3, 9.4**

    For any valid (user_code, partner_code, relationship_type), calling
    _load_relationship_prompt twice with the same arguments returns identical
    strings and only reads files on the first call (cache hit on second).
    For any empty or non-existent PDN code, the function raises ValueError.
    """

    @given(
        user_code=pdn_code_strategy,
        partner_code=pdn_code_strategy,
        relationship_type=relationship_type_strategy,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_two_calls_same_args_return_identical_result_and_cache(
        self, user_code, partner_code, relationship_type
    ):
        """Property: Two calls with same args → identical result, file read only first call.

        **Validates: Requirements 9.3**
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            agent = _create_agent(tmp_dir)

            # Clear prompt cache to ensure fresh state
            agent._prompt_cache.clear()

            fake_base_prompt = "Base relationship prompt"
            fake_guardrails = "Guardrails content"
            fake_code_data = {code: f"Code data for [{code}]" for code in PDN_CODES}

            read_text_call_count = {"count": 0}

            def mock_read_text(self, encoding="utf-8"):
                read_text_call_count["count"] += 1
                path_str = str(self)
                if "relationship_agent.prompt" in path_str:
                    return fake_base_prompt
                elif "guardrails.prompt" in path_str:
                    return fake_guardrails
                for code in PDN_CODES:
                    if f"/{code}.prompt" in path_str:
                        return fake_code_data[code]
                return ""

            def mock_exists(self):
                return True

            with patch("pathlib.Path.read_text", mock_read_text):
                with patch("pathlib.Path.exists", mock_exists):
                    # First call - should read files
                    result1 = agent._load_relationship_prompt(
                        user_code, partner_code, relationship_type
                    )
                    first_call_reads = read_text_call_count["count"]

                    # Second call - should use cache, no additional file reads
                    result2 = agent._load_relationship_prompt(
                        user_code, partner_code, relationship_type
                    )
                    second_call_reads = read_text_call_count["count"]

            # Results must be identical
            assert result1 == result2, (
                "Two calls with same args must return identical result"
            )

            # First call should have read files (at least 1 read)
            assert first_call_reads > 0, (
                "First call should read files from disk"
            )

            # Second call should NOT have read any additional files (cache hit)
            assert second_call_reads == first_call_reads, (
                f"Second call should not read files (cache hit). "
                f"Reads after first call: {first_call_reads}, "
                f"reads after second call: {second_call_reads}"
            )

    @given(
        invalid_code=st.one_of(
            st.just(""),
            st.text(
                alphabet=st.characters(whitelist_categories=("L", "N")),
                min_size=1,
                max_size=10,
            ).filter(lambda x: x not in PDN_CODES),
        ),
        partner_code=pdn_code_strategy,
        relationship_type=relationship_type_strategy,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_invalid_or_empty_pdn_code_raises_value_error(
        self, invalid_code, partner_code, relationship_type
    ):
        """Property: For any empty or non-existent PDN code, raises ValueError.

        **Validates: Requirements 9.4**
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            agent = _create_agent(tmp_dir)

            # Clear prompt cache
            agent._prompt_cache.clear()

            fake_base_prompt = "Base relationship prompt"
            fake_guardrails = "Guardrails content"

            def mock_read_text(self, encoding="utf-8"):
                path_str = str(self)
                if "relationship_agent.prompt" in path_str:
                    return fake_base_prompt
                elif "guardrails.prompt" in path_str:
                    return fake_guardrails
                return ""

            def mock_exists(self):
                path_str = str(self)
                # Base prompt and guardrails exist
                if "relationship_agent.prompt" in path_str:
                    return True
                if "guardrails.prompt" in path_str:
                    return True
                # Invalid code file does not exist
                return False

            with patch("pathlib.Path.read_text", mock_read_text):
                with patch("pathlib.Path.exists", mock_exists):
                    with pytest.raises(ValueError):
                        agent._load_relationship_prompt(
                            invalid_code, partner_code, relationship_type
                        )


class TestDailyLimitEnforcement:
    """Property 3: Daily limit is enforced identically to pdn_chat_ai.

    **Validates: Correctness Property 3**

    After daily_limit calls, the agent returns the limit message.
    Calls before the limit return non-limit responses.
    """

    @given(daily_limit=daily_limit_strategy)
    @settings(
        max_examples=20,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_daily_limit_enforcement(self, daily_limit):
        """Property: After exactly daily_limit calls, the agent returns the
        daily limit message. All calls before the limit return non-limit responses."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            agent = _create_agent(tmp_dir)

            # Mock the LLM to return a fixed response
            mock_response = MagicMock()
            mock_response.content = "תשובה מהיועץ"
            mock_response.usage_metadata = None
            agent.llm.invoke = MagicMock(return_value=mock_response)

            # Mock prompt loading to avoid file system dependencies
            agent._prompt_cache["rel_a3_e5_partner"] = "cached prompt"

            def mock_load_prompt(user_code, partner_code, rel_type):
                return "cached prompt"

            agent._load_relationship_prompt = mock_load_prompt

            user_name = "test_user"

            # Make daily_limit calls - all should return non-limit responses
            for i in range(daily_limit):
                response = agent.chat(
                    message=f"message_{i}",
                    user_name=user_name,
                    user_code="a3",
                    partner_code="e5",
                    relationship_type="partner",
                    daily_conversation_limit=daily_limit,
                )
                assert response != DAILY_LIMIT_MESSAGE, (
                    f"Call {i + 1}/{daily_limit} should NOT return limit message"
                )

            # The next call (daily_limit + 1) should return the limit message
            response = agent.chat(
                message="one_more_message",
                user_name=user_name,
                user_code="a3",
                partner_code="e5",
                relationship_type="partner",
                daily_conversation_limit=daily_limit,
            )
            assert response == DAILY_LIMIT_MESSAGE, (
                f"Call {daily_limit + 1} should return the daily limit message"
            )
