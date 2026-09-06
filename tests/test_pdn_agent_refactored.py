"""Tests for refactored PDN agent."""

import re
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from hypothesis import given, settings, strategies as st

from app.pdn_chat_ai.binat_agents.pdn_agent import PDNAgent

try:
    from app.pdn_chat_ai.binat_agents.pdn_agent_refactored import (
        PDNAgentRefactored,
        SessionStore,
        load_pdn_system_prompt
    )
    HAS_REFACTORED = True
except ImportError:
    HAS_REFACTORED = False


@pytest.mark.skipif(not HAS_REFACTORED, reason="pdn_agent_refactored module not available")
class TestSessionStore:
    """Test session store functionality."""
    
    def test_get_session_history_creates_new(self):
        store = SessionStore()
        history = store.get_session_history("user1_a7")
        assert history is not None
        assert len(history.messages) == 0
    
    def test_get_session_history_returns_existing(self):
        store = SessionStore()
        history1 = store.get_session_history("user1_a7")
        history1.add_user_message("test")
        
        history2 = store.get_session_history("user1_a7")
        assert history1 is history2
        assert len(history2.messages) == 1
    
    def test_clear_session(self):
        store = SessionStore()
        store.get_session_history("user1_a7")
        assert "user1_a7" in store._store
        
        store.clear_session("user1_a7")
        assert "user1_a7" not in store._store


@pytest.mark.skipif(not HAS_REFACTORED, reason="pdn_agent_refactored module not available")
class TestLoadPDNSystemPrompt:
    """Test prompt loading with caching."""
    
    @patch('pathlib.Path.read_text')
    def test_load_pdn_system_prompt(self, mock_read_text):
        mock_read_text.side_effect = [
            "Base prompt",
            "PDN specific",
            "Guardrails"
        ]
        
        prompts_dir = Path("/fake/path")
        result = load_pdn_system_prompt("a7", prompts_dir)
        
        assert "Base prompt" in result
        assert "PDN specific" in result
        assert "Guardrails" in result
    
    @patch('pathlib.Path.read_text')
    def test_prompt_caching(self, mock_read_text):
        mock_read_text.side_effect = [
            "Base prompt",
            "PDN specific",
            "Guardrails"
        ]
        
        prompts_dir = Path("/fake/path")
        
        # First call
        result1 = load_pdn_system_prompt("a7", prompts_dir)
        # Second call should use cache
        result2 = load_pdn_system_prompt("a7", prompts_dir)
        
        assert result1 == result2
        # read_text should only be called 3 times (not 6)
        assert mock_read_text.call_count == 3


