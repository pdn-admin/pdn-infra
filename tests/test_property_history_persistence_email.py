"""Property test: History persistence uses email (not display name).

**Validates: Correctness Property 6**

Register a user with Hebrew display name and email, persist session,
verify history is saved under email (not display name).
"""

import tempfile
from unittest.mock import patch, MagicMock

import pytest
from hypothesis import given, settings, HealthCheck, assume
from hypothesis import strategies as st

from app.pdn_relationships.agents.relationship_agent import RelationshipAgent
from app.pdn_relationships.agents.base_pdn_agent import BasePDNAgent, BaseAgentConfig


# --- Strategies ---

# Hebrew display names (non-ASCII)
hebrew_display_name_strategy = st.text(
    min_size=2,
    max_size=20,
    alphabet=st.characters(
        whitelist_categories=("L",),
        whitelist_characters="אבגדהוזחטיכלמנסעפצקרשת "
    ),
).filter(lambda x: x.strip() != "")

# Valid email addresses (ASCII, safe for filesystem)
email_strategy = st.from_regex(
    r"[a-z][a-z0-9]{2,10}@[a-z]{3,8}\.[a-z]{2,4}",
    fullmatch=True,
)


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
            with patch("app.pdn_relationships.agents.base_pdn_agent.ChatAnthropic") as mock_anthropic:
                mock_llm = MagicMock()
                mock_openai.return_value = mock_llm
                mock_anthropic.return_value = MagicMock()
                with patch.dict("os.environ", {"SAVED_RESULTS_DIR": tmp_dir}):
                    agent = RelationshipAgent()
    return agent


class TestHistoryPersistenceUsesEmail:
    """Property 6: History persistence uses email (not display name).

    **Validates: Correctness Property 6**

    When a user with a Hebrew display name registers and persists a session,
    the history is saved under their email address, not their display name.
    """

    @given(
        display_name=hebrew_display_name_strategy,
        email=email_strategy,
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_persist_session_saves_under_email(self, display_name, email):
        """Property: For any Hebrew display name and email, persist_session
        calls save_user_history with the email (not the display name)."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            agent = _create_agent(tmp_dir)

            # Mock the summary LLM to return a summary without making real API calls
            mock_summary_response = MagicMock()
            mock_summary_response.content = "סיכום שיחה"
            agent.summary_llm = MagicMock()
            agent.summary_llm.invoke = MagicMock(return_value=mock_summary_response)

            # Add some conversation history so persist_session has something to save
            agent.conversation_history[display_name].raw.append({
                "user": "שאלה",
                "assistant": "תשובה",
            })

            # Mock the history_service.save_user_history to capture the call
            agent.history_service.save_user_history = MagicMock(return_value=True)

            # Register email and persist session
            agent.register_user_email(display_name, email)
            agent.persist_session(display_name, email)

            # Verify save_user_history was called with email, NOT display name
            agent.history_service.save_user_history.assert_called_once()
            call_args = agent.history_service.save_user_history.call_args
            saved_user_id = call_args[0][0]  # First positional argument

            assert saved_user_id == email, (
                f"History should be saved under email '{email}' "
                f"but was saved under '{saved_user_id}'"
            )
            assert saved_user_id != display_name, (
                f"History should NOT be saved under display name '{display_name}'"
            )

    @given(
        display_name=hebrew_display_name_strategy,
        email=email_strategy,
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_summarize_old_turns_uses_email_not_display_name(self, display_name, email):
        """Property: When summarization triggers during _add_to_history,
        the persisted history uses email (not display name)."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            agent = _create_agent(tmp_dir)

            # Mock the summary LLM
            mock_summary_response = MagicMock()
            mock_summary_response.content = "סיכום אוטומטי"
            agent.summary_llm = MagicMock()
            agent.summary_llm.invoke = MagicMock(return_value=mock_summary_response)

            # Mock save_user_history
            agent.history_service.save_user_history = MagicMock(return_value=True)

            # Register email mapping
            agent.register_user_email(display_name, email)

            # Set low thresholds to trigger summarization
            agent.MAX_TURNS_BEFORE_SUMMARY = 3
            agent.RAW_TURNS_TO_KEEP = 1

            # Add enough history to trigger summarization
            for i in range(4):
                agent._add_to_history(display_name, f"שאלה {i}", f"תשובה {i}")

            # Verify that if save_user_history was called, it used email
            if agent.history_service.save_user_history.called:
                call_args = agent.history_service.save_user_history.call_args
                saved_user_id = call_args[0][0]
                assert saved_user_id == email, (
                    f"Summarization should persist under email '{email}' "
                    f"but used '{saved_user_id}'"
                )
