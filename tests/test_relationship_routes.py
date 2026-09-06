"""Tests for relationship advisor Flask routes.

Tests login validation, chat endpoint, and logout session management.
Requirements: Route-level validation and flow.
"""

import pytest
from unittest.mock import patch, MagicMock
from flask import Flask

from app.pdn_relationships.constants import PDN_CODES, RelationshipType
from app.pdn_relationships.relationship_routes import pdn_relationships_bp, handle_errors


@pytest.fixture
def app():
    """Create a minimal Flask test app with the relationship blueprint."""
    application = Flask(__name__)
    application.config['TESTING'] = True
    application.config['SECRET_KEY'] = 'test-secret-key'
    application.config['SESSION_TYPE'] = 'filesystem'
    application.register_blueprint(pdn_relationships_bp, url_prefix='/pdn-relationships')
    return application


@pytest.fixture
def client(app):
    """Create Flask test client."""
    return app.test_client()


@pytest.fixture
def mock_user_manager():
    """Mock the user manager to return a valid user."""
    with patch('app.pdn_relationships.relationship_routes.get_user_manager') as mock_um:
        mgr = MagicMock()
        mgr.get_user.return_value = {
            'password': 'testpass',
            'name': 'Test User',
            'pdn_code': 'a3',
            'daily_conversation_limit': 15,
        }
        # verify_password returns True only when password matches 'testpass'
        mgr.verify_password.side_effect = lambda email, pwd: pwd == 'testpass'
        mock_um.return_value = mgr
        yield mgr


@pytest.fixture
def mock_agent():
    """Mock the RelationshipAgent to avoid real LLM calls."""
    with patch('app.pdn_relationships.relationship_routes.get_relationship_agent') as mock_factory:
        agent = MagicMock()
        agent.chat.return_value = "תשובה מהיועץ"
        agent.persist_session.return_value = None
        agent.register_user_email.return_value = None
        agent.conversation_history = {}
        mock_factory.return_value = agent
        yield agent


@pytest.fixture
def mock_history_service():
    """Mock the history service."""
    with patch('app.pdn_relationships.relationship_routes._history_service') as mock_hs:
        mock_hs.load_user_history.return_value = None
        yield mock_hs


@pytest.fixture
def mock_conversation_stats():
    """Mock conversation_stats to verify stats tracking."""
    with patch('app.pdn_relationships.relationship_routes.conversation_stats') as mock_cs:
        yield mock_cs


