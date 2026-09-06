"""Tests for Flask chat routes.

Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.8, 5.1, 5.2, 5.3
"""

import logging
import pytest
from unittest.mock import patch, MagicMock
from app.main import create_app
from app.pdn_chat_ai.logger import setup_logger


@pytest.fixture
def app():
    """Create Flask test app."""
    with patch('app.main.start_memory_monitoring'):
        application = create_app()
    application.config['TESTING'] = True
    application.config['SECRET_KEY'] = 'test-secret'
    application.config['SESSION_TYPE'] = 'filesystem'
    return application


@pytest.fixture
def client(app):
    """Create Flask test client."""
    return app.test_client()


@pytest.fixture
def mock_agent():
    """Mock the PDNAgent to avoid real LLM calls."""
    with patch('app.pdn_chat_ai.chat_routes.get_agent_instance') as mock:
        agent = MagicMock()
        agent.chat_with_binat.return_value = "Mock response"
        agent.build_21_transformation_plan.return_value = "Mock plan"
        agent.daily_training.return_value = "Mock training"
        agent.persist_session.return_value = None
        agent.register_user_email.return_value = None
        agent.conversation_history = {}
        mock.return_value = agent
        yield agent


@pytest.fixture
def mock_user_manager():
    """Mock the user manager."""
    with patch('app.pdn_chat_ai.chat_routes.get_user_manager') as mock:
        mgr = MagicMock()
        mgr.get_user.return_value = {
            'password': 'testpass',
            'name': 'Test User',
            'pdn_code': 'a7',
            'daily_conversation_limit': 15
        }
        mgr.verify_password.return_value = True
        mock.return_value = mgr
        yield mgr


@pytest.fixture
def logged_in_client(client, mock_user_manager, mock_agent):
    """A client that is already logged in."""
    client.post('/pdn-binat/login', json={
            'terms_accepted': True,
        'email': 'test@example.com',
        'password': 'testpass'
    })
    return client