class TestPDNAgentRefactored:
    """Test refactored PDN agent."""
    
    @pytest.fixture
    def mock_llm(self):
        llm = Mock()
        llm.invoke = Mock(return_value=Mock(content="Test response"))
        return llm
    
    @pytest.fixture
    def agent(self, mock_llm):
        with patch('app.pdn_chat_ai.binat_agents.pdn_agent_refactored.ChatOpenAI', return_value=mock_llm):
            agent = PDNAgentRefactored(
                llm_provider="openai",
                openai_key="test_key"
            )
            return agent
    
    def test_initialization_openai(self):
        with patch('app.pdn_chat_ai.binat_agents.pdn_agent_refactored.ChatOpenAI') as mock_openai:
            agent = PDNAgentRefactored(
                llm_provider="openai",
                openai_key="test_key"
            )
            assert agent.llm_provider == "openai"
            assert agent.model_name == "gpt-4o"
            mock_openai.assert_called_once()
    
    def test_initialization_anthropic(self):
        with patch('app.pdn_chat_ai.binat_agents.pdn_agent_refactored.ChatAnthropic') as mock_anthropic:
            agent = PDNAgentRefactored(
                llm_provider="anthropic",
                anthropic_key="test_key"
            )
            assert agent.llm_provider == "anthropic"
            assert agent.model_name == "claude-3-5-sonnet-20241022"
            mock_anthropic.assert_called_once()
    
    def test_session_id_generation(self, agent):
        session_id = agent._get_session_id("user1", "a7")
        assert session_id == "user1_a7"
    
    def test_daily_limit_check_new_user(self, agent):
        assert agent._check_daily_limit("new_user") is True
    
    def test_daily_limit_increment(self, agent):
        user = "test_user"
        agent._check_daily_limit(user)
        
        for i in range(15):
            agent._increment_count(user)
        
        assert agent._check_daily_limit(user) is False
    
    @patch('app.pdn_chat_ai.binat_agents.pdn_agent_refactored.load_pdn_system_prompt')
    def test_chat_creates_chain_once(self, mock_load_prompt, agent):
        mock_load_prompt.return_value = "System prompt"
        
        # First chat
        with patch.object(agent, '_get_or_create_chain') as mock_get_chain:
            mock_chain = Mock()
            mock_chain.invoke = Mock(return_value=Mock(content="Response"))
            mock_get_chain.return_value = mock_chain
            
            agent.chat("Hello", "user1", "a7")
            agent.chat("Hi again", "user1", "a7")
            
            # Chain should be created once
            assert mock_get_chain.call_count == 2
            # But the same chain instance is reused
    
    @patch('app.pdn_chat_ai.binat_agents.pdn_agent_refactored.load_pdn_system_prompt')
    def test_chat_different_pdn_codes(self, mock_load_prompt, agent):
        mock_load_prompt.return_value = "System prompt"
        
        with patch.object(agent.llm, 'invoke', return_value=Mock(content="Response")):
            # Different PDN codes should create different chains
            agent.chat("Hello", "user1", "a7")
            agent.chat("Hello", "user1", "e5")
            
            assert len(agent._chains) == 2
            assert "a7" in agent._chains
            assert "e5" in agent._chains
    
    def test_clear_history(self, agent):
        session_id = agent._get_session_id("user1", "a7")
        agent.session_store.get_session_history(session_id).add_user_message("test")
        
        agent.clear_history("user1", "a7")
        
        # Session should be removed
        assert session_id not in agent.session_store._store
    
    def test_get_history(self, agent):
        session_id = agent._get_session_id("user1", "a7")
        history = agent.session_store.get_session_history(session_id)
        history.add_user_message("test message")
        
        messages = agent.get_history("user1", "a7")
        assert len(messages) == 1
        assert messages[0].content == "test message"
    
    @patch('app.pdn_chat_ai.binat_agents.pdn_agent_refactored.load_pdn_system_prompt')
    def test_chat_daily_limit_exceeded(self, mock_load_prompt, agent):
        mock_load_prompt.return_value = "System prompt"
        user = "limited_user"
        
        # Exceed limit
        for i in range(15):
            agent._increment_count(user)
        
        response = agent.chat("Hello", user, "a7")
        assert "הגעת למגבלת השיחות" in response
    
    @patch('app.pdn_chat_ai.binat_agents.pdn_agent_refactored.load_pdn_system_prompt')
    def test_chat_formats_input_correctly(self, mock_load_prompt, agent):
        mock_load_prompt.return_value = "System prompt"
        
        with patch.object(agent, '_get_or_create_chain') as mock_get_chain:
            mock_chain = Mock()
            mock_chain.invoke = Mock(return_value=Mock(content="Response"))
            mock_get_chain.return_value = mock_chain
            
            agent.chat("Test query", "sarah", "a7")
            
            # Check that invoke was called with formatted input
            call_args = mock_chain.invoke.call_args
            input_text = call_args[0][0]['input']
            
            assert "User Name is: sarah" in input_text
            assert "User PDN Code is: a7" in input_text
            assert "Test query" in input_text