class TestLogin:
    """Tests for the login endpoint.

    Validates: Requirements 10.1, 10.2
    """

    def test_login_valid_credentials(self, client, mock_user_manager, mock_agent, mock_history_service):
        """Valid credentials with valid partner_code and relationship_type returns 200."""
        response = client.post('/pdn-relationships/login', json={
            'email': 'test@example.com',
            'password': 'testpass',
            'partner_code': 'e5',
            'relationship_type': 'partner',
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['user_name'] == 'Test User'
        assert data['partner_code'] == 'e5'
        assert data['relationship_type'] == 'partner'

    def test_login_invalid_partner_code_returns_400(self, client, mock_user_manager):
        """Invalid partner_code should return 400."""
        response = client.post('/pdn-relationships/login', json={
            'email': 'test@example.com',
            'password': 'testpass',
            'partner_code': 'invalid_code',
            'relationship_type': 'partner',
        })
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_login_invalid_relationship_type_returns_400(self, client, mock_user_manager):
        """Invalid relationship_type should return 400."""
        response = client.post('/pdn-relationships/login', json={
            'email': 'test@example.com',
            'password': 'testpass',
            'partner_code': 'a3',
            'relationship_type': 'enemy',
        })
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_login_wrong_password_returns_401(self, client, mock_user_manager, mock_history_service):
        """Wrong password should return 401."""
        mock_user_manager.get_user.return_value = {
            'password': 'correctpass',
            'name': 'Test User',
            'pdn_code': 'a3',
            'daily_conversation_limit': 15,
        }
        mock_user_manager.verify_password.side_effect = lambda email, pwd: pwd == 'correctpass'
        response = client.post('/pdn-relationships/login', json={
            'email': 'test@example.com',
            'password': 'wrongpass',
            'partner_code': 'e5',
            'relationship_type': 'partner',
        })
        assert response.status_code == 401
        data = response.get_json()
        assert data['success'] is False

    def test_login_missing_email_returns_400(self, client, mock_user_manager):
        """Missing email should return 400."""
        response = client.post('/pdn-relationships/login', json={
            'email': '',
            'password': 'testpass',
            'partner_code': 'e5',
            'relationship_type': 'partner',
        })
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'required' in data['error'].lower() or 'email' in data['error'].lower()

    def test_login_missing_password_returns_400(self, client, mock_user_manager):
        """Missing password should return 400."""
        response = client.post('/pdn-relationships/login', json={
            'email': 'test@example.com',
            'password': '',
            'partner_code': 'e5',
            'relationship_type': 'partner',
        })
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_login_no_data_returns_error(self, client, mock_user_manager):
        """No JSON body (wrong content type) should return an error status."""
        response = client.post('/pdn-relationships/login',
                               data='not json',
                               content_type='text/plain')
        # UnsupportedMediaType is caught by handle_errors as generic Exception → 500
        assert response.status_code == 500

    def test_login_nonexistent_user_returns_401(self, client, mock_user_manager, mock_history_service):
        """Non-existent user (get_user returns None) should return 401."""
        mock_user_manager.get_user.return_value = None
        response = client.post('/pdn-relationships/login', json={
            'email': 'nobody@example.com',
            'password': 'testpass',
            'partner_code': 'e5',
            'relationship_type': 'partner',
        })
        assert response.status_code == 401
        data = response.get_json()
        assert data['success'] is False

    def test_login_verifies_get_user_manager_called(self, client, mock_user_manager, mock_agent, mock_history_service):
        """Login should call get_user_manager to retrieve user data."""
        client.post('/pdn-relationships/login', json={
            'email': 'test@example.com',
            'password': 'testpass',
            'partner_code': 'e5',
            'relationship_type': 'partner',
        })
        mock_user_manager.get_user.assert_called_with('test@example.com')
        mock_user_manager.verify_password.assert_called_with('test@example.com', 'testpass')

    def test_login_all_valid_relationship_types(self, client, mock_user_manager, mock_agent, mock_history_service):
        """All valid relationship types should be accepted."""
        for rt in ['partner', 'friend', 'colleague']:
            response = client.post('/pdn-relationships/login', json={
                'email': 'test@example.com',
                'password': 'testpass',
                'partner_code': 'e5',
                'relationship_type': rt,
            })
            assert response.status_code == 200, f"Failed for relationship_type={rt}"

    def test_login_all_valid_partner_codes(self, client, mock_user_manager, mock_agent, mock_history_service):
        """All valid PDN codes should be accepted as partner_code."""
        for code in PDN_CODES:
            response = client.post('/pdn-relationships/login', json={
                'email': 'test@example.com',
                'password': 'testpass',
                'partner_code': code,
                'relationship_type': 'partner',
            })
            assert response.status_code == 200, f"Failed for partner_code={code}"

    def test_login_partner_code_case_insensitive(self, client, mock_user_manager, mock_agent, mock_history_service):
        """Partner code should be case-insensitive (lowered before validation)."""
        response = client.post('/pdn-relationships/login', json={
            'email': 'test@example.com',
            'password': 'testpass',
            'partner_code': 'E5',
            'relationship_type': 'partner',
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['partner_code'] == 'e5'

    def test_login_sets_session_data(self, client, mock_user_manager, mock_agent, mock_history_service):
        """Successful login should set session data correctly."""
        client.post('/pdn-relationships/login', json={
            'email': 'test@example.com',
            'password': 'testpass',
            'partner_code': 'e5',
            'relationship_type': 'partner',
        })
        with client.session_transaction() as sess:
            assert sess['user_email'] == 'test@example.com'
            assert sess['user_name'] == 'Test User'
            assert sess['pdn_code'] == 'a3'
            assert sess['partner_code'] == 'e5'
            assert sess['relationship_type'] == 'partner'
            assert sess['daily_conversation_limit'] == 15


class TestChat:
    """Tests for the chat endpoint.

    Validates: Requirements 10.3, 10.6
    """

    def _login(self, client, mock_user_manager, mock_agent, mock_history_service):
        """Helper to login before chat tests."""
        client.post('/pdn-relationships/login', json={
            'email': 'test@example.com',
            'password': 'testpass',
            'partner_code': 'e5',
            'relationship_type': 'partner',
        })

    def test_chat_returns_response_with_timestamp(self, client, mock_user_manager, mock_agent, mock_history_service, mock_conversation_stats):
        """Chat endpoint should return response text and a timestamp."""
        self._login(client, mock_user_manager, mock_agent, mock_history_service)

        response = client.post('/pdn-relationships/chat', json={
            'message': 'שלום, אני צריך עזרה',
            'user_name': 'Test User',
            'pdn_code': 'a3',
            'partner_code': 'e5',
            'relationship_type': 'partner',
        })
        assert response.status_code == 200
        data = response.get_json()
        assert 'response' in data
        assert 'timestamp' in data
        assert data['response'] == "תשובה מהיועץ"

    def test_chat_empty_message_returns_400(self, client, mock_user_manager, mock_agent, mock_history_service, mock_conversation_stats):
        """Empty message should return 400."""
        self._login(client, mock_user_manager, mock_agent, mock_history_service)

        response = client.post('/pdn-relationships/chat', json={
            'message': '',
            'user_name': 'Test User',
            'pdn_code': 'a3',
            'partner_code': 'e5',
            'relationship_type': 'partner',
        })
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'empty' in data['error'].lower()

    def test_chat_message_exceeding_5000_chars_returns_400(self, client, mock_user_manager, mock_agent, mock_history_service, mock_conversation_stats):
        """Message exceeding 5000 characters should return HTTP 400."""
        self._login(client, mock_user_manager, mock_agent, mock_history_service)

        long_message = 'א' * 5001
        response = client.post('/pdn-relationships/chat', json={
            'message': long_message,
            'user_name': 'Test User',
            'pdn_code': 'a3',
            'partner_code': 'e5',
            'relationship_type': 'partner',
        })
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert '5000' in data['error']

    def test_chat_message_exactly_5000_chars_succeeds(self, client, mock_user_manager, mock_agent, mock_history_service, mock_conversation_stats):
        """Message of exactly 5000 characters should succeed."""
        self._login(client, mock_user_manager, mock_agent, mock_history_service)

        exact_message = 'a' * 5000
        response = client.post('/pdn-relationships/chat', json={
            'message': exact_message,
            'user_name': 'Test User',
            'pdn_code': 'a3',
            'partner_code': 'e5',
            'relationship_type': 'partner',
        })
        assert response.status_code == 200

    def test_chat_tracks_conversation_stats(self, client, mock_user_manager, mock_agent, mock_history_service, mock_conversation_stats):
        """Chat should increment conversation stats for the user."""
        self._login(client, mock_user_manager, mock_agent, mock_history_service)

        client.post('/pdn-relationships/chat', json={
            'message': 'Hello',
            'user_name': 'Test User',
            'pdn_code': 'a3',
            'partner_code': 'e5',
            'relationship_type': 'partner',
        })
        mock_conversation_stats.increment_conversation.assert_called_with('test@example.com')

    def test_chat_calls_agent_with_correct_params(self, client, mock_user_manager, mock_agent, mock_history_service, mock_conversation_stats):
        """Chat should call agent.chat with the correct parameters."""
        self._login(client, mock_user_manager, mock_agent, mock_history_service)

        client.post('/pdn-relationships/chat', json={
            'message': 'Help me',
            'user_name': 'Test User',
            'pdn_code': 'a3',
            'partner_code': 'e5',
            'relationship_type': 'partner',
        })
        mock_agent.chat.assert_called_once_with(
            message='Help me',
            user_name='Test User',
            user_code='a3',
            partner_code='e5',
            relationship_type='partner',
            daily_conversation_limit=15,
        )

    def test_chat_registers_user_email(self, client, mock_user_manager, mock_agent, mock_history_service, mock_conversation_stats):
        """Chat should register user email mapping on the agent."""
        self._login(client, mock_user_manager, mock_agent, mock_history_service)

        client.post('/pdn-relationships/chat', json={
            'message': 'Hello',
            'user_name': 'Test User',
            'pdn_code': 'a3',
            'partner_code': 'e5',
            'relationship_type': 'partner',
        })
        mock_agent.register_user_email.assert_called_with('Test User', 'test@example.com')

    def test_chat_no_data_returns_error(self, client, mock_user_manager, mock_agent, mock_history_service, mock_conversation_stats):
        """No JSON body (wrong content type) should return an error status."""
        self._login(client, mock_user_manager, mock_agent, mock_history_service)

        response = client.post('/pdn-relationships/chat',
                               data='not json',
                               content_type='text/plain')
        # UnsupportedMediaType is caught by handle_errors as generic Exception → 500
        assert response.status_code == 500

    def test_chat_without_auth_returns_401(self, client, mock_agent, mock_conversation_stats):
        """Chat without authentication should return 401."""
        response = client.post('/pdn-relationships/chat', json={
            'message': 'Hello',
            'user_name': 'Test User',
            'pdn_code': 'a3',
            'partner_code': 'e5',
            'relationship_type': 'partner',
        })
        assert response.status_code == 401

    def test_chat_injects_persisted_history(self, client, mock_user_manager, mock_agent, mock_history_service, mock_conversation_stats):
        """Chat should inject persisted history from session into agent on first message."""
        # Set up history service to return a payload during login
        from app.utils.user_history_service import UserHistoryPayload
        history_payload = UserHistoryPayload(
            schema_version="1.0",
            user_id="test@example.com",
            updated_at="2025-01-15T10:00:00",
            summary="Previous conversation summary",
            metadata={"last_session_date": "2025-01-14"},
        )
        mock_history_service.load_user_history.return_value = history_payload

        # Need to set up conversation_history dict for the agent
        from collections import defaultdict
        mock_history_obj = MagicMock()
        mock_history_obj.summary = ""
        mock_agent.conversation_history = defaultdict(lambda: mock_history_obj)

        self._login(client, mock_user_manager, mock_agent, mock_history_service)

        # First chat message should inject history
        client.post('/pdn-relationships/chat', json={
            'message': 'Hello',
            'user_name': 'Test User',
            'pdn_code': 'a3',
            'partner_code': 'e5',
            'relationship_type': 'partner',
        })

        # Verify the summary was set on the agent's conversation history
        assert 'Previous conversation summary' in mock_history_obj.summary


class TestLogout:
    """Tests for the logout endpoint.

    Validates: Requirements 10.4
    """

    def test_logout_persists_history_and_clears_session(self, client, mock_user_manager, mock_agent, mock_history_service, mock_conversation_stats):
        """Logout should persist history and clear session."""
        # Login first
        client.post('/pdn-relationships/login', json={
            'email': 'test@example.com',
            'password': 'testpass',
            'partner_code': 'e5',
            'relationship_type': 'partner',
        })

        # Logout
        response = client.post('/pdn-relationships/logout')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

        # Verify persist_session was called with correct args
        mock_agent.persist_session.assert_called_once_with('Test User', 'test@example.com')

        # Verify session is cleared (accessing chat-page should have empty session values)
        with client.session_transaction() as sess:
            assert 'user_email' not in sess
            assert 'user_name' not in sess

    def test_logout_without_auth_returns_401(self, client, mock_agent):
        """Logout without authentication should return 401."""
        response = client.post('/pdn-relationships/logout')
        assert response.status_code == 401

    def test_logout_clears_all_session_keys(self, client, mock_user_manager, mock_agent, mock_history_service, mock_conversation_stats):
        """Logout should clear all session keys."""
        # Login first
        client.post('/pdn-relationships/login', json={
            'email': 'test@example.com',
            'password': 'testpass',
            'partner_code': 'e5',
            'relationship_type': 'partner',
        })

        # Logout
        client.post('/pdn-relationships/logout')

        # Verify all relationship-related session keys are cleared
        with client.session_transaction() as sess:
            assert 'user_email' not in sess
            assert 'user_name' not in sess
            assert 'pdn_code' not in sess
            assert 'partner_code' not in sess
            assert 'relationship_type' not in sess
            assert 'daily_conversation_limit' not in sess
            assert 'user_id' not in sess

    def test_logout_returns_success_message(self, client, mock_user_manager, mock_agent, mock_history_service, mock_conversation_stats):
        """Logout should return success message."""
        # Login first
        client.post('/pdn-relationships/login', json={
            'email': 'test@example.com',
            'password': 'testpass',
            'partner_code': 'e5',
            'relationship_type': 'partner',
        })

        response = client.post('/pdn-relationships/logout')
        data = response.get_json()
        assert data['success'] is True
        assert 'message' in data


class TestHandleErrors:
    """Tests for the handle_errors decorator.

    Validates: Requirements 10.5
    """

    def test_value_error_returns_400(self, app):
        """ValueError should be mapped to HTTP 400."""
        with app.test_request_context():
            @handle_errors
            def raise_value_error():
                raise ValueError("Invalid input")

            response, status_code = raise_value_error()
            assert status_code == 400
            data = response.get_json()
            assert 'error' in data
            assert 'Invalid input' in data['error']

    def test_timeout_error_returns_503(self, app):
        """TimeoutError should be mapped to HTTP 503."""
        with app.test_request_context():
            @handle_errors
            def raise_timeout_error():
                raise TimeoutError("Connection timed out")

            response, status_code = raise_timeout_error()
            assert status_code == 503
            data = response.get_json()
            assert 'error' in data

    def test_connection_error_returns_503(self, app):
        """ConnectionError should be mapped to HTTP 503."""
        with app.test_request_context():
            @handle_errors
            def raise_connection_error():
                raise ConnectionError("Connection refused")

            response, status_code = raise_connection_error()
            assert status_code == 503

    def test_generic_exception_returns_500(self, app):
        """Generic Exception should be mapped to HTTP 500."""
        with app.test_request_context():
            @handle_errors
            def raise_generic_error():
                raise RuntimeError("Something went wrong")

            response, status_code = raise_generic_error()
            assert status_code == 500
            data = response.get_json()
            assert 'error' in data

    def test_no_exception_passes_through(self, app):
        """When no exception is raised, the function result passes through."""
        from flask import jsonify as flask_jsonify
        with app.test_request_context():
            @handle_errors
            def no_error():
                return flask_jsonify({"result": "ok"}), 200

            response, status_code = no_error()
            assert status_code == 200

    def test_value_error_via_chat_route(self, client, mock_user_manager, mock_agent, mock_history_service, mock_conversation_stats):
        """ValueError raised in agent.chat should return 400 via handle_errors."""
        # Login first
        client.post('/pdn-relationships/login', json={
            'email': 'test@example.com',
            'password': 'testpass',
            'partner_code': 'e5',
            'relationship_type': 'partner',
        })

        # Make agent.chat raise ValueError
        mock_agent.chat.side_effect = ValueError("Invalid parameter")

        response = client.post('/pdn-relationships/chat', json={
            'message': 'Hello',
            'user_name': 'Test User',
            'pdn_code': 'a3',
            'partner_code': 'e5',
            'relationship_type': 'partner',
        })
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_timeout_error_via_chat_route(self, client, mock_user_manager, mock_agent, mock_history_service, mock_conversation_stats):
        """TimeoutError raised in agent.chat should return 503 via handle_errors."""
        # Login first
        client.post('/pdn-relationships/login', json={
            'email': 'test@example.com',
            'password': 'testpass',
            'partner_code': 'e5',
            'relationship_type': 'partner',
        })

        # Make agent.chat raise TimeoutError
        mock_agent.chat.side_effect = TimeoutError("LLM timeout")

        response = client.post('/pdn-relationships/chat', json={
            'message': 'Hello',
            'user_name': 'Test User',
            'pdn_code': 'a3',
            'partner_code': 'e5',
            'relationship_type': 'partner',
        })
        assert response.status_code == 503

    def test_generic_exception_via_chat_route(self, client, mock_user_manager, mock_agent, mock_history_service, mock_conversation_stats):
        """Generic exception raised in agent.chat should return 500 via handle_errors."""
        # Login first
        client.post('/pdn-relationships/login', json={
            'email': 'test@example.com',
            'password': 'testpass',
            'partner_code': 'e5',
            'relationship_type': 'partner',
        })

        # Make agent.chat raise a generic exception
        mock_agent.chat.side_effect = RuntimeError("Unexpected error")

        response = client.post('/pdn-relationships/chat', json={
            'message': 'Hello',
            'user_name': 'Test User',
            'pdn_code': 'a3',
            'partner_code': 'e5',
            'relationship_type': 'partner',
        })
        assert response.status_code == 500


class TestConstants:
    """Tests for constants.py — RelationshipType enum and PDN_CODES list.

    Validates: Requirements 11.1, 11.2, 11.3
    """

    def test_relationship_type_enum_contains_exactly_three_values(self):
        """RelationshipType enum should contain exactly partner, friend, colleague."""
        values = {member.value for member in RelationshipType}
        assert values == {"partner", "friend", "colleague"}

    def test_relationship_type_enum_member_count(self):
        """RelationshipType enum should have exactly 3 members."""
        assert len(RelationshipType) == 3

    def test_relationship_type_partner(self):
        """RelationshipType.PARTNER should have value 'partner'."""
        assert RelationshipType.PARTNER.value == "partner"

    def test_relationship_type_friend(self):
        """RelationshipType.FRIEND should have value 'friend'."""
        assert RelationshipType.FRIEND.value == "friend"

    def test_relationship_type_colleague(self):
        """RelationshipType.COLLEAGUE should have value 'colleague'."""
        assert RelationshipType.COLLEAGUE.value == "colleague"

    def test_pdn_codes_contains_exactly_12_codes(self):
        """PDN_CODES should contain exactly 12 codes."""
        assert len(PDN_CODES) == 12

    def test_pdn_codes_exact_values(self):
        """PDN_CODES should contain the expected 12 codes."""
        expected = ["a3", "a7", "a11", "e1", "e5", "e9", "p2", "p6", "p10", "t4", "t8", "t12"]
        assert PDN_CODES == expected

    def test_pdn_codes_match_expected_pattern(self):
        """Each PDN code should match the pattern: single letter prefix followed by digits."""
        import re
        pattern = re.compile(r'^[a-z]\d+$')
        for code in PDN_CODES:
            assert pattern.match(code), f"Code '{code}' does not match expected pattern"

    def test_pdn_codes_prefixes(self):
        """PDN_CODES should use exactly the prefixes a, e, p, t (3 codes each)."""
        prefixes = [code[0] for code in PDN_CODES]
        assert prefixes.count('a') == 3
        assert prefixes.count('e') == 3
        assert prefixes.count('p') == 3
        assert prefixes.count('t') == 3
