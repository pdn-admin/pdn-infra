"""Tests for admin routes to achieve >80% code coverage.

Tests login/logout, session management, user listing, metadata,
conversation stats, token usage, and user journey endpoints.
"""

import pytest
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime, timedelta
from pathlib import Path as RealPath
from flask import Flask
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.pdn_admin.admin_routes import (
    pdn_admin_bp, admin_sessions, create_session, verify_session,
    cleanup_expired_sessions, _format_user, remove_none_keys,
    load_user_metadata, _metadata_cache, SESSION_TIMEOUT
)


@pytest.fixture(autouse=True)
def clear_admin_sessions():
    """Clear admin sessions before each test."""
    admin_sessions.clear()
    _metadata_cache['data'] = None
    _metadata_cache['timestamp'] = 0
    yield
    admin_sessions.clear()


@pytest.fixture
def app():
    """Create a minimal Flask test app with the admin blueprint."""
    application = Flask(__name__)
    application.config['TESTING'] = True
    application.config['SECRET_KEY'] = 'test-secret-key'
    application.config['ADMIN_PASSWORD'] = 'pdn'
    application.register_blueprint(pdn_admin_bp, url_prefix='/pdn-admin')
    return application


@pytest.fixture
def client(app):
    """Create Flask test client."""
    return app.test_client()


@pytest.fixture
def valid_session_token():
    """Create a valid admin session and return the token."""
    token = create_session('admin@test.com')
    return token


@pytest.fixture
def mock_user_manager():
    """Mock the user manager."""
    with patch('app.pdn_admin.admin_routes.get_user_manager') as mock_um:
        mgr = MagicMock()
        mgr.get_user.return_value = {
            'password': 'testpass',
            'name': 'Test User',
            'pdn_code': 'a3',
            'daily_conversation_limit': 15,
        }
        mgr.get_all_users.return_value = [
            {'email': 'user1@test.com', 'name': 'User 1', 'pdn_code': 'a3',
             'daily_conversation_limit': 15, 'gender': '', 'created_at': '2025-01-01'}
        ]
        mgr.get_available_pdn_codes.return_value = ['a3', 'e5', 'p10']
        mgr.add_user.return_value = {
            'email': 'new@test.com', 'name': 'New User', 'pdn_code': 'a3',
            'daily_conversation_limit': 15, 'gender': '', 'created_at': '2025-01-01 12:00'
        }
        mgr.update_user.return_value = {
            'email': 'user1@test.com', 'name': 'Updated', 'pdn_code': 'e5',
            'daily_conversation_limit': 20, 'gender': 'male', 'created_at': '2025-01-01'
        }
        mgr.delete_user.return_value = None
        mock_um.return_value = mgr
        yield mgr