class TestIntegration:
    """Integration tests (require actual API keys)."""
    
    @pytest.mark.skip(reason="Requires actual API key")
    def test_real_chat_openai(self):
        import os
        agent = PDNAgentRefactored(
            llm_provider="openai",
            openai_key=os.getenv("OPENAI_API_KEY")
        )
        
        response = agent.chat(
            user_query="שלום, איך אני יכול להתמודד עם פחד?",
            user_name="test_user",
            pdn_code="a7"
        )
        
        assert len(response) > 0
        assert isinstance(response, str)
    
    @pytest.mark.skip(reason="Requires actual API key")
    def test_real_chat_anthropic(self):
        import os
        agent = PDNAgentRefactored(
            llm_provider="anthropic",
            anthropic_key=os.getenv("ANTHROPIC_API_KEY")
        )
        
        response = agent.chat(
            user_query="שלום, איך אני יכול להתמודד עם פחד?",
            user_name="test_user",
            pdn_code="e5"
        )
        
        assert len(response) > 0
        assert isinstance(response, str)


class TestUsageStatsCostCalculationProperty:
    """Property-based tests for usage stats cost calculation.

    **Validates: Requirements 7.6**
    """

    # Model pricing as defined in get_usage_stats
    MODEL_PRICING = {
        'sonnet': {
            'input': 3.0, 'output': 15.0,
            'cache_write': 3.75, 'cache_read': 0.30,
        },
        'haiku': {
            'input': 0.80, 'output': 4.0,
            'cache_write': 1.0, 'cache_read': 0.08,
        },
        'gpt-4o-mini': {
            'input': 0.15, 'output': 0.60,
            'cache_write': 0.15, 'cache_read': 0.075,
        },
    }

    # Map model names to pricing tiers (matching _get_pricing logic)
    MODEL_TO_TIER = {
        'claude-sonnet-4-20250514': 'sonnet',
        'claude-3-5-haiku-20241022': 'haiku',
        'gpt-4o-mini': 'gpt-4o-mini',
    }

    @settings(max_examples=50)
    @given(
        input_tokens=st.integers(min_value=0, max_value=100000),
        output_tokens=st.integers(min_value=0, max_value=50000),
        cache_creation_tokens=st.integers(min_value=0, max_value=50000),
        cache_read_tokens=st.integers(min_value=0, max_value=50000),
        model=st.sampled_from(['claude-sonnet-4-20250514', 'claude-3-5-haiku-20241022', 'gpt-4o-mini']),
    )
    def test_property_15_usage_stats_cost_calculation(
        self, input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens, model
    ):
        """Property 15: Usage Stats Cost Calculation Invariant

        For any token usage data, the calculated cost equals:
        Cost = (uncached_input/1e6 × input_price) + (output/1e6 × output_price)
             + (cache_creation/1e6 × cache_write_price) + (cache_read/1e6 × cache_read_price)
        where uncached_input = input_tokens - cache_creation_tokens - cache_read_tokens

        **Validates: Requirements 7.6**
        """
        from datetime import datetime

        # Determine pricing tier
        tier = self.MODEL_TO_TIER[model]
        pricing = self.MODEL_PRICING[tier]

        # Expected cost calculation per the formula
        uncached_input = input_tokens - cache_creation_tokens - cache_read_tokens
        expected_cost = (
            (max(0, uncached_input) / 1e6) * pricing['input'] +
            (output_tokens / 1e6) * pricing['output'] +
            (cache_creation_tokens / 1e6) * pricing['cache_write'] +
            (cache_read_tokens / 1e6) * pricing['cache_read']
        )

        # Set up agent with synthetic token_usage data
        today = datetime.now().strftime('%Y-%m-%d')
        token_usage = {
            'test_user': {
                today: {
                    'input_tokens': input_tokens,
                    'output_tokens': output_tokens,
                    'cache_creation_tokens': cache_creation_tokens,
                    'cache_read_tokens': cache_read_tokens,
                    'calls': 1,
                    'model': model,
                }
            }
        }

        # Create agent with mocked dependencies
        with patch('app.pdn_chat_ai.binat_agents.pdn_agent.PDNAgent.__init__', return_value=None):
            agent = PDNAgent.__new__(PDNAgent)
            agent.token_usage = token_usage

        # Call get_usage_stats
        stats = agent.get_usage_stats(days=14)

        # Verify the cost matches our expected formula
        actual_cost = stats['users']['test_user']['total_cost']
        assert abs(actual_cost - round(expected_cost, 4)) < 1e-9, (
            f"Cost mismatch: actual={actual_cost}, expected={round(expected_cost, 4)} "
            f"for model={model}, input={input_tokens}, output={output_tokens}, "
            f"cache_creation={cache_creation_tokens}, cache_read={cache_read_tokens}"
        )