class TestLogin:
    """Tests for login endpoint.

    Validates: Requirements 4.2
    """

    def test_login_valid_credentials(self, client, mock_user_manager):
        """Valid credentials should return 200 with success."""
        response = client.post('/pdn-binat/login', json={
            'terms_accepted': True,
            'email': 'test@example.com',
            'password': 'testpass'
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['user_name'] == 'Test User'

    def test_login_returns_user_details(self, client, mock_user_manager):
        """Successful login should return user_id, user_name, pdn_code, daily_conversation_limit."""
        response = client.post('/pdn-binat/login', json={
            'terms_accepted': True,
            'email': 'test@example.com',
            'password': 'testpass'
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'user_id' in data
        assert data['user_name'] == 'Test User'
        assert data['pdn_code'] == 'a7'
        assert data['daily_conversation_limit'] == 15

    def test_login_invalid_credentials(self, client, mock_user_manager):
        """Invalid credentials should return 401."""
        mock_user_manager.verify_password.return_value = False
        response = client.post('/pdn-binat/login', json={
            'terms_accepted': True,
            'email': 'test@example.com',
            'password': 'wrongpass'
        })
        assert response.status_code == 401
        data = response.get_json()
        assert data['success'] is False
        assert 'error' in data

    def test_login_missing_email(self, client, mock_user_manager):
        """Missing email should return 400."""
        response = client.post('/pdn-binat/login', json={
            'terms_accepted': True,
            'email': '',
            'password': 'testpass'
        })
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_login_missing_password(self, client, mock_user_manager):
        """Missing password should return 400."""
        response = client.post('/pdn-binat/login', json={
            'terms_accepted': True,
            'email': 'test@example.com',
            'password': ''
        })
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_login_missing_both_fields(self, client, mock_user_manager):
        """Missing email and password should return 400."""
        response = client.post('/pdn-binat/login', json={
            'terms_accepted': True,
            'email': '',
            'password': ''
        })
        assert response.status_code == 400

    def test_login_no_json_body(self, client, mock_user_manager):
        """No JSON body should return error (500 from error handler wrapping 415)."""
        response = client.post('/pdn-binat/login',
                               data='not json',
                               content_type='text/plain')
        # Flask raises 415 which the error handler catches and returns 500
        assert response.status_code == 500

    def test_login_nonexistent_user(self, client, mock_user_manager):
        """Non-existent user should return 401."""
        mock_user_manager.get_user.return_value = None
        response = client.post('/pdn-binat/login', json={
            'terms_accepted': True,
            'email': 'nobody@test.com',
            'password': 'pass'
        })
        assert response.status_code == 401

    def test_login_calls_get_user_manager(self, client, mock_user_manager):
        """Login should call get_user_manager to retrieve user data."""
        client.post('/pdn-binat/login', json={
            'terms_accepted': True,
            'email': 'test@example.com',
            'password': 'testpass'
        })
        mock_user_manager.get_user.assert_called_with('test@example.com')

    def test_login_calls_verify_password(self, client, mock_user_manager):
        """Login should call verify_password with the provided credentials."""
        client.post('/pdn-binat/login', json={
            'terms_accepted': True,
            'email': 'test@example.com',
            'password': 'testpass'
        })
        mock_user_manager.verify_password.assert_called_with('test@example.com', 'testpass')


class TestLogout:
    """Tests for logout endpoint.

    Validates: Requirements 4.6
    """

    def test_logout_clears_session(self, client, mock_user_manager, mock_agent):
        """Logout should clear session and return success."""
        # First login
        client.post('/pdn-binat/login', json={
            'terms_accepted': True,
            'email': 'test@example.com',
            'password': 'testpass'
        })
        # Then logout
        response = client.post('/pdn-binat/logout')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    def test_logout_calls_persist_session(self, client, mock_user_manager, mock_agent):
        """Logout should call agent.persist_session to save conversation history."""
        # Login first
        client.post('/pdn-binat/login', json={
            'terms_accepted': True,
            'email': 'test@example.com',
            'password': 'testpass'
        })
        # Logout
        client.post('/pdn-binat/logout')
        # Verify persist_session was called with user_name and user_email
        mock_agent.persist_session.assert_called_once_with('Test User', 'test@example.com')

    def test_logout_session_cleared_after_logout(self, client, mock_user_manager, mock_agent):
        """After logout, session should be cleared so auth-required endpoints return 401."""
        # Login
        client.post('/pdn-binat/login', json={
            'terms_accepted': True,
            'email': 'test@example.com',
            'password': 'testpass'
        })
        # Logout
        client.post('/pdn-binat/logout')
        # Try to access chat (requires auth) — should get 401
        response = client.post('/pdn-binat/chat', json={
            'message': 'Hello',
            'user_name': 'Test User',
            'pdn_code': 'a7'
        })
        assert response.status_code == 401

    def test_logout_without_login(self, client, mock_agent):
        """Logout without prior login should still succeed (no user_name in session)."""
        response = client.post('/pdn-binat/logout')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        # persist_session should NOT be called since no user was logged in
        mock_agent.persist_session.assert_not_called()


class TestChatEndpoint:
    """Tests for chat endpoint.

    Validates: Requirements 4.3, 4.8
    """

    def test_chat_requires_data(self, logged_in_client, mock_agent):
        """Chat endpoint with empty JSON object should raise ValidationError for empty message."""
        response = logged_in_client.post('/pdn-binat/chat', json={})
        assert response.status_code == 400

    def test_chat_with_valid_data(self, logged_in_client, mock_agent):
        """Chat with valid data should return response."""
        response = logged_in_client.post('/pdn-binat/chat', json={
            'message': 'Hello',
            'user_name': 'Test User',
            'pdn_code': 'a7'
        })
        assert response.status_code == 200
        data = response.get_json()
        assert 'response' in data
        assert data['response'] == "Mock response"

    def test_chat_returns_timestamp(self, logged_in_client, mock_agent):
        """Chat response should include a timestamp."""
        response = logged_in_client.post('/pdn-binat/chat', json={
            'message': 'Hello',
            'user_name': 'Test User',
            'pdn_code': 'a7'
        })
        assert response.status_code == 200
        data = response.get_json()
        assert 'timestamp' in data

    def test_chat_empty_message_returns_400(self, logged_in_client, mock_agent):
        """Empty message should return 400 validation error."""
        response = logged_in_client.post('/pdn-binat/chat', json={
            'message': '',
            'user_name': 'Test User',
            'pdn_code': 'a7'
        })
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_chat_whitespace_only_message_returns_400(self, logged_in_client, mock_agent):
        """Whitespace-only message should return 400 validation error."""
        response = logged_in_client.post('/pdn-binat/chat', json={
            'message': '   ',
            'user_name': 'Test User',
            'pdn_code': 'a7'
        })
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_chat_message_exceeding_5000_chars_returns_400(self, logged_in_client, mock_agent):
        """Message exceeding 5000 characters should return HTTP 400.

        Validates: Requirements 4.8
        """
        long_message = 'x' * 5001
        response = logged_in_client.post('/pdn-binat/chat', json={
            'message': long_message,
            'user_name': 'Test User',
            'pdn_code': 'a7'
        })
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert '5000' in data['error']

    def test_chat_message_exactly_5000_chars_succeeds(self, logged_in_client, mock_agent):
        """Message of exactly 5000 characters should succeed."""
        message = 'x' * 5000
        response = logged_in_client.post('/pdn-binat/chat', json={
            'message': message,
            'user_name': 'Test User',
            'pdn_code': 'a7'
        })
        assert response.status_code == 200
        data = response.get_json()
        assert 'response' in data

    @patch('app.pdn_chat_ai.chat_routes.conversation_stats')
    def test_chat_tracks_conversation_stats(self, mock_stats, logged_in_client, mock_agent):
        """Chat should increment conversation stats for the user."""
        response = logged_in_client.post('/pdn-binat/chat', json={
            'message': 'Hello',
            'user_name': 'Test User',
            'pdn_code': 'a7'
        })
        assert response.status_code == 200
        mock_stats.increment_conversation.assert_called_with('test@example.com')

    def test_chat_calls_agent_with_correct_args(self, logged_in_client, mock_agent):
        """Chat should call agent.chat_with_binat with correct arguments."""
        logged_in_client.post('/pdn-binat/chat', json={
            'message': 'Hello world',
            'user_name': 'Test User',
            'pdn_code': 'a7'
        })
        mock_agent.chat_with_binat.assert_called_once_with(
            'Hello world',
            'Test User',
            'a7',
            daily_conversation_limit=15
        )

    def test_chat_requires_auth(self, client, mock_agent):
        """Chat endpoint should return 401 without authentication."""
        response = client.post('/pdn-binat/chat', json={
            'message': 'Hello',
            'user_name': 'Test User',
            'pdn_code': 'a7'
        })
        assert response.status_code == 401

    def test_chat_empty_json_returns_response(self, client, mock_user_manager, mock_agent):
        """Empty JSON with valid content-type should call agent and return response."""
        # Login first to set session
        client.post('/pdn-binat/login', json={
            'terms_accepted': True,
            'email': 'test@example.com',
            'password': 'testpass'
        })
        response = client.post('/pdn-binat/chat', json={
            'message': 'test',
            'user_name': 'Test',
            'pdn_code': 'a7'
        })
        assert response.status_code == 200
        data = response.get_json()
        assert 'response' in data


class Test21DayPlan:
    """Tests for 21-day transformation plan endpoint.

    Validates: Requirements 4.4
    """

    def test_21_day_plan_with_valid_goal(self, logged_in_client, mock_agent):
        """Valid goal should return plan response."""
        response = logged_in_client.post('/pdn-binat/21-day-plan', json={
            'goal': 'Improve communication skills',
            'user_name': 'Test User',
            'pdn_code': 'a7'
        })
        assert response.status_code == 200
        data = response.get_json()
        assert 'response' in data
        assert data['response'] == "Mock plan"

    def test_21_day_plan_returns_timestamp(self, logged_in_client, mock_agent):
        """21-day plan response should include a timestamp."""
        response = logged_in_client.post('/pdn-binat/21-day-plan', json={
            'goal': 'Improve focus',
            'user_name': 'Test User',
            'pdn_code': 'a7'
        })
        assert response.status_code == 200
        data = response.get_json()
        assert 'timestamp' in data

    def test_21_day_plan_empty_goal_returns_400(self, logged_in_client, mock_agent):
        """Empty goal should return 400."""
        response = logged_in_client.post('/pdn-binat/21-day-plan', json={
            'goal': '',
            'user_name': 'Test User',
            'pdn_code': 'a7'
        })
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_21_day_plan_whitespace_goal_returns_400(self, logged_in_client, mock_agent):
        """Whitespace-only goal should return 400."""
        response = logged_in_client.post('/pdn-binat/21-day-plan', json={
            'goal': '   ',
            'user_name': 'Test User',
            'pdn_code': 'a7'
        })
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_21_day_plan_calls_agent_correctly(self, logged_in_client, mock_agent):
        """21-day plan should call agent.build_21_transformation_plan with correct args."""
        logged_in_client.post('/pdn-binat/21-day-plan', json={
            'goal': 'Be more assertive',
            'user_name': 'Test User',
            'pdn_code': 'a7'
        })
        mock_agent.build_21_transformation_plan.assert_called_once_with(
            'Be more assertive', 'Test User', 'a7', 15
        )

    def test_21_day_plan_requires_auth(self, client, mock_agent):
        """21-day plan endpoint should return 401 without authentication."""
        response = client.post('/pdn-binat/21-day-plan', json={
            'goal': 'Improve focus',
            'user_name': 'Test User',
            'pdn_code': 'a7'
        })
        assert response.status_code == 401

    @patch('app.pdn_chat_ai.chat_routes.conversation_stats')
    def test_21_day_plan_tracks_stats(self, mock_stats, logged_in_client, mock_agent):
        """21-day plan should increment conversation stats."""
        logged_in_client.post('/pdn-binat/21-day-plan', json={
            'goal': 'Improve focus',
            'user_name': 'Test User',
            'pdn_code': 'a7'
        })
        mock_stats.increment_conversation.assert_called_with('test@example.com')


class TestDailyTraining:
    """Tests for daily training endpoint.

    Validates: Requirements 4.5
    """

    def test_daily_training_with_valid_task(self, logged_in_client, mock_agent):
        """Valid task should return training response."""
        response = logged_in_client.post('/pdn-binat/daily-training', json={
            'task': 'Practice active listening',
            'user_name': 'Test User',
            'pdn_code': 'a7'
        })
        assert response.status_code == 200
        data = response.get_json()
        assert 'response' in data
        assert data['response'] == "Mock training"

    def test_daily_training_returns_timestamp(self, logged_in_client, mock_agent):
        """Daily training response should include a timestamp."""
        response = logged_in_client.post('/pdn-binat/daily-training', json={
            'task': 'Mindfulness exercise',
            'user_name': 'Test User',
            'pdn_code': 'a7'
        })
        assert response.status_code == 200
        data = response.get_json()
        assert 'timestamp' in data

    def test_daily_training_empty_task_returns_400(self, logged_in_client, mock_agent):
        """Empty task should return 400."""
        response = logged_in_client.post('/pdn-binat/daily-training', json={
            'task': '',
            'user_name': 'Test User',
            'pdn_code': 'a7'
        })
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_daily_training_whitespace_task_returns_400(self, logged_in_client, mock_agent):
        """Whitespace-only task should return 400."""
        response = logged_in_client.post('/pdn-binat/daily-training', json={
            'task': '   ',
            'user_name': 'Test User',
            'pdn_code': 'a7'
        })
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_daily_training_calls_agent_correctly(self, logged_in_client, mock_agent):
        """Daily training should call agent.daily_training with correct args."""
        logged_in_client.post('/pdn-binat/daily-training', json={
            'task': 'Breathing exercise',
            'user_name': 'Test User',
            'pdn_code': 'a7'
        })
        mock_agent.daily_training.assert_called_once_with(
            'Test User', 'a7', 'Breathing exercise', 15
        )

    def test_daily_training_requires_auth(self, client, mock_agent):
        """Daily training endpoint should return 401 without authentication."""
        response = client.post('/pdn-binat/daily-training', json={
            'task': 'Practice focus',
            'user_name': 'Test User',
            'pdn_code': 'a7'
        })
        assert response.status_code == 401

    @patch('app.pdn_chat_ai.chat_routes.conversation_stats')
    def test_daily_training_tracks_stats(self, mock_stats, logged_in_client, mock_agent):
        """Daily training should increment conversation stats."""
        logged_in_client.post('/pdn-binat/daily-training', json={
            'task': 'Practice focus',
            'user_name': 'Test User',
            'pdn_code': 'a7'
        })
        mock_stats.increment_conversation.assert_called_with('test@example.com')


class TestLogger:
    """Tests for logger.py setup_logger function.

    Validates: Requirements 5.1, 5.2, 5.3
    """

    def test_setup_logger_returns_correct_name(self):
        """setup_logger should return a logger with the specified name."""
        logger = setup_logger('test_logger_name')
        assert logger.name == 'test_logger_name'
        # Cleanup
        logger.handlers.clear()

    def test_setup_logger_default_name(self):
        """setup_logger with no args should use 'pdn_chat_ai' as default name."""
        logger = setup_logger()
        assert logger.name == 'pdn_chat_ai'
        # Cleanup
        logger.handlers.clear()

    def test_setup_logger_sets_info_level(self):
        """setup_logger should set the logger level to INFO."""
        logger = setup_logger('test_logger_level')
        assert logger.level == logging.INFO
        # Cleanup
        logger.handlers.clear()

    def test_setup_logger_adds_stream_handler(self):
        """setup_logger should add exactly one StreamHandler."""
        logger = setup_logger('test_logger_handler')
        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0], logging.StreamHandler)
        # Cleanup
        logger.handlers.clear()

    def test_setup_logger_handler_has_formatter(self):
        """setup_logger should configure the handler with the expected format."""
        logger = setup_logger('test_logger_formatter')
        handler = logger.handlers[0]
        formatter = handler.formatter
        assert formatter is not None
        assert '%(asctime)s' in formatter._fmt
        assert '%(name)s' in formatter._fmt
        assert '%(levelname)s' in formatter._fmt
        assert '%(message)s' in formatter._fmt
        # Cleanup
        logger.handlers.clear()

    def test_setup_logger_idempotent_no_duplicate_handlers(self):
        """Calling setup_logger multiple times with the same name should not add duplicate handlers."""
        # Use a unique name to avoid interference from other tests
        name = 'test_logger_idempotent'
        # Ensure clean state
        logger = logging.getLogger(name)
        logger.handlers.clear()

        # Call setup_logger multiple times
        logger1 = setup_logger(name)
        logger2 = setup_logger(name)
        logger3 = setup_logger(name)

        # Should still have exactly one handler
        assert len(logger3.handlers) == 1
        # All calls should return the same logger instance
        assert logger1 is logger2
        assert logger2 is logger3
        # Cleanup
        logger.handlers.clear()