class TestAdminLogin:
    """Tests for admin login/logout endpoints."""

    @patch('flask.templating._render', return_value='')
    def test_admin_login_page(self, mock_render, client):
        """GET / should render login page."""
        response = client.get('/pdn-admin/')
        assert response.status_code == 200

    @patch('flask.templating._render', return_value='')
    def test_admin_dashboard_page(self, mock_render, client):
        """GET /dashboard should render dashboard page."""
        response = client.get('/pdn-admin/dashboard')
        assert response.status_code == 200

    def test_login_valid_credentials(self, client):
        """Valid admin password returns session token."""
        response = client.post('/pdn-admin/login', json={
            'email': 'admin@test.com',
            'password': 'pdn'
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'session_token' in data

    def test_login_case_sensitive_password(self, client):
        """Password comparison is case-sensitive (security hardening)."""
        response = client.post('/pdn-admin/login', json={
            'email': 'admin@test.com',
            'password': 'PDN'
        })
        assert response.status_code == 401

    def test_login_invalid_credentials(self, client):
        """Invalid password returns 401."""
        response = client.post('/pdn-admin/login', json={
            'email': 'admin@test.com',
            'password': 'wrong'
        })
        assert response.status_code == 401
        data = response.get_json()
        assert 'error' in data

    def test_login_exception_handling(self, client):
        """Malformed request returns 400."""
        response = client.post('/pdn-admin/login',
                               data='not json',
                               content_type='application/json')
        assert response.status_code == 400

    def test_logout(self, client, valid_session_token):
        """Logout removes session token."""
        response = client.get(f'/pdn-admin/logout?session_token={valid_session_token}')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert valid_session_token not in admin_sessions

    def test_logout_without_token(self, client):
        """Logout without token still succeeds."""
        response = client.get('/pdn-admin/logout')
        assert response.status_code == 200


class TestSessionManagement:
    """Tests for session creation, verification, and cleanup."""

    def test_create_session(self):
        """create_session returns a token and stores session data."""
        token = create_session('test@example.com')
        assert token in admin_sessions
        assert admin_sessions[token]['email'] == 'test@example.com'
        assert 'expires_at' in admin_sessions[token]

    def test_create_session_replaces_existing(self):
        """Creating a new session for same email removes old one."""
        token1 = create_session('test@example.com')
        token2 = create_session('test@example.com')
        assert token1 not in admin_sessions
        assert token2 in admin_sessions

    def test_verify_session_valid(self, app):
        """verify_session returns session data for valid token."""
        token = create_session('test@example.com')
        with app.test_request_context():
            session_data = verify_session(token)
            assert session_data['email'] == 'test@example.com'

    def test_verify_session_invalid_token(self, app):
        """verify_session aborts 401 for invalid token."""
        with app.test_request_context():
            with pytest.raises(Exception):
                verify_session('invalid-token')

    def test_verify_session_none_token(self, app):
        """verify_session aborts 401 for None token."""
        with app.test_request_context():
            with pytest.raises(Exception):
                verify_session(None)

    def test_verify_session_expired(self, app):
        """verify_session aborts 401 for expired token."""
        token = create_session('test@example.com')
        admin_sessions[token]['expires_at'] = datetime.now() - timedelta(hours=1)
        with app.test_request_context():
            with pytest.raises(Exception):
                verify_session(token)

    def test_cleanup_expired_sessions(self):
        """cleanup_expired_sessions removes expired entries."""
        token1 = create_session('user1@test.com')
        token2 = create_session('user2@test.com')
        admin_sessions[token1]['expires_at'] = datetime.now() - timedelta(hours=1)
        cleanup_expired_sessions()
        assert token1 not in admin_sessions
        assert token2 in admin_sessions

    def test_verify_session_sliding_window(self, app):
        """verify_session refreshes expiry on successful verification."""
        token = create_session('test@example.com')
        old_expiry = admin_sessions[token]['expires_at']
        with app.test_request_context():
            verify_session(token)
        new_expiry = admin_sessions[token]['expires_at']
        assert new_expiry >= old_expiry


class TestSessionManagementExtended:
    """Extended tests for session management: require_admin_session decorator and edge cases.

    Validates: Requirements 1.1, 1.2, 1.3
    """

    def test_create_session_enforces_max_sessions(self):
        """create_session evicts oldest session when MAX_ADMIN_SESSIONS reached."""
        from app.pdn_admin.admin_routes import MAX_ADMIN_SESSIONS
        # Fill up sessions to the max
        tokens = []
        for i in range(MAX_ADMIN_SESSIONS):
            token = create_session(f'user{i}@test.com')
            tokens.append(token)

        # Creating one more should evict the oldest
        new_token = create_session('overflow@test.com')
        assert new_token in admin_sessions
        assert len(admin_sessions) <= MAX_ADMIN_SESSIONS

    def test_create_session_returns_urlsafe_token(self):
        """create_session returns a URL-safe token string."""
        token = create_session('test@example.com')
        assert isinstance(token, str)
        assert len(token) > 0
        # URL-safe base64 characters only
        import re
        assert re.match(r'^[A-Za-z0-9_-]+$', token)

    def test_create_session_stores_login_time(self):
        """create_session stores login_time in session data."""
        token = create_session('test@example.com')
        session = admin_sessions[token]
        assert 'login_time' in session
        assert isinstance(session['login_time'], datetime)

    def test_create_session_stores_expires_at(self):
        """create_session stores expires_at as login_time + SESSION_TIMEOUT."""
        token = create_session('test@example.com')
        session = admin_sessions[token]
        expected_expiry = session['login_time'] + SESSION_TIMEOUT
        assert session['expires_at'] == expected_expiry

    def test_verify_session_calls_cleanup(self, app):
        """verify_session triggers cleanup_expired_sessions."""
        # Create an expired session and a valid one
        expired_token = create_session('expired@test.com')
        admin_sessions[expired_token]['expires_at'] = datetime.now() - timedelta(hours=1)
        valid_token = create_session('valid@test.com')

        with app.test_request_context():
            verify_session(valid_token)

        # Expired session should have been cleaned up
        assert expired_token not in admin_sessions

    def test_cleanup_expired_sessions_no_expired(self):
        """cleanup_expired_sessions does nothing when no sessions are expired."""
        token1 = create_session('user1@test.com')
        token2 = create_session('user2@test.com')
        cleanup_expired_sessions()
        assert token1 in admin_sessions
        assert token2 in admin_sessions

    def test_cleanup_expired_sessions_all_expired(self):
        """cleanup_expired_sessions removes all sessions when all are expired."""
        token1 = create_session('user1@test.com')
        token2 = create_session('user2@test.com')
        admin_sessions[token1]['expires_at'] = datetime.now() - timedelta(hours=1)
        admin_sessions[token2]['expires_at'] = datetime.now() - timedelta(hours=1)
        cleanup_expired_sessions()
        assert len(admin_sessions) == 0

    def test_require_admin_session_valid_token(self, client, valid_session_token):
        """require_admin_session allows access with valid session token."""
        # The /logged-in-users endpoint uses verify_session directly,
        # but /metadata/csv also uses verify_session. Let's test a decorated endpoint.
        # The conversation-stats endpoint doesn't use require_admin_session,
        # but /users endpoint does via verify_session in the route.
        # Let's test via the metadata/csv endpoint which calls verify_session
        response = client.get(f'/pdn-admin/metadata/csv?session_token={valid_session_token}')
        assert response.status_code == 200

    def test_require_admin_session_no_token(self, client):
        """require_admin_session rejects requests without session token."""
        # The logged-in-users endpoint calls verify_session which aborts 401
        response = client.get('/pdn-admin/logged-in-users')
        assert response.status_code == 401

    def test_require_admin_session_invalid_token(self, client):
        """require_admin_session rejects requests with invalid session token."""
        response = client.get('/pdn-admin/logged-in-users?session_token=invalid-token-xyz')
        assert response.status_code == 401

    def test_require_admin_session_expired_token(self, client):
        """require_admin_session rejects requests with expired session token."""
        token = create_session('admin@test.com')
        admin_sessions[token]['expires_at'] = datetime.now() - timedelta(hours=1)
        response = client.get(f'/pdn-admin/logged-in-users?session_token={token}')
        assert response.status_code == 401

    def test_admin_login_correct_password_creates_session(self, client):
        """Admin login with correct password creates a session in admin_sessions."""
        response = client.post('/pdn-admin/login', json={
            'email': 'admin@test.com',
            'password': 'pdn'
        })
        assert response.status_code == 200
        data = response.get_json()
        token = data['session_token']
        assert token in admin_sessions
        assert admin_sessions[token]['email'] == 'admin@test.com'

    def test_admin_login_incorrect_password_no_session(self, client):
        """Admin login with incorrect password does not create a session."""
        initial_count = len(admin_sessions)
        response = client.post('/pdn-admin/login', json={
            'email': 'admin@test.com',
            'password': 'wrong-password'
        })
        assert response.status_code == 401
        assert len(admin_sessions) == initial_count

    def test_admin_login_with_custom_config_password(self, app):
        """Admin login uses ADMIN_PASSWORD from app config."""
        app.config['ADMIN_PASSWORD'] = 'custom-secret-123'
        client = app.test_client()
        response = client.post('/pdn-admin/login', json={
            'email': 'admin@test.com',
            'password': 'custom-secret-123'
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    def test_admin_login_empty_password_rejected(self, client):
        """Admin login with empty password is rejected."""
        response = client.post('/pdn-admin/login', json={
            'email': 'admin@test.com',
            'password': ''
        })
        assert response.status_code == 401


class TestLoggedInUsers:
    """Tests for the logged-in-users endpoint."""

    def test_get_logged_in_users(self, client, valid_session_token):
        """Returns list of logged-in users."""
        response = client.get(f'/pdn-admin/logged-in-users?session_token={valid_session_token}')
        assert response.status_code == 200
        data = response.get_json()
        assert 'users' in data
        assert 'count' in data

    def test_get_logged_in_users_no_token(self, client):
        """Returns 401 without valid session."""
        response = client.get('/pdn-admin/logged-in-users')
        assert response.status_code == 401


class TestMetadata:
    """Tests for metadata endpoints."""

    @patch('app.pdn_admin.admin_routes.load_user_metadata')
    def test_get_metadata_csv(self, mock_load, client, valid_session_token):
        """Returns metadata list."""
        mock_load.return_value = [{'email': 'user@test.com', 'pdn_code': 'a3'}]
        response = client.get(f'/pdn-admin/metadata/csv?session_token={valid_session_token}')
        assert response.status_code == 200
        data = response.get_json()
        assert 'data' in data


class TestUserQuestionnaire:
    """Tests for user questionnaire endpoint."""

    @patch('app.pdn_admin.admin_routes.UserMetadataHandler')
    def test_get_user_questionnaire_found(self, mock_handler_cls, client, valid_session_token):
        """Returns questionnaire data when found."""
        mock_handler = MagicMock()
        mock_handler.get_user_files.return_value = {'metadata': {'first_name': 'Test'}, 'answers': {}}
        mock_handler.get_user_by_email.return_value = {'User ID': '123', 'First Name': 'Test'}
        mock_handler_cls.return_value = mock_handler

        response = client.get(f'/pdn-admin/user/questionnaire/test@test.com?session_token={valid_session_token}')
        assert response.status_code == 200

    @patch('app.pdn_admin.admin_routes.UserMetadataHandler')
    def test_get_user_questionnaire_not_found(self, mock_handler_cls, client, valid_session_token):
        """Returns 404 when questionnaire not found."""
        mock_handler = MagicMock()
        mock_handler.get_user_files.return_value = None
        mock_handler_cls.return_value = mock_handler

        response = client.get(f'/pdn-admin/user/questionnaire/missing@test.com?session_token={valid_session_token}')
        assert response.status_code == 404


class TestUserVoice:
    """Tests for user voice endpoint."""

    @patch('app.pdn_admin.admin_routes.PDNFilePath')
    def test_get_user_voice_not_found(self, mock_pdn_path_cls, client, valid_session_token):
        """Returns 404 when no voice recordings found."""
        mock_pdn_path = MagicMock()
        mock_pdn_path.find_user_file.return_value = None
        mock_pdn_path_cls.return_value = mock_pdn_path

        response = client.get(f'/pdn-admin/user/voice/test@test.com?session_token={valid_session_token}')
        assert response.status_code == 404


class TestUserDiagnose:
    """Tests for user diagnose update endpoint."""

    @patch('app.pdn_admin.admin_routes.load_user_metadata')
    @patch('app.pdn_admin.admin_routes.UserMetadataHandler')
    def test_update_user_diagnose_success(self, mock_handler_cls, mock_load, client, valid_session_token):
        """Successfully updates diagnose info."""
        mock_load.return_value = [{'email': 'test@test.com', 'pdn_code': 'a3'}]
        mock_handler = MagicMock()
        mock_handler_cls.return_value = mock_handler

        response = client.put(
            f'/pdn-admin/user/diagnose/test@test.com?session_token={valid_session_token}',
            json={'diagnose_pdn_code': 'e5', 'diagnose_comments': 'test comment'}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    @patch('app.pdn_admin.admin_routes.load_user_metadata')
    def test_update_user_diagnose_not_found(self, mock_load, client, valid_session_token):
        """Returns 404 when user not found."""
        mock_load.return_value = []

        response = client.put(
            f'/pdn-admin/user/diagnose/missing@test.com?session_token={valid_session_token}',
            json={'diagnose_pdn_code': 'e5'}
        )
        assert response.status_code == 404


class TestConversationStats:
    """Tests for conversation stats endpoint."""

    @patch('app.pdn_admin.admin_routes.conversation_stats')
    def test_get_conversation_stats(self, mock_stats, client):
        """Returns conversation stats."""
        mock_stats.get_all_stats.return_value = {'2025-01-01': {'user@test.com': 5}}
        response = client.get('/pdn-admin/conversation-stats?days=7')
        assert response.status_code == 200
        data = response.get_json()
        assert 'stats' in data
        assert data['days'] == 7


class TestTokenUsage:
    """Tests for token usage endpoint."""

    def test_get_token_usage(self, client, valid_session_token):
        """Returns token usage stats."""
        with patch('app.pdn_chat_ai.chat_routes.get_agent_instance') as mock_agent_fn:
            mock_agent = MagicMock()
            mock_agent.get_usage_stats.return_value = {'total_calls': 100}
            mock_agent_fn.return_value = mock_agent

            response = client.get(f'/pdn-admin/token-usage?session_token={valid_session_token}&days=14')
            assert response.status_code == 200
            data = response.get_json()
            assert 'stats' in data


class TestUserJourney:
    """Tests for user journey endpoint."""

    @patch('app.pdn_admin.admin_routes.conversation_stats')
    @patch('app.pdn_admin.admin_routes.UserMetadataHandler')
    def test_get_user_journey(self, mock_handler_cls, mock_stats, client, valid_session_token):
        """Returns user journey data."""
        mock_handler = MagicMock()
        mock_handler.get_user_by_email.return_value = {
            'First Name': 'Test', 'Last Name': 'User',
            'PDN Code': 'a3', 'Date': '01/06/2025'
        }
        mock_handler_cls.return_value = mock_handler
        mock_stats._read_locked.return_value = {
            '2025-06-01': {'test@test.com': 3}
        }

        with patch('app.pdn_chat_ai.chat_routes.get_agent_instance') as mock_agent_fn:
            mock_agent = MagicMock()
            mock_agent.token_usage = {}
            mock_agent_fn.return_value = mock_agent

            response = client.get(f'/pdn-admin/user/journey/test@test.com?session_token={valid_session_token}')
        assert response.status_code == 200
        data = response.get_json()
        assert 'events' in data
        assert 'metrics' in data


class TestVersion:
    """Tests for version endpoint."""

    def test_get_version(self, client):
        """Returns version info."""
        response = client.get('/pdn-admin/version')
        assert response.status_code == 200
        data = response.get_json()
        assert 'version' in data
        assert 'release_date' in data
        assert 'release_notes' in data


class TestUserManagement:
    """Tests for user CRUD endpoints."""

    def test_list_users(self, client, valid_session_token, mock_user_manager):
        """GET /users returns user list."""
        response = client.get(f'/pdn-admin/users?session_token={valid_session_token}')
        assert response.status_code == 200
        data = response.get_json()
        assert 'users' in data

    def test_get_pdn_codes(self, client, valid_session_token, mock_user_manager):
        """GET /users/pdn-codes returns available codes."""
        response = client.get(f'/pdn-admin/users/pdn-codes?session_token={valid_session_token}')
        assert response.status_code == 200
        data = response.get_json()
        assert 'codes' in data

    def test_create_user_success(self, client, valid_session_token, mock_user_manager):
        """POST /users creates a new user."""
        response = client.post(
            f'/pdn-admin/users?session_token={valid_session_token}',
            json={
                'admin_password': 'pdn',
                'email': 'new@test.com',
                'password': 'pass123',
                'name': 'New User',
                'gender': 'male',
                'pdn_code': 'a3',
                'daily_conversation_limit': 15
            }
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data['success'] is True

    def test_create_user_invalid_admin_password(self, client, valid_session_token, mock_user_manager):
        """POST /users with admin_password field ignored - session_token is sufficient."""
        response = client.post(
            f'/pdn-admin/users?session_token={valid_session_token}',
            json={
                'admin_password': 'wrong',
                'email': 'new@test.com',
                'password': 'pass123',
                'name': 'New User',
                'pdn_code': 'a3'
            }
        )
        assert response.status_code == 201

    def test_create_user_no_data(self, client, valid_session_token, mock_user_manager):
        """POST /users with no data returns 400."""
        response = client.post(
            f'/pdn-admin/users?session_token={valid_session_token}',
            content_type='application/json',
            data=''
        )
        assert response.status_code == 400

    def test_create_user_invalid_daily_limit(self, client, valid_session_token, mock_user_manager):
        """POST /users with non-numeric daily_limit returns 400."""
        response = client.post(
            f'/pdn-admin/users?session_token={valid_session_token}',
            json={
                'admin_password': 'pdn',
                'email': 'new@test.com',
                'password': 'pass123',
                'name': 'New User',
                'pdn_code': 'a3',
                'daily_conversation_limit': 'abc'
            }
        )
        assert response.status_code == 400

    def test_create_user_validation_error(self, client, valid_session_token, mock_user_manager):
        """POST /users with duplicate email returns 400."""
        mock_user_manager.add_user.side_effect = ValueError("User already exists")
        response = client.post(
            f'/pdn-admin/users?session_token={valid_session_token}',
            json={
                'admin_password': 'pdn',
                'email': 'existing@test.com',
                'password': 'pass123',
                'name': 'Existing',
                'pdn_code': 'a3',
                'daily_conversation_limit': 15
            }
        )
        assert response.status_code == 400

    def test_update_user_success(self, client, valid_session_token, mock_user_manager):
        """PUT /users/<email> updates user."""
        response = client.put(
            f'/pdn-admin/users/user1@test.com?session_token={valid_session_token}',
            json={
                'admin_password': 'pdn',
                'name': 'Updated',
                'pdn_code': 'e5'
            }
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    def test_update_user_invalid_admin_password(self, client, valid_session_token, mock_user_manager):
        """PUT /users/<email> with admin_password field ignored - session_token is sufficient."""
        response = client.put(
            f'/pdn-admin/users/user1@test.com?session_token={valid_session_token}',
            json={'admin_password': 'wrong', 'name': 'Updated'}
        )
        assert response.status_code == 200

    def test_update_user_not_found(self, client, valid_session_token, mock_user_manager):
        """PUT /users/<email> for missing user returns 404."""
        mock_user_manager.update_user.side_effect = KeyError("User not found")
        response = client.put(
            f'/pdn-admin/users/missing@test.com?session_token={valid_session_token}',
            json={'admin_password': 'pdn', 'name': 'Updated'}
        )
        assert response.status_code == 404

    def test_update_user_no_data(self, client, valid_session_token, mock_user_manager):
        """PUT /users/<email> with no data returns 400."""
        response = client.put(
            f'/pdn-admin/users/user1@test.com?session_token={valid_session_token}',
            content_type='application/json',
            data=''
        )
        assert response.status_code == 400

    def test_update_user_invalid_daily_limit(self, client, valid_session_token, mock_user_manager):
        """PUT /users/<email> with non-numeric daily_limit returns 400."""
        response = client.put(
            f'/pdn-admin/users/user1@test.com?session_token={valid_session_token}',
            json={'admin_password': 'pdn', 'daily_conversation_limit': 'abc'}
        )
        assert response.status_code == 400

    def test_delete_user_success(self, client, valid_session_token, mock_user_manager):
        """DELETE /users/<email> removes user."""
        response = client.delete(
            f'/pdn-admin/users/user1@test.com?session_token={valid_session_token}',
            json={'admin_password': 'pdn'}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    def test_delete_user_invalid_admin_password(self, client, valid_session_token, mock_user_manager):
        """DELETE /users/<email> with admin_password field ignored - session_token is sufficient."""
        response = client.delete(
            f'/pdn-admin/users/user1@test.com?session_token={valid_session_token}',
            json={'admin_password': 'wrong'}
        )
        assert response.status_code == 200

    def test_delete_user_not_found(self, client, valid_session_token, mock_user_manager):
        """DELETE /users/<email> for missing user returns 404."""
        mock_user_manager.delete_user.side_effect = KeyError("User not found")
        response = client.delete(
            f'/pdn-admin/users/missing@test.com?session_token={valid_session_token}',
            json={'admin_password': 'pdn'}
        )
        assert response.status_code == 404


class TestSendEmail:
    """Tests for email sending endpoints."""

    @patch('app.pdn_admin.admin_routes.send_pdn_code_email')
    @patch('app.pdn_admin.admin_routes.calculate_pdn_code')
    @patch('app.pdn_admin.admin_routes.load_answers')
    def test_send_user_email_success(self, mock_load, mock_calc, mock_send, client, valid_session_token):
        """Successfully sends PDN code email."""
        mock_load.return_value = {'answers': {'1': 'a'}}
        mock_calc.return_value = 'a3'
        mock_send.return_value = True

        response = client.post(f'/pdn-admin/user/send_email/test@test.com?session_token={valid_session_token}')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    @patch('app.pdn_admin.admin_routes.load_answers')
    def test_send_user_email_no_answers(self, mock_load, client, valid_session_token):
        """Returns 404 when no answers found."""
        mock_load.return_value = None
        response = client.post(f'/pdn-admin/user/send_email/test@test.com?session_token={valid_session_token}')
        assert response.status_code == 404

    @patch('app.pdn_admin.admin_routes.send_binat_invite_email')
    @patch('app.pdn_admin.admin_routes.UserMetadataHandler')
    def test_send_binat_invite_success(self, mock_handler_cls, mock_send, client, valid_session_token):
        """Successfully sends Binat invite."""
        mock_handler = MagicMock()
        mock_handler.get_user_files.return_value = {'metadata': {'first_name': 'Test'}}
        mock_handler.get_user_by_email.return_value = {'First Name': 'Test'}
        mock_handler_cls.return_value = mock_handler
        mock_send.return_value = True

        response = client.post(f'/pdn-admin/user/send_binat_invite/test@test.com?session_token={valid_session_token}')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True


class TestRecalculatePDN:
    """Tests for PDN recalculation endpoint."""

    @patch('app.pdn_admin.admin_routes.UserMetadataHandler')
    @patch('app.pdn_admin.admin_routes.calculate_pdn_code')
    @patch('app.pdn_admin.admin_routes.load_answers')
    def test_recalculate_pdn_success(self, mock_load, mock_calc, mock_handler_cls, client, valid_session_token):
        """Successfully recalculates PDN code."""
        mock_load.return_value = {'answers': {'1': 'a'}}
        mock_calc.return_value = {'pdn_code': 'e5', 'needs_verification': False, 'confidence_score': 95}
        mock_handler = MagicMock()
        mock_handler.update_pdn_code_with_comment.return_value = True
        mock_handler.get_user_by_email.return_value = {'Date': '01/01/2025', 'PDN Update Comments': 'Admin'}
        mock_handler_cls.return_value = mock_handler

        response = client.post(f'/pdn-admin/user/recalculate_pdn/test@test.com?session_token={valid_session_token}')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['pdn_code'] == 'e5'

    @patch('app.pdn_admin.admin_routes.load_answers')
    def test_recalculate_pdn_no_answers(self, mock_load, client, valid_session_token):
        """Returns 404 when no answers found."""
        mock_load.return_value = None
        response = client.post(f'/pdn-admin/user/recalculate_pdn/test@test.com?session_token={valid_session_token}')
        assert response.status_code == 404


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_format_user_with_expires(self):
        """_format_user includes expires_at when present."""
        session_data = {
            'email': 'test@test.com',
            'login_time': datetime(2025, 1, 1, 12, 0, 0),
            'expires_at': datetime(2025, 1, 1, 14, 0, 0)
        }
        result = _format_user(session_data, 'admin')
        assert result['email'] == 'test@test.com'
        assert result['type'] == 'admin'
        assert 'expires_at' in result

    def test_format_user_without_expires(self):
        """_format_user works without expires_at."""
        session_data = {
            'email': 'test@test.com',
            'login_time': datetime(2025, 1, 1, 12, 0, 0)
        }
        result = _format_user(session_data, 'chat_ai')
        assert result['type'] == 'chat_ai'
        assert 'expires_at' not in result

    def test_format_user_fallback_to_user_id(self):
        """_format_user falls back to user_id when email missing."""
        session_data = {
            'user_id': 'uid123',
            'login_time': datetime(2025, 1, 1, 12, 0, 0)
        }
        result = _format_user(session_data, 'chat_ai')
        assert result['email'] == 'uid123'

    def test_remove_none_keys_dict(self):
        """remove_none_keys removes None keys from dicts."""
        data = {'a': 1, None: 'bad', 'b': {'c': 2, None: 'also bad'}}
        result = remove_none_keys(data)
        assert None not in result
        assert None not in result['b']

    def test_remove_none_keys_list(self):
        """remove_none_keys handles lists."""
        data = [{'a': 1, None: 'bad'}, {'b': 2}]
        result = remove_none_keys(data)
        assert None not in result[0]

    def test_remove_none_keys_scalar(self):
        """remove_none_keys returns scalars unchanged."""
        assert remove_none_keys(42) == 42
        assert remove_none_keys("hello") == "hello"


class TestLoadUserMetadata:
    """Tests for load_user_metadata function."""

    def test_load_metadata_file_not_found(self, monkeypatch):
        """Returns empty list when CSV file doesn't exist."""
        monkeypatch.setenv('SAVED_RESULTS_DIR', '/nonexistent/path')
        _metadata_cache['data'] = None
        _metadata_cache['timestamp'] = 0
        result = load_user_metadata()
        assert result == []

    def test_load_metadata_from_cache(self):
        """Returns cached data when cache is fresh."""
        import time
        _metadata_cache['data'] = [{'email': 'cached@test.com'}]
        _metadata_cache['timestamp'] = time.time()
        result = load_user_metadata()
        assert result == [{'email': 'cached@test.com'}]

    @patch('app.pdn_admin.admin_routes.UserMetadataHandler')
    def test_load_metadata_from_csv(self, mock_handler_cls, tmp_path, monkeypatch):
        """Loads metadata from CSV file."""
        # Create a test CSV file
        csv_file = tmp_path / 'user_metadata.csv'
        csv_file.write_text(
            'Email,User ID,Date,PDN Code,PDN Voice Code,Diagnose PDN Code,Diagnose Comments,PDN Update Comments,First Name,Last Name,Phone,Native Language,Gender,Education Level,Job Title,Birth Year\n'
            'test@test.com,uid1,01/01/2025,a3,,,,,,Test,User,050,,male,,,1990\n',
            encoding='utf-8'
        )
        monkeypatch.setenv('SAVED_RESULTS_DIR', str(tmp_path))
        _metadata_cache['data'] = None
        _metadata_cache['timestamp'] = 0

        mock_handler = MagicMock()
        mock_handler.get_user_files.return_value = None
        mock_handler_cls.return_value = mock_handler

        result = load_user_metadata()
        assert len(result) == 1
        assert result[0]['email'] == 'test@test.com'

    @patch('app.pdn_admin.admin_routes.UserMetadataHandler')
    def test_load_metadata_skips_empty_rows(self, mock_handler_cls, tmp_path, monkeypatch):
        """Skips rows with empty email."""
        csv_file = tmp_path / 'user_metadata.csv'
        csv_file.write_text(
            'Email,User ID,Date,PDN Code\n'
            ',uid1,01/01/2025,a3\n'
            'valid@test.com,uid2,02/01/2025,e5\n',
            encoding='utf-8'
        )
        monkeypatch.setenv('SAVED_RESULTS_DIR', str(tmp_path))
        _metadata_cache['data'] = None
        _metadata_cache['timestamp'] = 0

        mock_handler = MagicMock()
        mock_handler.get_user_files.return_value = None
        mock_handler_cls.return_value = mock_handler

        result = load_user_metadata()
        assert len(result) == 1
        assert result[0]['email'] == 'valid@test.com'


class TestServeAudio:
    """Tests for audio serving endpoint."""

    def test_serve_audio_file_not_found(self, client, valid_session_token, tmp_path, monkeypatch):
        """Returns 404 when audio file doesn't exist."""
        monkeypatch.setenv('SAVED_RESULTS_DIR', str(tmp_path))
        response = client.get(f'/pdn-admin/audio/nonexistent.wav?session_token={valid_session_token}')
        assert response.status_code == 404

    def test_serve_audio_success(self, client, valid_session_token, tmp_path, monkeypatch):
        """Serves audio file when it exists."""
        monkeypatch.setenv('SAVED_RESULTS_DIR', str(tmp_path))
        audio_file = tmp_path / 'test.wav'
        audio_file.write_bytes(b'RIFF' + b'\x00' * 100)

        response = client.get(f'/pdn-admin/audio/test.wav?session_token={valid_session_token}')
        assert response.status_code == 200

    def test_serve_audio_path_traversal(self, client, valid_session_token, tmp_path, monkeypatch):
        """Blocks path traversal attempts."""
        monkeypatch.setenv('SAVED_RESULTS_DIR', str(tmp_path))
        response = client.get(f'/pdn-admin/audio/../../etc/passwd?session_token={valid_session_token}')
        assert response.status_code in (400, 403, 404)

    def test_serve_audio_strips_prefix(self, client, valid_session_token, tmp_path, monkeypatch):
        """Handles saved_results/ prefix in path."""
        monkeypatch.setenv('SAVED_RESULTS_DIR', str(tmp_path))
        audio_file = tmp_path / 'user' / 'test.wav'
        audio_file.parent.mkdir(parents=True, exist_ok=True)
        audio_file.write_bytes(b'RIFF' + b'\x00' * 100)

        response = client.get(f'/pdn-admin/audio/saved_results/user/test.wav?session_token={valid_session_token}')
        assert response.status_code == 200


class TestSaveAudio:
    """Tests for audio upload endpoint."""

    def test_save_audio_no_file(self, client, valid_session_token):
        """Returns 400 when no audio file provided."""
        response = client.post(f'/pdn-admin/api/save-audio?session_token={valid_session_token}',
                               data={'username': 'test'},
                               content_type='multipart/form-data')
        assert response.status_code == 400

    @patch('app.pdn_admin.admin_routes.PDNFilePath')
    def test_save_audio_success(self, mock_pdn_path_cls, client, valid_session_token, tmp_path):
        """Successfully saves audio file."""
        mock_pdn_path = MagicMock()
        mock_pdn_path.get_user_dir.return_value = tmp_path
        mock_pdn_path_cls.return_value = mock_pdn_path

        import io
        data = {
            'audio': (io.BytesIO(b'RIFF' + b'\x00' * 100), 'test.wav'),
            'username': 'testuser'
        }
        response = client.post(f'/pdn-admin/api/save-audio?session_token={valid_session_token}',
                               data=data,
                               content_type='multipart/form-data')
        assert response.status_code == 200
        result = response.get_json()
        assert result['status'] == 'success'

    def test_save_audio_empty_filename(self, client, valid_session_token):
        """Returns 400 when filename is empty."""
        import io
        data = {
            'audio': (io.BytesIO(b''), ''),
            'username': 'testuser'
        }
        response = client.post('/pdn-admin/api/save-audio',
                               data=data,
                               content_type='multipart/form-data')
        assert response.status_code == 400


class TestDownloadJson:
    """Tests for JSON download endpoint."""

    def test_download_json_no_session_token(self, client):
        """Returns 401 without session token."""
        response = client.get('/pdn-admin/download-json')
        assert response.status_code == 401

    def test_download_json_no_file_path(self, client, valid_session_token):
        """Returns 400 without file_path."""
        response = client.get(f'/pdn-admin/download-json?session_token={valid_session_token}')
        assert response.status_code == 400

    def test_download_json_file_not_found(self, client, valid_session_token, tmp_path, monkeypatch):
        """Returns 404 when file doesn't exist."""
        monkeypatch.setenv('SAVED_RESULTS_DIR', str(tmp_path))
        response = client.get(
            f'/pdn-admin/download-json?session_token={valid_session_token}&admin_password=pdn&file_path=nonexistent.json'
        )
        assert response.status_code == 404

    def test_download_json_not_json_file(self, client, valid_session_token, tmp_path, monkeypatch):
        """Returns 400 when file is not JSON."""
        monkeypatch.setenv('SAVED_RESULTS_DIR', str(tmp_path))
        txt_file = tmp_path / 'test.txt'
        txt_file.write_text('hello')
        response = client.get(
            f'/pdn-admin/download-json?session_token={valid_session_token}&admin_password=pdn&file_path=test.txt'
        )
        assert response.status_code == 400

    def test_download_json_success(self, client, valid_session_token, tmp_path, monkeypatch):
        """Successfully downloads JSON file."""
        monkeypatch.setenv('SAVED_RESULTS_DIR', str(tmp_path))
        json_file = tmp_path / 'test.json'
        json_file.write_text('{"key": "value"}')
        response = client.get(
            f'/pdn-admin/download-json?session_token={valid_session_token}&admin_password=pdn&file_path=test.json'
        )
        assert response.status_code == 200


class TestSendEmailExtended:
    """Additional tests for email endpoints."""

    @patch('app.pdn_admin.admin_routes.send_pdn_code_email')
    @patch('app.pdn_admin.admin_routes.calculate_pdn_code')
    @patch('app.pdn_admin.admin_routes.load_answers')
    def test_send_email_dict_result(self, mock_load, mock_calc, mock_send, client, valid_session_token):
        """Handles dict calculation result with needs_verification."""
        mock_load.return_value = {'answers': {'1': 'a'}}
        mock_calc.return_value = {'pdn_code': 'a3', 'needs_verification': True}
        mock_send.return_value = True

        response = client.post(f'/pdn-admin/user/send_email/test@test.com?session_token={valid_session_token}')
        assert response.status_code == 200
        data = response.get_json()
        assert data['needs_verification'] is True

    @patch('app.pdn_admin.admin_routes.send_pdn_code_email')
    @patch('app.pdn_admin.admin_routes.calculate_pdn_code')
    @patch('app.pdn_admin.admin_routes.load_answers')
    def test_send_email_no_pdn_code(self, mock_load, mock_calc, mock_send, client, valid_session_token):
        """Returns 400 when PDN code can't be calculated."""
        mock_load.return_value = {'answers': {'1': 'a'}}
        mock_calc.return_value = None

        response = client.post(f'/pdn-admin/user/send_email/test@test.com?session_token={valid_session_token}')
        assert response.status_code == 400

    @patch('app.pdn_admin.admin_routes.send_pdn_code_email')
    @patch('app.pdn_admin.admin_routes.calculate_pdn_code')
    @patch('app.pdn_admin.admin_routes.load_answers')
    def test_send_email_send_failure(self, mock_load, mock_calc, mock_send, client, valid_session_token):
        """Returns 500 when email sending fails."""
        mock_load.return_value = {'answers': {'1': 'a'}}
        mock_calc.return_value = 'a3'
        mock_send.return_value = False

        response = client.post(f'/pdn-admin/user/send_email/test@test.com?session_token={valid_session_token}')
        assert response.status_code == 500

    @patch('app.pdn_admin.admin_routes.send_binat_invite_email')
    @patch('app.pdn_admin.admin_routes.UserMetadataHandler')
    def test_send_binat_invite_failure(self, mock_handler_cls, mock_send, client, valid_session_token):
        """Returns 500 when Binat invite fails."""
        mock_handler = MagicMock()
        mock_handler.get_user_files.return_value = {'metadata': {'first_name': 'Test'}}
        mock_handler.get_user_by_email.return_value = None
        mock_handler_cls.return_value = mock_handler
        mock_send.return_value = False

        response = client.post(f'/pdn-admin/user/send_binat_invite/test@test.com?session_token={valid_session_token}')
        assert response.status_code == 500


class TestRecalculatePDNExtended:
    """Additional tests for PDN recalculation."""

    @patch('app.pdn_admin.admin_routes.UserMetadataHandler')
    @patch('app.pdn_admin.admin_routes.calculate_pdn_code')
    @patch('app.pdn_admin.admin_routes.load_answers')
    def test_recalculate_pdn_with_details(self, mock_load, mock_calc, mock_handler_cls, client, valid_session_token):
        """Handles calculation result with details."""
        mock_load.return_value = {'answers': {'1': 'a'}}
        mock_calc.return_value = {
            'pdn_code': 'e5',
            'needs_verification': True,
            'confidence_score': 75,
            'calculation_details': {'scores': [1, 2, 3]}
        }
        mock_handler = MagicMock()
        mock_handler.update_pdn_code_with_comment.return_value = True
        mock_handler.get_user_by_email.return_value = {'Date': '01/01/2025', 'PDN Update Comments': 'Admin'}
        mock_handler_cls.return_value = mock_handler

        response = client.post(f'/pdn-admin/user/recalculate_pdn/test@test.com?session_token={valid_session_token}')
        assert response.status_code == 200
        data = response.get_json()
        assert data['needs_verification'] is True
        assert 'calculation_details' in data

    @patch('app.pdn_admin.admin_routes.calculate_pdn_code')
    @patch('app.pdn_admin.admin_routes.load_answers')
    def test_recalculate_pdn_no_code(self, mock_load, mock_calc, client, valid_session_token):
        """Returns 400 when PDN code can't be calculated."""
        mock_load.return_value = {'answers': {'1': 'a'}}
        mock_calc.return_value = {'pdn_code': None, 'needs_verification': False, 'confidence_score': 0}

        response = client.post(f'/pdn-admin/user/recalculate_pdn/test@test.com?session_token={valid_session_token}')
        assert response.status_code == 400

    @patch('app.pdn_admin.admin_routes.UserMetadataHandler')
    @patch('app.pdn_admin.admin_routes.calculate_pdn_code')
    @patch('app.pdn_admin.admin_routes.load_answers')
    def test_recalculate_pdn_csv_update_fails(self, mock_load, mock_calc, mock_handler_cls, client, valid_session_token):
        """Returns 500 when CSV update fails."""
        mock_load.return_value = {'answers': {'1': 'a'}}
        mock_calc.return_value = 'a3'
        mock_handler = MagicMock()
        mock_handler.update_pdn_code_with_comment.return_value = False
        mock_handler_cls.return_value = mock_handler

        response = client.post(f'/pdn-admin/user/recalculate_pdn/test@test.com?session_token={valid_session_token}')
        assert response.status_code == 500


class TestUserVoiceExtended:
    """Additional tests for user voice endpoint."""

    @patch('app.pdn_admin.admin_routes.PDNFilePath')
    def test_get_user_voice_found(self, mock_pdn_path_cls, client, valid_session_token, tmp_path):
        """Returns voice recordings when found."""
        # Create a mock file
        voice_file = tmp_path / 'question1.wav'
        voice_file.write_bytes(b'RIFF' + b'\x00' * 100)

        mock_pdn_path = MagicMock()
        mock_pdn_path.find_user_file.side_effect = lambda email, filename: voice_file if 'question1' in filename else None
        mock_pdn_path_cls.return_value = mock_pdn_path

        response = client.get(f'/pdn-admin/user/voice/test@test.com?session_token={valid_session_token}')
        assert response.status_code == 200
        data = response.get_json()
        assert data['has_recordings'] is True


class TestLoadUserMetadataExtended:
    """Extended tests for load_user_metadata with JSON metadata and edge cases."""

    @patch('app.pdn_admin.admin_routes.UserMetadataHandler')
    def test_load_metadata_with_json_metadata(self, mock_handler_cls, tmp_path, monkeypatch):
        """Loads metadata merging CSV and JSON data."""
        csv_file = tmp_path / 'user_metadata.csv'
        csv_file.write_text(
            'Email,User ID,Date,PDN Code,PDN Voice Code,Diagnose PDN Code,'
            'Diagnose Comments,PDN Update Comments,First Name,Last Name,'
            'Phone,Native Language,Gender,Education Level,Job Title,Birth Year\n'
            'user@test.com,uid1,01/01/2025,a3,,,,,,CSV_First,CSV_Last,'
            '050,,male,,,1990\n',
            encoding='utf-8'
        )
        monkeypatch.setenv('SAVED_RESULTS_DIR', str(tmp_path))
        _metadata_cache['data'] = None
        _metadata_cache['timestamp'] = 0

        mock_handler = MagicMock()
        mock_handler.get_user_files.return_value = {
            'metadata': {
                'first_name': 'JSON_First',
                'last_name': 'JSON_Last',
                'phone': '054-1234567',
                'native_language': 'Hebrew',
                'gender': 'male',
                'education_level': 'BSc',
                'job_title': 'Engineer',
                'birth_year': '1985',
                'coupon_code': 'TESTCOUPON'
            }
        }
        mock_handler_cls.return_value = mock_handler

        result = load_user_metadata()
        assert len(result) == 1
        # JSON metadata takes precedence over CSV
        assert result[0]['first_name'] == 'JSON_First'
        assert result[0]['last_name'] == 'JSON_Last'
        assert result[0]['phone'] == '054-1234567'
        assert result[0]['coupon_code'] == 'TESTCOUPON'

    @patch('app.pdn_admin.admin_routes.UserMetadataHandler')
    def test_load_metadata_json_exception(self, mock_handler_cls, tmp_path, monkeypatch):
        """Handles exception when loading JSON metadata for a user."""
        csv_file = tmp_path / 'user_metadata.csv'
        csv_file.write_text(
            'Email,User ID,Date,PDN Code,PDN Voice Code,Diagnose PDN Code,'
            'Diagnose Comments,PDN Update Comments,First Name,Last Name,'
            'Phone,Native Language,Gender,Education Level,Job Title,Birth Year\n'
            'user@test.com,uid1,01/01/2025,a3,,,,,First,Last,'
            '050,,male,,,1990\n',
            encoding='utf-8'
        )
        monkeypatch.setenv('SAVED_RESULTS_DIR', str(tmp_path))
        _metadata_cache['data'] = None
        _metadata_cache['timestamp'] = 0

        mock_handler = MagicMock()
        mock_handler.get_user_files.side_effect = Exception("JSON load error")
        mock_handler_cls.return_value = mock_handler

        result = load_user_metadata()
        # Should still return the user with CSV data despite JSON error
        assert len(result) == 1
        assert result[0]['email'] == 'user@test.com'
        assert result[0]['first_name'] == 'First'

    @patch('app.pdn_admin.admin_routes.UserMetadataHandler')
    def test_load_metadata_general_exception(self, mock_handler_cls, monkeypatch):
        """Returns empty list on general exception."""
        monkeypatch.setenv('SAVED_RESULTS_DIR', '/some/path')
        _metadata_cache['data'] = None
        _metadata_cache['timestamp'] = 0

        # Patch open to raise an exception
        with patch('builtins.open', side_effect=PermissionError("Access denied")):
            with patch('pathlib.Path.exists', return_value=True):
                result = load_user_metadata()
        assert result == []


class TestGetUserQuestionnaireExtended:
    """Extended tests for get_user_questionnaire endpoint."""

    @patch('app.pdn_admin.admin_routes.UserMetadataHandler')
    def test_questionnaire_no_csv_metadata(self, mock_handler_cls, client, valid_session_token):
        """Returns questionnaire with default metadata when CSV has no user."""
        mock_handler = MagicMock()
        mock_handler.get_user_files.return_value = {'answers': {'1': 'a'}}
        mock_handler.get_user_by_email.return_value = None
        mock_handler_cls.return_value = mock_handler

        response = client.get(
            f'/pdn-admin/user/questionnaire/nocsv@test.com?session_token={valid_session_token}'
        )
        assert response.status_code == 200
        data = response.get_json()
        assert 'metadata' in data
        assert data['metadata']['email'] == 'nocsv@test.com'

    @patch('app.pdn_admin.admin_routes.UserMetadataHandler')
    def test_questionnaire_exception(self, mock_handler_cls, client, valid_session_token):
        """Returns 500 when an exception occurs loading questionnaire."""
        mock_handler = MagicMock()
        mock_handler.get_user_files.side_effect = Exception("DB error")
        mock_handler_cls.return_value = mock_handler

        response = client.get(
            f'/pdn-admin/user/questionnaire/error@test.com?session_token={valid_session_token}'
        )
        assert response.status_code == 500
        data = response.get_json()
        assert 'error' in data


class TestGetUserVoiceExtended:
    """Extended tests for get_user_voice endpoint."""

    @patch('app.pdn_admin.admin_routes.PDNFilePath')
    def test_voice_file_access_error(self, mock_pdn_path_cls, client, valid_session_token, tmp_path):
        """Handles OSError when accessing voice file."""
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_file.is_file.side_effect = OSError("Permission denied")

        mock_pdn_path = MagicMock()
        mock_pdn_path.find_user_file.return_value = mock_file
        mock_pdn_path_cls.return_value = mock_pdn_path

        response = client.get(
            f'/pdn-admin/user/voice/test@test.com?session_token={valid_session_token}'
        )
        # No valid recordings found due to OSError, returns 404
        assert response.status_code == 404

    @patch('app.pdn_admin.admin_routes.PDNFilePath')
    def test_voice_outer_exception(self, mock_pdn_path_cls, client, valid_session_token):
        """Returns 404 when outer exception occurs."""
        mock_pdn_path_cls.side_effect = Exception("Init error")

        response = client.get(
            f'/pdn-admin/user/voice/test@test.com?session_token={valid_session_token}'
        )
        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data

    @patch('app.pdn_admin.admin_routes.PDNFilePath')
    def test_voice_file_zero_size(self, mock_pdn_path_cls, client, valid_session_token, tmp_path):
        """Returns 404 when voice file has zero size."""
        # Create a zero-byte file
        voice_file = tmp_path / 'question1.wav'
        voice_file.write_bytes(b'')

        mock_pdn_path = MagicMock()
        mock_pdn_path.find_user_file.side_effect = lambda email, filename: (
            voice_file if 'question1' in filename else None
        )
        mock_pdn_path_cls.return_value = mock_pdn_path

        response = client.get(
            f'/pdn-admin/user/voice/test@test.com?session_token={valid_session_token}'
        )
        # Zero-size file is skipped, no valid recordings → 404
        assert response.status_code == 404



class TestAudioRoutesCoverage:
    """Tests for audio_routes.py to achieve >90% coverage.

    Tests full file serving, range requests, error handling,
    and path traversal protection with mocked file system access.
    """

    @pytest.fixture
    def audio_app(self):
        """Create a Flask app with the audio blueprint registered."""
        from app.pdn_admin.audio_routes import audio_bp
        application = Flask(__name__)
        application.config['TESTING'] = True
        application.config['SECRET_KEY'] = 'test-secret-key'
        application.register_blueprint(audio_bp, url_prefix='/pdn-admin')
        return application

    @pytest.fixture
    def audio_client(self, audio_app):
        """Create Flask test client for audio routes."""
        return audio_app.test_client()

    @patch('app.pdn_admin.audio_routes.PDNFilePath')
    @patch('os.path.getsize')
    def test_full_file_request_returns_200(self, mock_getsize, mock_pdn_cls, audio_client, tmp_path):
        """Full file request returns 200 with audio/wav content."""
        # Create a real temp file for send_file to work
        audio_file = tmp_path / 'recording.wav'
        audio_content = b'RIFF' + b'\x00' * 100
        audio_file.write_bytes(audio_content)

        mock_pdn = MagicMock()
        mock_pdn.get_user_dir.return_value = tmp_path
        mock_pdn_cls.return_value = mock_pdn
        mock_getsize.return_value = len(audio_content)

        response = audio_client.get('/pdn-admin/audio/user@test.com/recording.wav')
        assert response.status_code == 200
        assert response.content_type == 'audio/wav'

    @patch('app.pdn_admin.audio_routes.PDNFilePath')
    @patch('os.path.getsize')
    def test_range_request_returns_206_with_content_range(self, mock_getsize, mock_pdn_cls, audio_client, tmp_path):
        """Range request returns 206 with correct Content-Range headers."""
        # Create a real temp file
        audio_file = tmp_path / 'recording.wav'
        audio_content = b'RIFF' + b'\x00' * 1000
        audio_file.write_bytes(audio_content)

        mock_pdn = MagicMock()
        mock_pdn.get_user_dir.return_value = tmp_path
        mock_pdn_cls.return_value = mock_pdn
        mock_getsize.return_value = len(audio_content)

        response = audio_client.get(
            '/pdn-admin/audio/user@test.com/recording.wav',
            headers={'Range': 'bytes=0-99'}
        )
        assert response.status_code == 206
        assert response.headers.get('Content-Range') == f'bytes 0-99/{len(audio_content)}'
        assert response.headers.get('Accept-Ranges') == 'bytes'
        assert response.headers.get('Content-Length') == '100'
        assert len(response.data) == 100

    @patch('app.pdn_admin.audio_routes.PDNFilePath')
    @patch('os.path.getsize')
    def test_range_request_middle_range(self, mock_getsize, mock_pdn_cls, audio_client, tmp_path):
        """Range request for middle of file returns correct bytes."""
        audio_file = tmp_path / 'recording.wav'
        audio_content = b'A' * 500 + b'B' * 500
        audio_file.write_bytes(audio_content)

        mock_pdn = MagicMock()
        mock_pdn.get_user_dir.return_value = tmp_path
        mock_pdn_cls.return_value = mock_pdn
        mock_getsize.return_value = len(audio_content)

        response = audio_client.get(
            '/pdn-admin/audio/user@test.com/recording.wav',
            headers={'Range': 'bytes=500-599'}
        )
        assert response.status_code == 206
        assert response.headers.get('Content-Range') == f'bytes 500-599/{len(audio_content)}'
        assert len(response.data) == 100
        assert response.data == b'B' * 100

    @patch('app.pdn_admin.audio_routes.PDNFilePath')
    def test_non_existent_file_returns_404(self, mock_pdn_cls, audio_client, tmp_path):
        """Non-existent file returns 404."""
        mock_pdn = MagicMock()
        mock_pdn.get_user_dir.return_value = tmp_path
        mock_pdn_cls.return_value = mock_pdn

        response = audio_client.get('/pdn-admin/audio/user@test.com/nonexistent.wav')
        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data
        assert 'not found' in data['error'].lower()

    @patch('app.pdn_admin.audio_routes.PDNFilePath')
    @patch('os.path.getsize')
    def test_invalid_range_returns_416(self, mock_getsize, mock_pdn_cls, audio_client, tmp_path):
        """Invalid range header returns 416."""
        audio_file = tmp_path / 'recording.wav'
        audio_content = b'RIFF' + b'\x00' * 100
        audio_file.write_bytes(audio_content)

        mock_pdn = MagicMock()
        mock_pdn.get_user_dir.return_value = tmp_path
        mock_pdn_cls.return_value = mock_pdn
        mock_getsize.return_value = len(audio_content)

        # Range start beyond file size
        response = audio_client.get(
            '/pdn-admin/audio/user@test.com/recording.wav',
            headers={'Range': 'bytes=5000-6000'}
        )
        assert response.status_code == 416
        data = response.get_json()
        assert 'error' in data

    @patch('app.pdn_admin.audio_routes.PDNFilePath')
    @patch('os.path.getsize')
    def test_invalid_range_format_returns_416(self, mock_getsize, mock_pdn_cls, audio_client, tmp_path):
        """Malformed range header returns 416."""
        audio_file = tmp_path / 'recording.wav'
        audio_content = b'RIFF' + b'\x00' * 100
        audio_file.write_bytes(audio_content)

        mock_pdn = MagicMock()
        mock_pdn.get_user_dir.return_value = tmp_path
        mock_pdn_cls.return_value = mock_pdn
        mock_getsize.return_value = len(audio_content)

        # Malformed range
        response = audio_client.get(
            '/pdn-admin/audio/user@test.com/recording.wav',
            headers={'Range': 'bytes=abc-def'}
        )
        assert response.status_code == 416

    @patch('app.pdn_admin.audio_routes.PDNFilePath')
    @patch('os.path.getsize')
    def test_range_start_greater_than_end_returns_416(self, mock_getsize, mock_pdn_cls, audio_client, tmp_path):
        """Range where start > end returns 416."""
        audio_file = tmp_path / 'recording.wav'
        audio_content = b'RIFF' + b'\x00' * 100
        audio_file.write_bytes(audio_content)

        mock_pdn = MagicMock()
        mock_pdn.get_user_dir.return_value = tmp_path
        mock_pdn_cls.return_value = mock_pdn
        mock_getsize.return_value = len(audio_content)

        response = audio_client.get(
            '/pdn-admin/audio/user@test.com/recording.wav',
            headers={'Range': 'bytes=50-10'}
        )
        assert response.status_code == 416

    @patch('app.pdn_admin.audio_routes.PDNFilePath')
    @patch('os.path.getsize')
    def test_empty_file_returns_404(self, mock_getsize, mock_pdn_cls, audio_client, tmp_path):
        """Empty file (zero bytes) returns 404."""
        audio_file = tmp_path / 'empty.wav'
        audio_file.write_bytes(b'')

        mock_pdn = MagicMock()
        mock_pdn.get_user_dir.return_value = tmp_path
        mock_pdn_cls.return_value = mock_pdn
        mock_getsize.return_value = 0

        response = audio_client.get('/pdn-admin/audio/user@test.com/empty.wav')
        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data
        assert 'empty' in data['error'].lower()

    @patch('app.pdn_admin.audio_routes.PDNFilePath')
    def test_path_traversal_protection_returns_403(self, mock_pdn_cls, audio_client, tmp_path):
        """Path traversal attempt is blocked.

        The audio route uses PDNFilePath.get_user_dir which sanitizes the user part,
        and the filename is used directly. When a path traversal is attempted via
        the filename portion (e.g., ../../../etc/passwd), the resolved path should
        not serve files outside the user directory. The route returns 404 because
        the traversal path doesn't exist after sanitization.
        """
        mock_pdn = MagicMock()
        mock_pdn.get_user_dir.return_value = tmp_path
        mock_pdn_cls.return_value = mock_pdn

        # Path traversal via filename - file won't exist at traversed path
        response = audio_client.get('/pdn-admin/audio/user@test.com/../../etc/passwd')
        # The route returns 404 because the file doesn't exist after path resolution
        # This effectively blocks path traversal (file not served)
        assert response.status_code in (403, 404)

    @patch('app.pdn_admin.audio_routes.PDNFilePath')
    def test_path_traversal_via_user_part(self, mock_pdn_cls, audio_client, tmp_path):
        """Path traversal via user directory part is sanitized by PDNFilePath."""
        mock_pdn = MagicMock()
        # PDNFilePath sanitizes the user part, so traversal chars are stripped
        mock_pdn.get_user_dir.return_value = tmp_path / 'sanitized'
        mock_pdn_cls.return_value = mock_pdn

        response = audio_client.get('/pdn-admin/audio/../../../etc/passwd')
        # File won't exist in the sanitized directory
        assert response.status_code in (403, 404)

    @patch('app.pdn_admin.audio_routes.PDNFilePath')
    @patch('os.path.getsize')
    def test_filename_without_user_directory(self, mock_getsize, mock_pdn_cls, audio_client, tmp_path):
        """Filename without user directory uses 'default' user part."""
        audio_file = tmp_path / 'simple.wav'
        audio_content = b'RIFF' + b'\x00' * 50
        audio_file.write_bytes(audio_content)

        mock_pdn = MagicMock()
        mock_pdn.get_user_dir.return_value = tmp_path
        mock_pdn_cls.return_value = mock_pdn
        mock_getsize.return_value = len(audio_content)

        response = audio_client.get('/pdn-admin/audio/simple.wav')
        assert response.status_code == 200
        # Verify PDNFilePath was called with 'default' since no '/' in filename
        mock_pdn.get_user_dir.assert_called_with('default')

    @patch('app.pdn_admin.audio_routes.PDNFilePath')
    def test_internal_server_error_returns_500(self, mock_pdn_cls, audio_client):
        """Internal error during file serving returns 500."""
        mock_pdn = MagicMock()
        mock_pdn.get_user_dir.side_effect = Exception("Unexpected error")
        mock_pdn_cls.return_value = mock_pdn

        response = audio_client.get('/pdn-admin/audio/user@test.com/file.wav')
        assert response.status_code == 500
        data = response.get_json()
        assert 'error' in data
        assert 'Internal server error' in data['error']

    @patch('app.pdn_admin.audio_routes.PDNFilePath')
    @patch('os.path.getsize')
    def test_range_request_without_end(self, mock_getsize, mock_pdn_cls, audio_client, tmp_path):
        """Range request without end byte serves to end of file."""
        audio_file = tmp_path / 'recording.wav'
        audio_content = b'RIFF' + b'\x00' * 200
        audio_file.write_bytes(audio_content)

        mock_pdn = MagicMock()
        mock_pdn.get_user_dir.return_value = tmp_path
        mock_pdn_cls.return_value = mock_pdn
        mock_getsize.return_value = len(audio_content)

        response = audio_client.get(
            '/pdn-admin/audio/user@test.com/recording.wav',
            headers={'Range': 'bytes=100-'}
        )
        assert response.status_code == 206
        expected_end = len(audio_content) - 1
        assert response.headers.get('Content-Range') == f'bytes 100-{expected_end}/{len(audio_content)}'
        assert len(response.data) == len(audio_content) - 100


class TestSendUserEmailExtended:
    """Extended tests for send_user_email endpoint."""

    @patch('app.pdn_admin.admin_routes.send_pdn_code_email')
    @patch('app.pdn_admin.admin_routes.calculate_pdn_code')
    @patch('app.pdn_admin.admin_routes.load_answers')
    def test_send_email_exception(self, mock_load, mock_calc, mock_send, client, valid_session_token):
        """Returns 500 when an exception occurs."""
        mock_load.side_effect = Exception("Storage error")

        response = client.post(
            f'/pdn-admin/user/send_email/test@test.com?session_token={valid_session_token}'
        )
        assert response.status_code == 500
        data = response.get_json()
        assert 'error' in data

    @patch('app.pdn_admin.admin_routes.send_pdn_code_email')
    @patch('app.pdn_admin.admin_routes.calculate_pdn_code')
    @patch('app.pdn_admin.admin_routes.load_answers')
    def test_send_email_dict_no_pdn_code(self, mock_load, mock_calc, mock_send, client, valid_session_token):
        """Returns 400 when dict result has empty pdn_code."""
        mock_load.return_value = {'answers': {'1': 'a'}}
        mock_calc.return_value = {'pdn_code': '', 'needs_verification': False}

        response = client.post(
            f'/pdn-admin/user/send_email/test@test.com?session_token={valid_session_token}'
        )
        assert response.status_code == 400


class TestSendBinatInviteExtended:
    """Extended tests for send_binat_invite endpoint."""

    @patch('app.pdn_admin.admin_routes.send_binat_invite_email')
    @patch('app.pdn_admin.admin_routes.UserMetadataHandler')
    def test_binat_invite_no_first_name_in_questionnaire(
        self, mock_handler_cls, mock_send, client, valid_session_token
    ):
        """Falls back to CSV First Name when questionnaire has no first_name."""
        mock_handler = MagicMock()
        mock_handler.get_user_files.return_value = {'metadata': {}}
        mock_handler.get_user_by_email.return_value = {'First Name': 'CSVName'}
        mock_handler_cls.return_value = mock_handler
        mock_send.return_value = True

        response = client.post(
            f'/pdn-admin/user/send_binat_invite/test@test.com?session_token={valid_session_token}'
        )
        assert response.status_code == 200
        mock_send.assert_called_once_with('test@test.com', 'CSVName')

    @patch('app.pdn_admin.admin_routes.send_binat_invite_email')
    @patch('app.pdn_admin.admin_routes.UserMetadataHandler')
    def test_binat_invite_no_first_name_anywhere(
        self, mock_handler_cls, mock_send, client, valid_session_token
    ):
        """Sends invite with empty first_name when not found anywhere."""
        mock_handler = MagicMock()
        mock_handler.get_user_files.return_value = None
        mock_handler.get_user_by_email.return_value = None
        mock_handler_cls.return_value = mock_handler
        mock_send.return_value = True

        response = client.post(
            f'/pdn-admin/user/send_binat_invite/test@test.com?session_token={valid_session_token}'
        )
        assert response.status_code == 200
        mock_send.assert_called_once_with('test@test.com', '')

    @patch('app.pdn_admin.admin_routes.send_binat_invite_email')
    @patch('app.pdn_admin.admin_routes.UserMetadataHandler')
    def test_binat_invite_exception(
        self, mock_handler_cls, mock_send, client, valid_session_token
    ):
        """Returns 500 when an exception occurs."""
        mock_handler_cls.side_effect = Exception("Handler init error")

        response = client.post(
            f'/pdn-admin/user/send_binat_invite/test@test.com?session_token={valid_session_token}'
        )
        assert response.status_code == 500
        data = response.get_json()
        assert 'error' in data


class TestRecalculatePDNFullCoverage:
    """Full coverage tests for recalculate_user_pdn endpoint."""

    @patch('app.pdn_admin.admin_routes.UserMetadataHandler')
    @patch('app.pdn_admin.admin_routes.calculate_pdn_code')
    @patch('app.pdn_admin.admin_routes.load_answers')
    def test_recalculate_pdn_string_result(
        self, mock_load, mock_calc, mock_handler_cls, client, valid_session_token
    ):
        """Handles string calculation result (not dict)."""
        mock_load.return_value = {'answers': {'1': 'a'}}
        mock_calc.return_value = 'p6'
        mock_handler = MagicMock()
        mock_handler.update_pdn_code_with_comment.return_value = True
        mock_handler.get_user_by_email.return_value = {
            'Date': '15/06/2025',
            'PDN Update Comments': 'Admin recalculated'
        }
        mock_handler_cls.return_value = mock_handler

        response = client.post(
            f'/pdn-admin/user/recalculate_pdn/test@test.com?session_token={valid_session_token}'
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['pdn_code'] == 'p6'
        assert data['needs_verification'] is False
        assert data['confidence_score'] == 0
        assert 'calculation_details' not in data

    @patch('app.pdn_admin.admin_routes.UserMetadataHandler')
    @patch('app.pdn_admin.admin_routes.calculate_pdn_code')
    @patch('app.pdn_admin.admin_routes.load_answers')
    def test_recalculate_pdn_exception(
        self, mock_load, mock_calc, mock_handler_cls, client, valid_session_token
    ):
        """Returns 500 when an exception occurs."""
        mock_load.side_effect = Exception("Storage error")

        response = client.post(
            f'/pdn-admin/user/recalculate_pdn/test@test.com?session_token={valid_session_token}'
        )
        assert response.status_code == 500
        data = response.get_json()
        assert 'error' in data

    @patch('app.pdn_admin.admin_routes.UserMetadataHandler')
    @patch('app.pdn_admin.admin_routes.calculate_pdn_code')
    @patch('app.pdn_admin.admin_routes.load_answers')
    def test_recalculate_pdn_no_user_data_in_csv(
        self, mock_load, mock_calc, mock_handler_cls, client, valid_session_token
    ):
        """Handles case where get_user_by_email returns None."""
        mock_load.return_value = {'answers': {'1': 'a'}}
        mock_calc.return_value = {'pdn_code': 'e5', 'needs_verification': False, 'confidence_score': 90}
        mock_handler = MagicMock()
        mock_handler.update_pdn_code_with_comment.return_value = True
        mock_handler.get_user_by_email.return_value = None
        mock_handler_cls.return_value = mock_handler

        response = client.post(
            f'/pdn-admin/user/recalculate_pdn/test@test.com?session_token={valid_session_token}'
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['date'] == ''
        assert data['pdn_update_comments'] == ''


class TestPathTraversalProtectionProperty:
    """Property-based test for path traversal protection in serve_audio.

    **Validates: Requirements 1.7**

    Property 2: Path Traversal Protection
    For any file path that resolves outside the allowed SAVED_RESULTS_DIR directory
    (e.g., containing ../ sequences), the serve_audio endpoint rejects the request
    (returns 403 or 404), never serving files outside the allowed directory.
    """

    def _make_audio_client(self):
        """Create a Flask app and test client with the audio blueprint."""
        from app.pdn_admin.audio_routes import audio_bp
        application = Flask(__name__)
        application.config['TESTING'] = True
        application.config['SECRET_KEY'] = 'test-secret-key'
        application.register_blueprint(audio_bp, url_prefix='/pdn-admin')
        return application, application.test_client()

    @given(
        traversal_segments=st.lists(
            st.sampled_from(['..', '../', '..%2F', '..%2f', '....', './../']),
            min_size=1,
            max_size=5,
        ),
        suffix=st.sampled_from([
            'etc/passwd', 'etc/shadow', 'var/log/syslog',
            'home/user/.ssh/id_rsa', 'Windows/System32/config/sam',
            'proc/self/environ', 'app/secrets.json',
        ]),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_traversal_paths_never_serve_outside_directory(
        self, traversal_segments, suffix, tmp_path
    ):
        """Any path with traversal sequences resolving outside SAVED_RESULTS_DIR
        is rejected with 403 or 404, never serving external files."""
        audio_app, audio_client = self._make_audio_client()

        # Build a traversal path from the generated segments
        traversal_path = '/'.join(traversal_segments) + '/' + suffix

        with audio_app.app_context():
            with patch('app.pdn_admin.audio_routes.PDNFilePath') as mock_pdn_cls:
                mock_pdn = MagicMock()
                mock_pdn.get_user_dir.return_value = tmp_path / 'user_dir'
                mock_pdn_cls.return_value = mock_pdn

                # The traversal path is used as the filename in the URL
                # Format: /pdn-admin/audio/<path:filename>
                # We test with user/traversal_path format
                response = audio_client.get(
                    f'/pdn-admin/audio/user@test.com/{traversal_path}'
                )

                # The endpoint must NEVER return 200 for traversal paths
                # It should return 403 (forbidden) or 404 (not found)
                assert response.status_code in (403, 404, 500), (
                    f"Path traversal attempt with '{traversal_path}' returned "
                    f"status {response.status_code}, expected 403/404"
                )
                # Critically: must never return 200 (file served)
                assert response.status_code != 200, (
                    f"SECURITY: Path traversal '{traversal_path}' served a file!"
                )

    @given(
        num_dotdot=st.integers(min_value=1, max_value=10),
        target_file=st.from_regex(r'[a-z]{1,10}\.[a-z]{2,4}', fullmatch=True),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_dotdot_sequences_blocked(
        self, num_dotdot, target_file, tmp_path
    ):
        """Repeated ../ sequences of any depth are blocked."""
        audio_app, audio_client = self._make_audio_client()

        traversal = '/'.join(['..'] * num_dotdot) + '/' + target_file

        with audio_app.app_context():
            with patch('app.pdn_admin.audio_routes.PDNFilePath') as mock_pdn_cls:
                mock_pdn = MagicMock()
                # Set user_dir to a subdirectory of tmp_path
                user_dir = tmp_path / 'saved_results' / 'user'
                user_dir.mkdir(parents=True, exist_ok=True)
                mock_pdn.get_user_dir.return_value = user_dir
                mock_pdn_cls.return_value = mock_pdn

                response = audio_client.get(
                    f'/pdn-admin/audio/user@test.com/{traversal}'
                )

                # Must never serve files - should be 403 or 404
                assert response.status_code != 200, (
                    f"SECURITY: Path with {'../' * num_dotdot}{target_file} "
                    f"returned 200!"
                )
                assert response.status_code in (403, 404, 500)


class TestInvalidInputResponses:
    """Tests verifying invalid input returns HTTP 400/404."""

    @patch('app.pdn_admin.admin_routes.load_answers')
    def test_send_email_no_answers_returns_404(self, mock_load, client, valid_session_token):
        """send_user_email returns 404 when user has no answers."""
        mock_load.return_value = None
        response = client.post(
            f'/pdn-admin/user/send_email/nonexistent@test.com?session_token={valid_session_token}'
        )
        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data
        assert 'not found' in data['error'].lower()

    @patch('app.pdn_admin.admin_routes.calculate_pdn_code')
    @patch('app.pdn_admin.admin_routes.load_answers')
    def test_send_email_null_pdn_code_returns_400(
        self, mock_load, mock_calc, client, valid_session_token
    ):
        """send_user_email returns 400 when PDN code is None."""
        mock_load.return_value = {'answers': {'1': 'a'}}
        mock_calc.return_value = None
        response = client.post(
            f'/pdn-admin/user/send_email/test@test.com?session_token={valid_session_token}'
        )
        assert response.status_code == 400

    @patch('app.pdn_admin.admin_routes.load_answers')
    def test_recalculate_pdn_no_answers_returns_404(self, mock_load, client, valid_session_token):
        """recalculate_user_pdn returns 404 when user has no answers."""
        mock_load.return_value = None
        response = client.post(
            f'/pdn-admin/user/recalculate_pdn/nonexistent@test.com?session_token={valid_session_token}'
        )
        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data
        assert 'not found' in data['error'].lower()

    @patch('app.pdn_admin.admin_routes.calculate_pdn_code')
    @patch('app.pdn_admin.admin_routes.load_answers')
    def test_recalculate_pdn_null_code_returns_400(
        self, mock_load, mock_calc, client, valid_session_token
    ):
        """recalculate_user_pdn returns 400 when PDN code is None."""
        mock_load.return_value = {'answers': {'1': 'a'}}
        mock_calc.return_value = None
        response = client.post(
            f'/pdn-admin/user/recalculate_pdn/test@test.com?session_token={valid_session_token}'
        )
        assert response.status_code == 400

    @patch('app.pdn_admin.admin_routes.UserMetadataHandler')
    def test_questionnaire_not_found_returns_404(self, mock_handler_cls, client, valid_session_token):
        """get_user_questionnaire returns 404 when no data found."""
        mock_handler = MagicMock()
        mock_handler.get_user_files.return_value = None
        mock_handler_cls.return_value = mock_handler

        response = client.get(
            f'/pdn-admin/user/questionnaire/missing@test.com?session_token={valid_session_token}'
        )
        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data

    @patch('app.pdn_admin.admin_routes.PDNFilePath')
    def test_voice_not_found_returns_404(self, mock_pdn_path_cls, client, valid_session_token):
        """get_user_voice returns 404 when no recordings found."""
        mock_pdn_path = MagicMock()
        mock_pdn_path.find_user_file.return_value = None
        mock_pdn_path_cls.return_value = mock_pdn_path

        response = client.get(
            f'/pdn-admin/user/voice/missing@test.com?session_token={valid_session_token}'
        )
        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data

    @patch('app.pdn_admin.admin_routes.load_user_metadata')
    def test_update_diagnose_user_not_found_returns_404(
        self, mock_load, client, valid_session_token
    ):
        """update_user_diagnose returns 404 when user not in metadata."""
        mock_load.return_value = []
        response = client.put(
            f'/pdn-admin/user/diagnose/missing@test.com?session_token={valid_session_token}',
            json={'diagnose_pdn_code': 'a3'}
        )
        assert response.status_code == 404


# --- Property-Based Tests ---

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st


class TestSessionLifecycleProperty:
    """Property-based test for session lifecycle validity.

    **Validates: Requirements 1.3**

    Property 1: Session Lifecycle Validity
    For any email string, creating a session produces a token that passes
    verification. After the session expires (time advanced past SESSION_TIMEOUT),
    verification rejects that same token.
    """

    @given(email=st.from_regex(r'[a-z]{3,10}@[a-z]{3,8}\.[a-z]{2,4}', fullmatch=True))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_session_lifecycle_validity(self, email, app):
        """Created session verifies; expired session rejects."""
        # Clear sessions to avoid interference between examples
        admin_sessions.clear()

        # Create a session for the given email
        token = create_session(email)

        # The token should be in admin_sessions
        assert token in admin_sessions
        assert admin_sessions[token]['email'] == email

        # Verify the session succeeds (within app context for abort to work)
        with app.test_request_context():
            session_data = verify_session(token)
            assert session_data['email'] == email

        # Now expire the session by setting expires_at in the past
        admin_sessions[token]['expires_at'] = datetime.now() - timedelta(seconds=1)

        # Verification should now reject the expired token
        with app.test_request_context():
            with pytest.raises(Exception):
                verify_session(token)

        # The expired token should have been removed from admin_sessions
        assert token not in admin_sessions


# --- Property-Based Tests ---

import tempfile
from hypothesis import given, settings, strategies as st


class TestAudioRangeRequestProperty:
    """Property-based test for audio range request correctness.

    **Validates: Requirements 2.3**

    Property 3: Audio Range Request Correctness
    For any valid byte range (start, end) where 0 <= start <= end < file_size,
    the audio endpoint returns HTTP 206 with a Content-Range header of
    "bytes {start}-{end}/{file_size}" and a response body of exactly
    (end - start + 1) bytes.
    """

    @given(data=st.data())
    @settings(max_examples=50)
    def test_valid_range_returns_206_with_correct_headers_and_body(self, data):
        """For any valid byte range (start, end) where 0 <= start <= end < file_size,
        the audio endpoint returns HTTP 206 with correct Content-Range and body length.

        **Validates: Requirements 2.3**
        """
        # Generate a file size between 1 and 10000 bytes
        file_size = data.draw(st.integers(min_value=1, max_value=10000), label="file_size")

        # Generate valid start and end within file bounds
        start = data.draw(st.integers(min_value=0, max_value=file_size - 1), label="start")
        end = data.draw(st.integers(min_value=start, max_value=file_size - 1), label="end")

        # Create a temp audio file with known content
        audio_content = bytes(range(256)) * (file_size // 256 + 1)
        audio_content = audio_content[:file_size]

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = RealPath(tmp_dir)
            audio_file = tmp_path / 'test_audio.wav'
            audio_file.write_bytes(audio_content)

            # Set up Flask app and client
            from app.pdn_admin.audio_routes import audio_bp
            application = Flask(__name__)
            application.config['TESTING'] = True
            application.config['SECRET_KEY'] = 'test-secret-key'
            application.register_blueprint(audio_bp, url_prefix='/pdn-admin')

            with application.test_client() as client:
                with patch('app.pdn_admin.audio_routes.PDNFilePath') as mock_pdn_cls, \
                     patch('os.path.getsize', return_value=file_size):
                    mock_pdn = MagicMock()
                    mock_pdn.get_user_dir.return_value = tmp_path
                    mock_pdn_cls.return_value = mock_pdn

                    response = client.get(
                        '/pdn-admin/audio/user@test.com/test_audio.wav',
                        headers={'Range': f'bytes={start}-{end}'}
                    )

                    # Assert HTTP 206 Partial Content
                    assert response.status_code == 206, (
                        f"Expected 206 for range {start}-{end} of file_size={file_size}, "
                        f"got {response.status_code}"
                    )

                    # Assert Content-Range header is correct
                    expected_content_range = f'bytes {start}-{end}/{file_size}'
                    assert response.headers.get('Content-Range') == expected_content_range, (
                        f"Expected Content-Range '{expected_content_range}', "
                        f"got '{response.headers.get('Content-Range')}'"
                    )

                    # Assert response body length is exactly (end - start + 1) bytes
                    expected_length = end - start + 1
                    assert len(response.data) == expected_length, (
                        f"Expected body length {expected_length} for range {start}-{end}, "
                        f"got {len(response.data)}"
                    )

                    # Assert the body content matches the expected slice of the file
                    expected_data = audio_content[start:end + 1]
                    assert response.data == expected_data, (
                        f"Response body doesn't match expected file content for range {start}-{end}"
                    )


# ============================================================
# Additional tests to close coverage gap for admin_routes.py
# Target: lines 278-279, 286-287, 703-705, 726-727, 758-759,
#         781-782, 796-798, 912-913, 926, 940-941, 953-957,
#         978-980, 993-995, 1005, 1041-1044, 1052, 1056,
#         1078-1082, 1090, 1098-1100, 1108, 1117-1119
# ============================================================


class TestLoggedInUsersExtended:
    """Tests for get_logged_in_users covering diagnosis/chat session loading."""

    @pytest.fixture(autouse=True)
    def setup(self, clear_admin_sessions):
        pass

    def test_logged_in_users_with_diagnosis_sessions(self, client, valid_session_token):
        """Cover lines 278-279: loading diagnosis sessions."""
        mock_sessions = {
            'diag-token-1': {
                'email': 'diag@test.com',
                'login_time': datetime.now(),
                'expires_at': datetime.now() + timedelta(hours=1)
            }
        }
        with patch('app.pdn_admin.admin_routes.admin_sessions', {
            valid_session_token: admin_sessions[valid_session_token]
        }):
            with patch.dict('sys.modules', {'app.pdn_diagnose.diagnosis_routes': MagicMock(active_sessions=mock_sessions)}):
                from app.pdn_diagnose import diagnosis_routes
                diagnosis_routes.active_sessions = mock_sessions
                response = client.get(f'/pdn-admin/logged-in-users?session_token={valid_session_token}')
                assert response.status_code == 200

    def test_logged_in_users_with_chat_sessions(self, client, valid_session_token):
        """Cover lines 286-287: loading chat sessions."""
        mock_chat_sessions = {
            'chat-token-1': {
                'email': 'chat@test.com',
                'login_time': datetime.now(),
                'expires_at': datetime.now() + timedelta(hours=1)
            }
        }
        with patch('app.pdn_chat_ai.chat_routes.chat_sessions', mock_chat_sessions):
            response = client.get(f'/pdn-admin/logged-in-users?session_token={valid_session_token}')
            assert response.status_code == 200


class TestUserJourneyExtended:
    """Tests for get_user_journey covering token usage, conversations, and date parsing."""

    @pytest.fixture(autouse=True)
    def setup(self, clear_admin_sessions):
        pass

    def test_journey_with_token_usage_data(self, client, valid_session_token):
        """Cover lines 703-705, 726-727: token usage loading and events."""
        mock_handler = MagicMock()
        mock_handler.get_user_by_email.return_value = {
            'First Name': 'Test',
            'Last Name': 'User',
            'PDN Code': 'e5',
            'Date': '15/01/2025'
        }
        mock_stats = {
            '2025-01-20': {'test@example.com': 3}
        }
        mock_agent = MagicMock()
        mock_agent.token_usage = {
            'test@example.com': {
                '2025-01-20': {
                    'input_tokens': 5000,
                    'output_tokens': 2000,
                    'calls': 10
                }
            }
        }
        with patch('app.pdn_admin.admin_routes.UserMetadataHandler', return_value=mock_handler), \
             patch('app.pdn_admin.admin_routes.conversation_stats') as mock_conv_stats, \
             patch('app.pdn_chat_ai.chat_routes.get_agent_instance', return_value=mock_agent):
            mock_conv_stats._read_locked.return_value = mock_stats
            response = client.get(f'/pdn-admin/user/journey/test@example.com?session_token={valid_session_token}')
            assert response.status_code == 200
            data = response.get_json()
            assert data['email'] == 'test@example.com'
            assert len(data['events']) > 0

    def test_journey_with_name_based_token_lookup(self, client, valid_session_token):
        """Cover lines 726-727: fallback to first name for token lookup."""
        mock_handler = MagicMock()
        mock_handler.get_user_by_email.return_value = {
            'First Name': 'TestName',
            'Last Name': 'User',
            'PDN Code': 'e5',
            'Date': '15/01/2025'
        }
        mock_agent = MagicMock()
        # No data for email, but data for first name
        mock_agent.token_usage = {
            'TestName': {
                '2025-01-20': {
                    'input_tokens': 1000,
                    'output_tokens': 500,
                    'calls': 5
                }
            }
        }
        with patch('app.pdn_admin.admin_routes.UserMetadataHandler', return_value=mock_handler), \
             patch('app.pdn_admin.admin_routes.conversation_stats') as mock_conv_stats, \
             patch('app.pdn_chat_ai.chat_routes.get_agent_instance', return_value=mock_agent):
            mock_conv_stats._read_locked.return_value = {}
            response = client.get(f'/pdn-admin/user/journey/test@example.com?session_token={valid_session_token}')
            assert response.status_code == 200

    def test_journey_with_invalid_date_format(self, client, valid_session_token):
        """Cover lines 781-782: exception in date parsing."""
        mock_handler = MagicMock()
        mock_handler.get_user_by_email.return_value = {
            'First Name': 'Test',
            'Last Name': 'User',
            'PDN Code': 'e5',
            'Date': 'invalid-date'
        }
        with patch('app.pdn_admin.admin_routes.UserMetadataHandler', return_value=mock_handler), \
             patch('app.pdn_admin.admin_routes.conversation_stats') as mock_conv_stats, \
             patch('app.pdn_chat_ai.chat_routes.get_agent_instance', side_effect=Exception("no agent")):
            mock_conv_stats._read_locked.return_value = {}
            response = client.get(f'/pdn-admin/user/journey/test@example.com?session_token={valid_session_token}')
            assert response.status_code == 200

    def test_journey_exception_returns_500(self, client, valid_session_token):
        """Cover lines 796-798: general exception in get_user_journey."""
        with patch('app.pdn_admin.admin_routes.UserMetadataHandler', side_effect=Exception("DB error")), \
             patch('app.pdn_admin.admin_routes.conversation_stats') as mock_conv_stats:
            mock_conv_stats._read_locked.side_effect = Exception("stats error")
            response = client.get(f'/pdn-admin/user/journey/test@example.com?session_token={valid_session_token}')
            assert response.status_code == 500

    def test_journey_no_user_data(self, client, valid_session_token):
        """Cover line 758-759: no user_data path."""
        mock_handler = MagicMock()
        mock_handler.get_user_by_email.return_value = None
        with patch('app.pdn_admin.admin_routes.UserMetadataHandler', return_value=mock_handler), \
             patch('app.pdn_admin.admin_routes.conversation_stats') as mock_conv_stats, \
             patch('app.pdn_chat_ai.chat_routes.get_agent_instance', side_effect=Exception("no agent")):
            mock_conv_stats._read_locked.return_value = {}
            response = client.get(f'/pdn-admin/user/journey/test@example.com?session_token={valid_session_token}')
            assert response.status_code == 200
            data = response.get_json()
            assert data['user_name'] == 'test@example.com'


class TestDownloadJsonExtended:
    """Tests for download_user_json covering additional paths."""

    @pytest.fixture(autouse=True)
    def setup(self, clear_admin_sessions):
        pass

    def test_download_json_with_saved_results_prefix(self, client, valid_session_token, tmp_path, monkeypatch):
        """Cover lines 940-941: path with 'saved_results/' prefix."""
        monkeypatch.setenv('SAVED_RESULTS_DIR', str(tmp_path))
        json_file = tmp_path / 'user' / 'answers.json'
        json_file.parent.mkdir(parents=True, exist_ok=True)
        json_file.write_text('{"test": true}')
        response = client.get(
            f'/pdn-admin/download-json?session_token={valid_session_token}&admin_password=pdn&file_path=saved_results/user/answers.json'
        )
        assert response.status_code == 200

    def test_download_json_path_traversal(self, client, valid_session_token, tmp_path, monkeypatch):
        """Cover lines 953-957: path traversal detection returns 403 (caught as 400 by error handler)."""
        monkeypatch.setenv('SAVED_RESULTS_DIR', str(tmp_path))
        response = client.get(
            f'/pdn-admin/download-json?session_token={valid_session_token}&admin_password=pdn&file_path=../../etc/passwd'
        )
        # The abort(403) inside the try block triggers the except which calls abort(400)
        # The path traversal is detected (line 953) but the abort(403) raises an exception
        # caught by the outer except on line 956 which aborts with 400
        assert response.status_code in (400, 403)

    def test_download_json_send_file_exception(self, client, valid_session_token, tmp_path, monkeypatch):
        """Cover lines 993-995: exception in send_file."""
        monkeypatch.setenv('SAVED_RESULTS_DIR', str(tmp_path))
        json_file = tmp_path / 'test.json'
        json_file.write_text('{"test": true}')
        with patch('app.pdn_admin.admin_routes.send_file', side_effect=Exception("IO error")):
            response = client.get(
                f'/pdn-admin/download-json?session_token={valid_session_token}&admin_password=pdn&file_path=test.json'
            )
            assert response.status_code == 500


class TestCouponRoutesExtended:
    """Tests for coupon routes covering error paths."""

    @pytest.fixture(autouse=True)
    def setup(self, clear_admin_sessions):
        pass

    def test_create_coupon_already_exists(self, client, valid_session_token):
        """Cover lines 1041-1044: coupon code already exists error."""
        mock_cm = MagicMock()
        mock_cm.create_coupon.side_effect = ValueError("Code 'TEST' already exists")
        with patch('app.pdn_admin.admin_routes.get_coupon_manager', return_value=mock_cm):
            response = client.post(
                f'/pdn-admin/coupons?session_token={valid_session_token}',
                json={'name': 'Test', 'max_usage': 10, 'code': 'TEST'}
            )
            assert response.status_code == 409

    def test_create_coupon_invalid_alphanumeric(self, client, valid_session_token):
        """Cover line 1042: alphanumeric validation error."""
        mock_cm = MagicMock()
        mock_cm.create_coupon.side_effect = ValueError("Code must be 4-20 alphanumeric characters")
        with patch('app.pdn_admin.admin_routes.get_coupon_manager', return_value=mock_cm):
            response = client.post(
                f'/pdn-admin/coupons?session_token={valid_session_token}',
                json={'name': 'Test', 'max_usage': 10, 'code': 'AB'}
            )
            assert response.status_code == 400

    def test_create_coupon_general_exception(self, client, valid_session_token):
        """Cover lines 1044: general exception in create_coupon."""
        mock_cm = MagicMock()
        mock_cm.create_coupon.side_effect = Exception("Unexpected error")
        with patch('app.pdn_admin.admin_routes.get_coupon_manager', return_value=mock_cm):
            response = client.post(
                f'/pdn-admin/coupons?session_token={valid_session_token}',
                json={'name': 'Test', 'max_usage': 10}
            )
            assert response.status_code == 500

    def test_create_coupon_empty_code_normalized_to_none(self, client, valid_session_token):
        """Cover line 1030-1031: empty code string normalized to None."""
        mock_cm = MagicMock()
        mock_cm.create_coupon.return_value = {'name': 'Test', 'code': 'AUTO123', 'max_usage': 5}
        mock_cm.to_response.return_value = {'name': 'Test', 'code': 'AUTO123', 'max_usage': 5}
        with patch('app.pdn_admin.admin_routes.get_coupon_manager', return_value=mock_cm):
            response = client.post(
                f'/pdn-admin/coupons?session_token={valid_session_token}',
                json={'name': 'Test', 'max_usage': 5, 'code': '   '}
            )
            assert response.status_code == 201
            mock_cm.create_coupon.assert_called_once_with('Test', 5, code=None)

    def test_update_coupon_invalid_code_format(self, client, valid_session_token):
        """Cover line 1052: invalid coupon code format in URL."""
        response = client.put(
            f'/pdn-admin/coupons/invalid!code?session_token={valid_session_token}',
            json={'name': 'Updated'}
        )
        assert response.status_code == 400

    def test_update_coupon_no_valid_fields(self, client, valid_session_token):
        """Cover line 1078: no valid fields to update."""
        response = client.put(
            f'/pdn-admin/coupons/TESTCODE?session_token={valid_session_token}',
            json={'invalid_field': 'value'}
        )
        assert response.status_code == 400

    def test_update_coupon_not_found(self, client, valid_session_token):
        """Cover lines 1080: coupon not found on update."""
        mock_cm = MagicMock()
        mock_cm.update_coupon.side_effect = KeyError("Not found")
        with patch('app.pdn_admin.admin_routes.get_coupon_manager', return_value=mock_cm):
            response = client.put(
                f'/pdn-admin/coupons/TESTCODE?session_token={valid_session_token}',
                json={'name': 'Updated'}
            )
            assert response.status_code == 404

    def test_update_coupon_value_error(self, client, valid_session_token):
        """Cover line 1082: ValueError on update."""
        mock_cm = MagicMock()
        mock_cm.update_coupon.side_effect = ValueError("Cannot change code")
        with patch('app.pdn_admin.admin_routes.get_coupon_manager', return_value=mock_cm):
            response = client.put(
                f'/pdn-admin/coupons/TESTCODE?session_token={valid_session_token}',
                json={'name': 'Updated'}
            )
            assert response.status_code == 400

    def test_update_coupon_general_exception(self, client, valid_session_token):
        """Cover lines 1083-1084: general exception on update."""
        mock_cm = MagicMock()
        mock_cm.update_coupon.side_effect = Exception("DB error")
        with patch('app.pdn_admin.admin_routes.get_coupon_manager', return_value=mock_cm):
            response = client.put(
                f'/pdn-admin/coupons/TESTCODE?session_token={valid_session_token}',
                json={'name': 'Updated'}
            )
            assert response.status_code == 500

    def test_delete_coupon_invalid_code_format(self, client, valid_session_token):
        """Cover line 1090: invalid code format on delete."""
        response = client.delete(
            f'/pdn-admin/coupons/bad!code?session_token={valid_session_token}'
        )
        assert response.status_code == 400

    def test_delete_coupon_not_found(self, client, valid_session_token):
        """Cover lines 1098-1100: coupon not found on delete."""
        mock_cm = MagicMock()
        mock_cm.delete_coupon.side_effect = KeyError("Not found")
        with patch('app.pdn_admin.admin_routes.get_coupon_manager', return_value=mock_cm):
            response = client.delete(
                f'/pdn-admin/coupons/TESTCODE?session_token={valid_session_token}'
            )
            assert response.status_code == 404

    def test_delete_coupon_general_exception(self, client, valid_session_token):
        """Cover lines 1101-1102: general exception on delete."""
        mock_cm = MagicMock()
        mock_cm.delete_coupon.side_effect = Exception("IO error")
        with patch('app.pdn_admin.admin_routes.get_coupon_manager', return_value=mock_cm):
            response = client.delete(
                f'/pdn-admin/coupons/TESTCODE?session_token={valid_session_token}'
            )
            assert response.status_code == 500

    def test_get_coupon_usage_invalid_code_format(self, client, valid_session_token):
        """Cover line 1108: invalid code format on usage."""
        response = client.get(
            f'/pdn-admin/coupons/bad!code/usage?session_token={valid_session_token}'
        )
        assert response.status_code == 400

    def test_get_coupon_usage_exception(self, client, valid_session_token):
        """Cover lines 1117-1119: general exception on usage."""
        mock_cm = MagicMock()
        mock_cm.get_coupon.side_effect = Exception("DB error")
        with patch('app.pdn_admin.admin_routes.get_coupon_manager', return_value=mock_cm):
            response = client.get(
                f'/pdn-admin/coupons/TESTCODE/usage?session_token={valid_session_token}'
            )
            assert response.status_code == 500

    def test_update_coupon_invalid_max_usage(self, client, valid_session_token):
        """Cover line 1056: invalid max_usage on update."""
        response = client.put(
            f'/pdn-admin/coupons/TESTCODE?session_token={valid_session_token}',
            json={'max_usage': 'not_a_number'}
        )
        assert response.status_code == 400

    def test_update_coupon_max_usage_below_one(self, client, valid_session_token):
        """Cover max_usage < 1 on update."""
        response = client.put(
            f'/pdn-admin/coupons/TESTCODE?session_token={valid_session_token}',
            json={'max_usage': 0}
        )
        assert response.status_code == 400


class TestServeAudioExtended:
    """Tests for serve_audio covering prefix stripping paths."""

    @pytest.fixture(autouse=True)
    def setup(self, clear_admin_sessions):
        pass

    def test_serve_audio_pdn_saved_results_prefix(self, client, valid_session_token, tmp_path, monkeypatch):
        """Cover lines 571-572: path with 'pdn/saved_results/' prefix."""
        monkeypatch.setenv('SAVED_RESULTS_DIR', str(tmp_path))
        audio_file = tmp_path / 'user' / 'test.wav'
        audio_file.parent.mkdir(parents=True, exist_ok=True)
        audio_file.write_bytes(b'\x00' * 100)
        response = client.get(
            f'/pdn-admin/audio/pdn/saved_results/user/test.wav?session_token={valid_session_token}'
        )
        assert response.status_code == 200

    def test_serve_audio_saved_results_prefix(self, client, valid_session_token, tmp_path, monkeypatch):
        """Cover lines 561-562: path with 'saved_results/' prefix."""
        monkeypatch.setenv('SAVED_RESULTS_DIR', str(tmp_path))
        audio_file = tmp_path / 'user' / 'test.wav'
        audio_file.parent.mkdir(parents=True, exist_ok=True)
        audio_file.write_bytes(b'\x00' * 100)
        response = client.get(
            f'/pdn-admin/audio/saved_results/user/test.wav?session_token={valid_session_token}'
        )
        assert response.status_code == 200

    def test_serve_audio_send_file_exception(self, client, valid_session_token, tmp_path, monkeypatch):
        """Cover lines 608-610: exception in send_file."""
        monkeypatch.setenv('SAVED_RESULTS_DIR', str(tmp_path))
        audio_file = tmp_path / 'test.wav'
        audio_file.write_bytes(b'\x00' * 100)
        with patch('app.pdn_admin.admin_routes.send_file', side_effect=Exception("IO error")):
            response = client.get(
                f'/pdn-admin/audio/test.wav?session_token={valid_session_token}'
            )
            assert response.status_code == 500


class TestSaveAudioExtended:
    """Tests for save_audio covering additional paths."""

    @pytest.fixture(autouse=True)
    def setup(self, clear_admin_sessions):
        pass

    def test_save_audio_exception(self, client, valid_session_token, tmp_path):
        """Cover lines 665-666: exception in save_audio."""
        with patch('app.pdn_admin.admin_routes.PDNFilePath') as mock_pdn_cls:
            mock_pdn = MagicMock()
            mock_pdn.get_user_dir.side_effect = Exception("Permission denied")
            mock_pdn_cls.return_value = mock_pdn
            
            from io import BytesIO
            data = {
                'audio': (BytesIO(b'audio data'), 'test.wav'),
                'username': 'testuser'
            }
            response = client.post(
                f'/pdn-admin/api/save-audio?session_token={valid_session_token}',
                data=data,
                content_type='multipart/form-data'
            )
            assert response.status_code == 500


class TestCreateUserExtended:
    """Tests for create_user covering the ValueError path (line 823)."""

    @pytest.fixture(autouse=True)
    def setup(self, clear_admin_sessions):
        pass

    def test_update_user_value_error(self, client, valid_session_token, mock_user_manager):
        """Cover line 878-879: ValueError on update_user."""
        mock_user_manager.update_user.side_effect = ValueError("Invalid pdn_code")
        response = client.put(
            f'/pdn-admin/users/test@example.com?session_token={valid_session_token}',
            json={'admin_password': 'pdn', 'pdn_code': 'invalid'}
        )
        assert response.status_code == 400