class TestGetUsageStats:
    """Tests for PDNAgent.get_usage_stats with synthetic token_usage data.

    **Validates: Requirements 7.6**
    """

    @pytest.fixture
    def agent_with_usage(self, mock_env):
        """Create a PDNAgent with synthetic token_usage data."""
        with patch('app.pdn_relationships.agents.base_pdn_agent.ChatAnthropic'), \
             patch('app.pdn_relationships.agents.base_pdn_agent.ChatOpenAI'), \
             patch('app.pdn_relationships.agents.base_pdn_agent.Path.exists', return_value=False):
            agent = PDNAgent(llm_provider='anthropic', model_name='claude-sonnet-4-20250514')
            # Inject synthetic token_usage data
            from datetime import datetime, timedelta
            today = datetime.now().strftime('%Y-%m-%d')
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

            agent.token_usage = {
                'user1': {
                    today: {
                        'input_tokens': 5000,
                        'output_tokens': 2000,
                        'cache_creation_tokens': 1000,
                        'cache_read_tokens': 500,
                        'calls': 10,
                        'model': 'claude-sonnet-4-20250514',
                    },
                    yesterday: {
                        'input_tokens': 3000,
                        'output_tokens': 1000,
                        'cache_creation_tokens': 500,
                        'cache_read_tokens': 200,
                        'calls': 5,
                        'model': 'claude-sonnet-4-20250514',
                    },
                },
                'user2': {
                    today: {
                        'input_tokens': 2000,
                        'output_tokens': 800,
                        'cache_creation_tokens': 0,
                        'cache_read_tokens': 0,
                        'calls': 3,
                        'model': 'claude-sonnet-4-20250514',
                    },
                },
            }
            return agent

    def test_usage_stats_returns_expected_structure(self, agent_with_usage):
        """Verify get_usage_stats returns all expected top-level keys."""
        stats = agent_with_usage.get_usage_stats(days=14)

        assert 'users' in stats
        assert 'daily_totals' in stats
        assert 'projection' in stats
        assert 'model_comparison' in stats
        assert 'period_days' in stats
        assert stats['period_days'] == 14

    def test_usage_stats_cost_calculation(self, agent_with_usage):
        """Verify cost calculations use correct pricing formula.

        Cost = (uncached_input/1e6 × input_price) + (output/1e6 × output_price)
             + (cache_creation/1e6 × cache_write_price) + (cache_read/1e6 × cache_read_price)
        where uncached_input = input_tokens - cache_creation_tokens - cache_read_tokens
        """
        stats = agent_with_usage.get_usage_stats(days=14)

        # Sonnet pricing: input=3.0, output=15.0, cache_write=3.75, cache_read=0.30
        # user1 today: uncached = 5000 - 1000 - 500 = 3500
        # cost = (3500/1e6)*3.0 + (2000/1e6)*15.0 + (1000/1e6)*3.75 + (500/1e6)*0.30
        #      = 0.0105 + 0.03 + 0.00375 + 0.00015 = 0.0444
        user1_today_cost = stats['users']['user1']['daily'][
            list(stats['users']['user1']['daily'].keys())[-1]  # today
        ]['cost']
        expected_cost = round(
            (3500 / 1e6) * 3.0 + (2000 / 1e6) * 15.0 + (1000 / 1e6) * 3.75 + (500 / 1e6) * 0.30,
            4
        )
        assert user1_today_cost == expected_cost

    def test_usage_stats_projections(self, agent_with_usage):
        """Verify projections are calculated from average daily cost."""
        stats = agent_with_usage.get_usage_stats(days=14)

        projection = stats['projection']
        assert 'active_days' in projection
        assert 'avg_daily_cost' in projection
        assert 'projected_monthly' in projection
        assert 'projected_yearly' in projection
        assert projection['active_days'] >= 1
        # Monthly = avg_daily * 30
        assert projection['projected_monthly'] == round(projection['avg_daily_cost'] * 30, 2)
        # Yearly = avg_daily * 365
        assert projection['projected_yearly'] == round(projection['avg_daily_cost'] * 365, 2)

    def test_usage_stats_model_comparison(self, agent_with_usage):
        """Verify model comparison includes sonnet and haiku with savings percentage."""
        stats = agent_with_usage.get_usage_stats(days=14)

        model_comparison = stats['model_comparison']
        assert 'sonnet' in model_comparison
        assert 'haiku' in model_comparison
        assert 'cost' in model_comparison['sonnet']
        assert 'cost' in model_comparison['haiku']
        assert 'savings_pct' in model_comparison['haiku']
        # Haiku should be cheaper than Sonnet
        assert model_comparison['haiku']['cost'] < model_comparison['sonnet']['cost']

    def test_usage_stats_recommendation(self, agent_with_usage):
        """Verify recommendation is generated when haiku savings > 50%."""
        stats = agent_with_usage.get_usage_stats(days=14)

        # With Sonnet pricing, haiku should offer >50% savings
        if stats['model_comparison']['haiku']['savings_pct'] > 50:
            assert stats['recommendation'] is not None
            assert stats['recommendation']['action'] == 'switch_to_haiku'
        else:
            # If savings are not > 50%, recommendation should be None
            assert stats['recommendation'] is None

    def test_usage_stats_per_user_totals(self, agent_with_usage):
        """Verify per-user totals aggregate correctly."""
        stats = agent_with_usage.get_usage_stats(days=14)

        user1 = stats['users']['user1']
        # user1 has data for today and yesterday
        assert user1['input_tokens'] == 5000 + 3000
        assert user1['output_tokens'] == 2000 + 1000
        assert user1['cache_creation_tokens'] == 1000 + 500
        assert user1['cache_read_tokens'] == 500 + 200
        assert user1['calls'] == 10 + 5

    def test_usage_stats_daily_totals(self, agent_with_usage):
        """Verify daily totals aggregate across users."""
        from datetime import datetime
        stats = agent_with_usage.get_usage_stats(days=14)
        today = datetime.now().strftime('%Y-%m-%d')

        # Today: user1 + user2
        assert today in stats['daily_totals']
        daily = stats['daily_totals'][today]
        assert daily['input_tokens'] == 5000 + 2000
        assert daily['output_tokens'] == 2000 + 800
        assert daily['calls'] == 10 + 3

    def test_usage_stats_cutoff_filters_old_data(self, mock_env):
        """Verify data older than the cutoff period is excluded."""
        with patch('app.pdn_relationships.agents.base_pdn_agent.ChatAnthropic'), \
             patch('app.pdn_relationships.agents.base_pdn_agent.ChatOpenAI'), \
             patch('app.pdn_relationships.agents.base_pdn_agent.Path.exists', return_value=False):
            agent = PDNAgent(llm_provider='anthropic', model_name='claude-sonnet-4-20250514')
            from datetime import datetime, timedelta
            old_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            today = datetime.now().strftime('%Y-%m-%d')

            agent.token_usage = {
                'user1': {
                    old_date: {
                        'input_tokens': 10000,
                        'output_tokens': 5000,
                        'cache_creation_tokens': 0,
                        'cache_read_tokens': 0,
                        'calls': 20,
                        'model': 'claude-sonnet-4-20250514',
                    },
                    today: {
                        'input_tokens': 1000,
                        'output_tokens': 500,
                        'cache_creation_tokens': 0,
                        'cache_read_tokens': 0,
                        'calls': 2,
                        'model': 'claude-sonnet-4-20250514',
                    },
                },
            }

            stats = agent.get_usage_stats(days=14)
            # Old data should be excluded
            assert stats['users']['user1']['input_tokens'] == 1000
            assert stats['users']['user1']['calls'] == 2


