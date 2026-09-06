"""Tests for coupon invite email functionality.

Tests the send_coupon_invite_email utility and the admin API route.
"""

import pytest
from unittest.mock import patch, MagicMock
from flask import Flask

from app.pdn_admin.admin_routes import pdn_admin_bp, admin_sessions, create_session, _metadata_cache
from app.utils.email_sender import send_coupon_invite_email


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
    """Create a minimal Flask test app."""
    application = Flask(__name__)
    application.config['TESTING'] = True
    application.config['SECRET_KEY'] = 'test-secret-key'
    application.config['ADMIN_PASSWORD'] = 'pdn'
    application.register_blueprint(pdn_admin_bp, url_prefix='/pdn-admin')
    return application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def valid_session_token():
    return create_session('admin@test.com')


@pytest.fixture
def mock_coupon_manager():
    with patch('app.pdn_admin.admin_routes.get_coupon_manager') as mock_get_cm:
        cm = MagicMock()
        def _to_response(coupon):
            result = dict(coupon)
            result["status"] = cm.get_status(coupon)
            return result
        cm.to_response.side_effect = _to_response
        mock_get_cm.return_value = cm
        yield cm


class TestSendCouponInviteEmail:
    """Tests for the send_coupon_invite_email utility function."""

    @patch('app.utils.email_sender.send_email_via_smtp')
    def test_sends_email_with_correct_content(self, mock_smtp):
        """Email contains coupon code and login link."""
        mock_smtp.return_value = True

        result = send_coupon_invite_email("user@test.com", "ABCD1234", "https://example.com")

        assert result is True
        mock_smtp.assert_called_once()
        msg = mock_smtp.call_args[0][0]
        assert msg['To'] == 'user@test.com'
        assert 'ABCD1234' in msg['Subject']
        # Check HTML body contains the coupon code and link
        html_part = msg.get_payload()[0].get_payload(decode=True).decode('utf-8')
        assert 'ABCD1234' in html_part
        assert 'https://example.com/pdn-diagnose/' in html_part

    @patch('app.utils.email_sender.send_email_via_smtp')
    def test_returns_false_on_smtp_failure(self, mock_smtp):
        """Returns False when SMTP fails."""
        mock_smtp.return_value = False

        result = send_coupon_invite_email("user@test.com", "CODE1234")

        assert result is False

    def test_returns_false_for_empty_email(self):
        """Returns False when email is empty."""
        result = send_coupon_invite_email("", "CODE1234")
        assert result is False

    @patch('app.utils.email_sender.send_email_via_smtp')
    def test_uses_default_base_url(self, mock_smtp):
        """Uses default Render URL when base_url not specified."""
        mock_smtp.return_value = True

        result = send_coupon_invite_email("user@test.com", "TEST0001")

        assert result is True
        msg = mock_smtp.call_args[0][0]
        html_part = msg.get_payload()[0].get_payload(decode=True).decode('utf-8')
        assert 'https://pdn-chat.onrender.com/pdn-diagnose/' in html_part


class TestSendCouponInviteRoute:
    """Tests for POST /pdn-admin/coupons/<code>/send-invite."""

    @patch('app.pdn_admin.admin_routes.send_coupon_invite_email')
    def test_send_invite_success(self, mock_send, client, valid_session_token, mock_coupon_manager):
        """Sending invite with valid coupon and email succeeds."""
        mock_coupon_manager.get_coupon.return_value = {"code": "ABCD1234", "name": "Test"}
        mock_send.return_value = True

        response = client.post(
            f'/pdn-admin/coupons/ABCD1234/send-invite?session_token={valid_session_token}',
            json={'email': 'recipient@test.com'}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'recipient@test.com' in data['message']
        mock_send.assert_called_once_with('recipient@test.com', 'ABCD1234', 'http://localhost')

    @patch('app.pdn_admin.admin_routes.send_coupon_invite_email')
    def test_send_invite_coupon_not_found(self, mock_send, client, valid_session_token, mock_coupon_manager):
        """Sending invite for non-existent coupon returns 404."""
        mock_coupon_manager.get_coupon.return_value = None

        response = client.post(
            f'/pdn-admin/coupons/NOTFOUND/send-invite?session_token={valid_session_token}',
            json={'email': 'user@test.com'}
        )
        assert response.status_code == 404
        assert 'Coupon not found' in response.get_json()['error']
        mock_send.assert_not_called()

    def test_send_invite_missing_email(self, client, valid_session_token, mock_coupon_manager):
        """Sending invite without email returns 400."""
        mock_coupon_manager.get_coupon.return_value = {"code": "ABCD1234", "name": "Test"}
        response = client.post(
            f'/pdn-admin/coupons/ABCD1234/send-invite?session_token={valid_session_token}',
            json={'email': ''}
        )
        assert response.status_code == 400
        assert 'email' in response.get_json()['error'].lower()

    def test_send_invite_invalid_email(self, client, valid_session_token, mock_coupon_manager):
        """Sending invite with invalid email returns 400."""
        response = client.post(
            f'/pdn-admin/coupons/ABCD1234/send-invite?session_token={valid_session_token}',
            json={'email': 'not-an-email'}
        )
        assert response.status_code == 400

    def test_send_invite_no_data(self, client, valid_session_token, mock_coupon_manager):
        """Sending invite with no JSON body returns 400."""
        response = client.post(
            f'/pdn-admin/coupons/ABCD1234/send-invite?session_token={valid_session_token}',
            content_type='application/json',
            data=''
        )
        assert response.status_code == 400

    def test_send_invite_unauthorized(self, client):
        """Sending invite without session returns 401."""
        response = client.post(
            '/pdn-admin/coupons/ABCD1234/send-invite',
            json={'email': 'user@test.com'}
        )
        assert response.status_code == 401

    @patch('app.pdn_admin.admin_routes.send_coupon_invite_email')
    def test_send_invite_smtp_failure(self, mock_send, client, valid_session_token, mock_coupon_manager):
        """Returns 500 when email sending fails."""
        mock_coupon_manager.get_coupon.return_value = {"code": "ABCD1234", "name": "Test"}
        mock_send.return_value = False

        response = client.post(
            f'/pdn-admin/coupons/ABCD1234/send-invite?session_token={valid_session_token}',
            json={'email': 'user@test.com'}
        )
        assert response.status_code == 500
        assert 'Failed to send email' in response.get_json()['error']

    @patch('app.pdn_admin.admin_routes.send_coupon_invite_email')
    def test_send_invite_email_lowercased(self, mock_send, client, valid_session_token, mock_coupon_manager):
        """Email is normalized to lowercase."""
        mock_coupon_manager.get_coupon.return_value = {"code": "ABCD1234", "name": "Test"}
        mock_send.return_value = True

        response = client.post(
            f'/pdn-admin/coupons/ABCD1234/send-invite?session_token={valid_session_token}',
            json={'email': 'User@Test.COM'}
        )
        assert response.status_code == 200
        mock_send.assert_called_once_with('user@test.com', 'ABCD1234', 'http://localhost')
