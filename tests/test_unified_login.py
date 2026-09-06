"""Tests for the unified diagnose login endpoint.

The login accepts a single 'password' field that auto-detects:
- If it matches a valid coupon code → coupon login
- Otherwise → password login (email local part before @)
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from flask import Flask

from app.pdn_diagnose.diagnosis_routes import pdn_diagnose_bp


@pytest.fixture
def app():
    """Create a minimal Flask test app with the diagnose blueprint."""
    application = Flask(__name__)
    application.config['TESTING'] = True
    application.config['SECRET_KEY'] = 'test-secret'
    application.config['SESSION_TYPE'] = 'filesystem'
    application.config['QUESTIONS_FILE'] = {}

    # Initialize Flask-Session
    from flask_session import Session
    Session(application)

    application.register_blueprint(pdn_diagnose_bp, url_prefix='/pdn-diagnose')
    return application


@pytest.fixture
def client(app):
    """Create Flask test client."""
    return app.test_client()


@pytest.fixture
def mock_coupon_manager():
    """Mock the coupon manager for login tests."""
    with patch('app.pdn_diagnose.diagnosis_routes.get_coupon_manager') as mock_get_cm:
        cm = MagicMock()
        mock_get_cm.return_value = cm
        yield cm


class TestUnifiedLogin:
    """Tests for the unified login endpoint."""

    def test_password_login_success(self, client, mock_coupon_manager):
        """Login with email prefix as password succeeds."""
        # validate_and_redeem returns failure (not a coupon)
        mock_coupon_manager.validate_and_redeem.return_value = (False, "Invalid coupon code", None)

        response = client.post('/pdn-diagnose/login', json={
            'email': 'john@example.com',
            'password': 'john'
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['message'] == 'Login successful'

    def test_password_login_wrong_password(self, client, mock_coupon_manager):
        """Login with wrong password returns 401."""
        mock_coupon_manager.validate_and_redeem.return_value = (False, "Invalid coupon code", None)

        response = client.post('/pdn-diagnose/login', json={
            'email': 'john@example.com',
            'password': 'wrongpass'
        })
        assert response.status_code == 401
        data = response.get_json()
        assert 'Invalid credentials' in data['error']

    def test_coupon_login_success(self, client, mock_coupon_manager):
        """Login with valid coupon code succeeds."""
        mock_coupon_manager.validate_and_redeem.return_value = (True, "Valid", {"code": "ABCD1234"})

        response = client.post('/pdn-diagnose/login', json={
            'email': 'user@example.com',
            'password': 'ABCD1234'
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['message'] == 'Login successful'

        # Verify coupon was validated with uppercase
        mock_coupon_manager.validate_and_redeem.assert_called_with('ABCD1234', 'user@example.com')

    def test_coupon_login_case_insensitive(self, client, mock_coupon_manager):
        """Coupon codes are uppercased before validation."""
        mock_coupon_manager.validate_and_redeem.return_value = (True, "Valid", {"code": "ABCD1234"})

        response = client.post('/pdn-diagnose/login', json={
            'email': 'user@example.com',
            'password': 'abcd1234'
        })
        assert response.status_code == 200
        mock_coupon_manager.validate_and_redeem.assert_called_with('ABCD1234', 'user@example.com')

    def test_coupon_login_full_returns_403(self, client, mock_coupon_manager):
        """Login with full coupon returns 403."""
        mock_coupon_manager.validate_and_redeem.return_value = (
            False, "Coupon has reached its usage limit", None
        )

        response = client.post('/pdn-diagnose/login', json={
            'email': 'user@example.com',
            'password': 'FULLCODE'
        })
        assert response.status_code == 403
        data = response.get_json()
        assert 'usage limit' in data['error']

    def test_missing_email_returns_400(self, client, mock_coupon_manager):
        """Login without email returns 400."""
        response = client.post('/pdn-diagnose/login', json={
            'password': 'something'
        })
        assert response.status_code == 400
        data = response.get_json()
        assert 'Email is required' in data['error']

    def test_missing_password_returns_400(self, client, mock_coupon_manager):
        """Login without password/coupon returns 400."""
        response = client.post('/pdn-diagnose/login', json={
            'email': 'user@example.com'
        })
        assert response.status_code == 400
        data = response.get_json()
        assert 'required' in data['error']

    def test_empty_email_returns_400(self, client, mock_coupon_manager):
        """Login with empty email returns 400."""
        response = client.post('/pdn-diagnose/login', json={
            'email': '   ',
            'password': 'test'
        })
        assert response.status_code == 400

    def test_empty_password_returns_400(self, client, mock_coupon_manager):
        """Login with empty password returns 400."""
        response = client.post('/pdn-diagnose/login', json={
            'email': 'user@example.com',
            'password': '   '
        })
        assert response.status_code == 400

    def test_coupon_takes_priority_over_password(self, client, mock_coupon_manager):
        """If credential matches a coupon, coupon login is used even if it also matches password."""
        mock_coupon_manager.validate_and_redeem.return_value = (True, "Valid", {"code": "ABCD1234"})

        response = client.post('/pdn-diagnose/login', json={
            'email': 'ABCD1234@example.com',
            'password': 'ABCD1234'
        })
        assert response.status_code == 200
        # Should have used coupon path
        mock_coupon_manager.validate_and_redeem.assert_called_once()

    def test_same_email_relogin_with_coupon_does_not_increment(self, client, mock_coupon_manager):
        """Re-login with same email and coupon should not increment usage_count."""
        mock_coupon_manager.validate_and_redeem.return_value = (True, "Valid", {
            "code": "ABCD1234", "usage_count": 1, "used_by": ["user@example.com"]
        })

        response = client.post('/pdn-diagnose/login', json={
            'email': 'user@example.com',
            'password': 'ABCD1234'
        })
        assert response.status_code == 200

        # Second login — same email, same coupon
        response = client.post('/pdn-diagnose/login', json={
            'email': 'user@example.com',
            'password': 'ABCD1234'
        })
        assert response.status_code == 200
        _, _, coupon = mock_coupon_manager.validate_and_redeem.return_value
        assert coupon["usage_count"] == 1

    def test_email_is_lowercased(self, client, mock_coupon_manager):
        """Email is normalized to lowercase."""
        mock_coupon_manager.validate_and_redeem.return_value = (False, "Invalid coupon code", None)

        response = client.post('/pdn-diagnose/login', json={
            'email': 'John@Example.COM',
            'password': 'john'
        })
        assert response.status_code == 200


class TestCouponReloginNoIncrement:
    """Tests that re-login with same email+coupon doesn't double-count usage."""

    def test_validate_and_redeem_skips_increment_for_existing_email(self):
        """validate_and_redeem does not increment usage_count if email already in used_by."""
        import tempfile
        import json
        from pathlib import Path
        from app.pdn_admin.coupon_manager import CouponManager

        # Create a temp coupons file with a coupon that already has a user
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({
                "TEST1234": {
                    "name": "Test",
                    "code": "TEST1234",
                    "max_usage": 3,
                    "usage_count": 1,
                    "used_by": ["existing@test.com"],
                    "created_at": "2025-01-01 00:00",
                    "updated_at": "2025-01-01 00:00"
                }
            }, f)
            tmp_path = Path(f.name)

        try:
            cm = CouponManager(json_path=tmp_path)

            # Re-login with same email — should NOT increment
            success, msg, coupon = cm.validate_and_redeem("TEST1234", "existing@test.com")
            assert success is True
            assert coupon["usage_count"] == 1  # Not incremented
            assert coupon["used_by"] == ["existing@test.com"]

            # New email — SHOULD increment
            success, msg, coupon = cm.validate_and_redeem("TEST1234", "new@test.com")
            assert success is True
            assert coupon["usage_count"] == 2
            assert "new@test.com" in coupon["used_by"]

            # Re-login with new email again — should NOT increment
            success, msg, coupon = cm.validate_and_redeem("TEST1234", "new@test.com")
            assert success is True
            assert coupon["usage_count"] == 2  # Still 2
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_redeem_coupon_skips_increment_for_existing_email(self):
        """redeem_coupon does not increment usage_count if email already in used_by."""
        import tempfile
        import json
        from pathlib import Path
        from app.pdn_admin.coupon_manager import CouponManager

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({
                "CODE5678": {
                    "name": "Test2",
                    "code": "CODE5678",
                    "max_usage": 2,
                    "usage_count": 1,
                    "used_by": ["user1@test.com"],
                    "created_at": "2025-01-01 00:00",
                    "updated_at": "2025-01-01 00:00"
                }
            }, f)
            tmp_path = Path(f.name)

        try:
            cm = CouponManager(json_path=tmp_path)

            # Re-login — should not increment
            coupon = cm.redeem_coupon("CODE5678", "user1@test.com")
            assert coupon["usage_count"] == 1

            # New user — should increment
            coupon = cm.redeem_coupon("CODE5678", "user2@test.com")
            assert coupon["usage_count"] == 2
            assert "user2@test.com" in coupon["used_by"]

            # Coupon is now full (2/2) — new user should fail
            try:
                cm.redeem_coupon("CODE5678", "user3@test.com")
                assert False, "Should have raised ValueError"
            except ValueError as e:
                assert "usage limit" in str(e)

            # But existing user can still re-login
            coupon = cm.redeem_coupon("CODE5678", "user1@test.com")
            assert coupon["usage_count"] == 2  # Still 2
        finally:
            tmp_path.unlink(missing_ok=True)