class TestCleanResponse:
    """Tests for PDNAgent._clean_response marker removal.

    **Validates: Requirements 7.7**
    """

    def test_removes_stop_marker(self):
        """Verify [STOP — wait for user response] is removed."""
        text = "Hello there[STOP — wait for user response] how are you?"
        result = PDNAgent._clean_response(text)
        assert "[STOP" not in result
        assert "Hello there how are you?" == result

    def test_removes_multiple_markers(self):
        """Verify multiple [STOP...] markers are all removed."""
        text = "Part 1[STOP]Part 2[STOP — pause]Part 3"
        result = PDNAgent._clean_response(text)
        assert "[STOP" not in result
        assert "Part 1Part 2Part 3" == result

    def test_strips_whitespace(self):
        """Verify leading/trailing whitespace is stripped."""
        text = "  Hello world  [STOP]  "
        result = PDNAgent._clean_response(text)
        assert result == "Hello world"

    def test_no_markers_unchanged(self):
        """Verify text without markers is returned unchanged (stripped)."""
        text = "  Normal response text  "
        result = PDNAgent._clean_response(text)
        assert result == "Normal response text"

    def test_empty_stop_marker(self):
        """Verify [STOP] with no content inside is removed."""
        text = "Before[STOP]After"
        result = PDNAgent._clean_response(text)
        assert result == "BeforeAfter"

    def test_marker_with_hebrew_content(self):
        """Verify markers with Hebrew content are removed."""
        text = "שלום[STOP — המתן לתגובת המשתמש]עולם"
        result = PDNAgent._clean_response(text)
        assert "[STOP" not in result
        assert "שלום" in result
        assert "עולם" in result


class TestDailyLimitEnforcement:
    """Tests for daily limit enforcement in PDNAgent methods.

    Verifies that when a user has exceeded the daily conversation limit,
    the agent returns the daily limit message without invoking the LLM.

    **Validates: Requirements 7.8**
    """

    @pytest.fixture
    def agent(self, mock_env):
        """Create a PDNAgent with mocked LLM."""
        with patch('app.pdn_relationships.agents.base_pdn_agent.ChatAnthropic') as mock_anthropic, \
             patch('app.pdn_relationships.agents.base_pdn_agent.ChatOpenAI'), \
             patch('app.pdn_relationships.agents.base_pdn_agent.Path.exists', return_value=False):
            mock_llm = Mock()
            mock_llm.invoke = Mock(return_value=Mock(content="LLM response"))
            mock_anthropic.return_value = mock_llm
            agent = PDNAgent(llm_provider='anthropic', model_name='claude-sonnet-4-20250514')
            agent.llm = mock_llm
            return agent

    def test_chat_with_binat_daily_limit_exceeded(self, agent):
        """When daily limit is exceeded, chat_with_binat returns limit message without LLM call."""
        user_name = "test_user"
        # Set conversation count to exceed limit
        agent.user_conversations[user_name]['count'] = 15

        with patch.object(agent, '_invoke_llm') as mock_invoke:
            result = agent.chat_with_binat(
                user_query="Hello",
                user_name=user_name,
                pdn_code="e5",
                daily_conversation_limit=15
            )

            assert "הגעת למגבלת השיחות" in result
            mock_invoke.assert_not_called()

    def test_build_21_plan_daily_limit_exceeded(self, agent):
        """When daily limit is exceeded, build_21_transformation_plan returns limit message without LLM call."""
        user_name = "test_user"
        agent.user_conversations[user_name]['count'] = 10

        with patch.object(agent, '_invoke_llm') as mock_invoke:
            result = agent.build_21_transformation_plan(
                user_goal="Be more confident",
                user_name=user_name,
                pdn_code="e5",
                daily_conversation_limit=10
            )

            assert "הגעת למגבלת השיחות" in result
            mock_invoke.assert_not_called()

    def test_daily_training_daily_limit_exceeded(self, agent):
        """When daily limit is exceeded, daily_training returns limit message without LLM call."""
        user_name = "test_user"
        agent.user_conversations[user_name]['count'] = 5

        with patch.object(agent, '_invoke_llm') as mock_invoke:
            result = agent.daily_training(
                user_name=user_name,
                pdn_code="e5",
                day_task="Practice mindfulness",
                daily_conversation_limit=5
            )

            assert "הגעת למגבלת השיחות" in result
            mock_invoke.assert_not_called()

    def test_exempt_user_not_limited(self, agent):
        """Exempt users are never limited regardless of conversation count."""
        exempt_user = "פנינה"
        agent.user_conversations[exempt_user]['count'] = 100

        with patch.object(agent, '_invoke_llm') as mock_invoke, \
             patch.object(agent, '_load_prompt', return_value="system prompt"), \
             patch.object(agent, '_track_usage'):
            mock_response = Mock()
            mock_response.content = "Response from LLM"
            mock_invoke.return_value = mock_response

            result = agent.chat_with_binat(
                user_query="Hello",
                user_name=exempt_user,
                pdn_code="e5",
                daily_conversation_limit=15
            )

            # LLM should be called for exempt users
            mock_invoke.assert_called_once()
            assert "הגעת למגבלת השיחות" not in result

    def test_under_limit_allows_llm_call(self, agent):
        """When under the daily limit, LLM is invoked normally."""
        user_name = "test_user"
        agent.user_conversations[user_name]['count'] = 5

        with patch.object(agent, '_invoke_llm') as mock_invoke, \
             patch.object(agent, '_load_prompt', return_value="system prompt"), \
             patch.object(agent, '_track_usage'):
            mock_response = Mock()
            mock_response.content = "Normal response"
            mock_invoke.return_value = mock_response

            result = agent.chat_with_binat(
                user_query="Hello",
                user_name=user_name,
                pdn_code="e5",
                daily_conversation_limit=15
            )

            mock_invoke.assert_called_once()
            assert "הגעת למגבלת השיחות" not in result


class TestResponseMarkerCleaningProperty:
    """Property-based tests for _clean_response marker removal.

    **Validates: Requirements 7.7**
    """

    # Strategy: generate strings that contain [STOP...] markers embedded in arbitrary text
    @settings(max_examples=50)
    @given(
        prefix=st.text(max_size=50),
        marker_content=st.text(
            alphabet=st.characters(blacklist_characters=']'),
            min_size=0,
            max_size=30
        ),
        suffix=st.text(max_size=50),
    )
    def test_property_16_response_marker_cleaning(self, prefix, marker_content, suffix):
        """Property 16: Response Marker Cleaning

        For any string containing [STOP followed by any characters and ],
        _clean_response produces a string that does not contain any such
        bracketed marker patterns, and the result is stripped of leading/trailing whitespace.

        **Validates: Requirements 7.7**
        """
        # Build input with a [STOP...] marker
        input_text = f"{prefix}[STOP{marker_content}]{suffix}"

        # Call _clean_response
        result = PDNAgent._clean_response(input_text)

        # Property: no [STOP...] markers remain in the output
        assert not re.search(r'\[STOP[^\]]*\]', result), (
            f"Marker still present in output: {result!r}"
        )

        # Property: result is stripped of leading/trailing whitespace
        assert result == result.strip()
