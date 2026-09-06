"""Unit tests for admin coupon API routes and CouponManager CRUD operations.

Tests CRUD operations on coupons via the admin API endpoints,
including authentication, error handling, and response formats.
Also tests CouponManager directly with mocked file I/O.

Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 4.1
"""

import pytest
from unittest.mock import patch, MagicMock, mock_open
from flask import Flask
from pathlib import Path
import json

from app.pdn_admin.admin_routes import (
    pdn_admin_bp, admin_sessions, create_session, _metadata_cache
)
from app.pdn_admin.coupon_manager import (
    CouponManager, generate_coupon_code, validate_custom_code
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
    return create_session('admin@test.com')


@pytest.fixture
def mock_coupon_manager():
    """Mock the coupon manager singleton."""
    with patch('app.pdn_admin.admin_routes.get_coupon_manager') as mock_get_cm:
        cm = MagicMock()
        # Make to_response behave like the real implementation
        def _to_response(coupon):
            result = dict(coupon)
            result["status"] = cm.get_status(coupon)
            return result
        cm.to_response.side_effect = _to_response
        mock_get_cm.return_value = cm
        yield cm


class TestListCoupons:
    """Tests for GET /pdn-admin/coupons."""

    def test_list_coupons_returns_all_fields(self, client, valid_session_token, mock_coupon_manager):
        """List coupons returns all expected fields including status."""
        mock_coupon_manager.get_all_coupons.return_value = [
            {
                "code": "ABCD1234",
                "name": "Workshop March",
                "max_usage": 50,
                "usage_count": 12,
                "used_by": ["user1@test.com"],
                "created_at": "2025-03-01 10:30",
                "updated_at": "2025-03-15 14:20",
                "status": "active"
            },
            {
                "code": "FULL0001",
                "name": "Full Coupon",
                "max_usage": 1,
                "usage_count": 1,
                "used_by": ["user2@test.com"],
                "created_at": "2025-01-01 09:00",
                "updated_at": "2025-01-02 10:00",
                "status": "full"
            }
        ]

        response = client.get(f'/pdn-admin/coupons?session_token={valid_session_token}')
        assert response.status_code == 200
        data = response.get_json()
        assert 'coupons' in data
        assert len(data['coupons']) == 2

        coupon = data['coupons'][0]
        assert coupon['code'] == 'ABCD1234'
        assert coupon['name'] == 'Workshop March'
        assert coupon['max_usage'] == 50
        assert coupon['usage_count'] == 12
        assert coupon['status'] == 'active'
        assert 'used_by' in coupon
        assert 'created_at' in coupon
        assert 'updated_at' in coupon

    def test_list_coupons_empty(self, client, valid_session_token, mock_coupon_manager):
        """List coupons returns empty list when no coupons exist."""
        mock_coupon_manager.get_all_coupons.return_value = []

        response = client.get(f'/pdn-admin/coupons?session_token={valid_session_token}')
        assert response.status_code == 200
        data = response.get_json()
        assert data['coupons'] == []

    def test_list_coupons_unauthorized(self, client):
        """List coupons without session token returns 401."""
        response = client.get('/pdn-admin/coupons')
        assert response.status_code == 401
        data = response.get_json()
        assert 'error' in data


class TestCreateCoupon:
    """Tests for POST /pdn-admin/coupons."""

    def test_create_coupon_without_custom_code(self, client, valid_session_token, mock_coupon_manager):
        """Create coupon without custom code auto-generates one."""
        mock_coupon_manager.create_coupon.return_value = {
            "code": "AUTO1234",
            "name": "New Coupon",
            "max_usage": 10,
            "usage_count": 0,
            "used_by": [],
            "created_at": "2025-06-01 12:00",
            "updated_at": "2025-06-01 12:00"
        }
        mock_coupon_manager.get_status.return_value = "active"

        response = client.post(
            f'/pdn-admin/coupons?session_token={valid_session_token}',
            json={'name': 'New Coupon', 'max_usage': 10}
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data['success'] is True
        assert data['coupon']['code'] == 'AUTO1234'
        assert data['coupon']['name'] == 'New Coupon'
        assert data['coupon']['max_usage'] == 10
        assert data['coupon']['usage_count'] == 0
        assert data['coupon']['status'] == 'active'

        # Verify create_coupon was called without code
        mock_coupon_manager.create_coupon.assert_called_once_with('New Coupon', 10, code=None)

    def test_create_coupon_with_custom_code(self, client, valid_session_token, mock_coupon_manager):
        """Create coupon with custom code uses the provided code."""
        mock_coupon_manager.create_coupon.return_value = {
            "code": "MYCODE01",
            "name": "Custom Coupon",
            "max_usage": 5,
            "usage_count": 0,
            "used_by": [],
            "created_at": "2025-06-01 12:00",
            "updated_at": "2025-06-01 12:00"
        }
        mock_coupon_manager.get_status.return_value = "active"

        response = client.post(
            f'/pdn-admin/coupons?session_token={valid_session_token}',
            json={'name': 'Custom Coupon', 'max_usage': 5, 'code': 'MYCODE01'}
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data['success'] is True
        assert data['coupon']['code'] == 'MYCODE01'

        # Verify create_coupon was called with the custom code
        mock_coupon_manager.create_coupon.assert_called_once_with('Custom Coupon', 5, code='MYCODE01')

    def test_create_coupon_duplicate_code_returns_409(self, client, valid_session_token, mock_coupon_manager):
        """Create coupon with duplicate code returns 409 Conflict."""
        mock_coupon_manager.create_coupon.side_effect = ValueError("Coupon code already exists")

        response = client.post(
            f'/pdn-admin/coupons?session_token={valid_session_token}',
            json={'name': 'Dup Coupon', 'max_usage': 10, 'code': 'EXISTING'}
        )
        assert response.status_code == 409
        data = response.get_json()
        assert 'already exists' in data['error']

    def test_create_coupon_invalid_custom_code_returns_400(self, client, valid_session_token, mock_coupon_manager):
        """Create coupon with invalid custom code returns 400."""
        mock_coupon_manager.create_coupon.side_effect = ValueError(
            "Code must be 4-20 alphanumeric characters"
        )

        response = client.post(
            f'/pdn-admin/coupons?session_token={valid_session_token}',
            json={'name': 'Bad Code', 'max_usage': 10, 'code': 'ab'}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'alphanumeric' in data['error']

    def test_create_coupon_missing_name_returns_400(self, client, valid_session_token, mock_coupon_manager):
        """Create coupon without name returns 400."""
        response = client.post(
            f'/pdn-admin/coupons?session_token={valid_session_token}',
            json={'max_usage': 10}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'Name is required' in data['error']

    def test_create_coupon_missing_max_usage_returns_400(self, client, valid_session_token, mock_coupon_manager):
        """Create coupon without max_usage returns 400."""
        response = client.post(
            f'/pdn-admin/coupons?session_token={valid_session_token}',
            json={'name': 'No Max'}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'max_usage is required' in data['error']

    def test_create_coupon_invalid_max_usage_returns_400(self, client, valid_session_token, mock_coupon_manager):
        """Create coupon with max_usage < 1 returns 400."""
        response = client.post(
            f'/pdn-admin/coupons?session_token={valid_session_token}',
            json={'name': 'Bad Max', 'max_usage': 0}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'Max usage must be at least 1' in data['error']

    def test_create_coupon_non_numeric_max_usage_returns_400(self, client, valid_session_token, mock_coupon_manager):
        """Create coupon with non-numeric max_usage returns 400."""
        response = client.post(
            f'/pdn-admin/coupons?session_token={valid_session_token}',
            json={'name': 'Bad Max', 'max_usage': 'abc'}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'Max usage must be at least 1' in data['error']

    def test_create_coupon_no_data_returns_400(self, client, valid_session_token, mock_coupon_manager):
        """Create coupon with no JSON body returns 400."""
        response = client.post(
            f'/pdn-admin/coupons?session_token={valid_session_token}',
            content_type='application/json',
            data=''
        )
        assert response.status_code == 400

    def test_create_coupon_unauthorized(self, client):
        """Create coupon without session token returns 401."""
        response = client.post(
            '/pdn-admin/coupons',
            json={'name': 'Test', 'max_usage': 10}
        )
        assert response.status_code == 401

    def test_create_coupon_empty_code_treated_as_none(self, client, valid_session_token, mock_coupon_manager):
        """Create coupon with empty string code auto-generates code."""
        mock_coupon_manager.create_coupon.return_value = {
            "code": "GENR1234",
            "name": "Auto Gen",
            "max_usage": 5,
            "usage_count": 0,
            "used_by": [],
            "created_at": "2025-06-01 12:00",
            "updated_at": "2025-06-01 12:00"
        }
        mock_coupon_manager.get_status.return_value = "active"

        response = client.post(
            f'/pdn-admin/coupons?session_token={valid_session_token}',
            json={'name': 'Auto Gen', 'max_usage': 5, 'code': '  '}
        )
        assert response.status_code == 201
        # Empty/whitespace code should be treated as None (auto-generate)
        mock_coupon_manager.create_coupon.assert_called_once_with('Auto Gen', 5, code=None)


class TestUpdateCoupon:
    """Tests for PUT /pdn-admin/coupons/<code>."""

    def test_update_coupon_name(self, client, valid_session_token, mock_coupon_manager):
        """Update coupon name succeeds."""
        mock_coupon_manager.update_coupon.return_value = {
            "code": "ABCD1234",
            "name": "Updated Name",
            "max_usage": 50,
            "usage_count": 12,
            "used_by": [],
            "created_at": "2025-03-01 10:30",
            "updated_at": "2025-06-01 12:00"
        }
        mock_coupon_manager.get_status.return_value = "active"

        response = client.put(
            f'/pdn-admin/coupons/ABCD1234?session_token={valid_session_token}',
            json={'name': 'Updated Name'}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['coupon']['name'] == 'Updated Name'
        assert data['coupon']['status'] == 'active'

    def test_update_coupon_max_usage(self, client, valid_session_token, mock_coupon_manager):
        """Update coupon max_usage succeeds."""
        mock_coupon_manager.update_coupon.return_value = {
            "code": "ABCD1234",
            "name": "Workshop",
            "max_usage": 100,
            "usage_count": 12,
            "used_by": [],
            "created_at": "2025-03-01 10:30",
            "updated_at": "2025-06-01 12:00"
        }
        mock_coupon_manager.get_status.return_value = "active"

        response = client.put(
            f'/pdn-admin/coupons/ABCD1234?session_token={valid_session_token}',
            json={'max_usage': 100}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['coupon']['max_usage'] == 100

    def test_update_coupon_not_found_returns_404(self, client, valid_session_token, mock_coupon_manager):
        """Update non-existent coupon returns 404."""
        mock_coupon_manager.update_coupon.side_effect = KeyError("Coupon not found")

        response = client.put(
            f'/pdn-admin/coupons/NOTFOUND?session_token={valid_session_token}',
            json={'name': 'New Name'}
        )
        assert response.status_code == 404
        data = response.get_json()
        assert 'Coupon not found' in data['error']

    def test_update_coupon_invalid_max_usage_returns_400(self, client, valid_session_token, mock_coupon_manager):
        """Update coupon with max_usage < 1 returns 400."""
        response = client.put(
            f'/pdn-admin/coupons/ABCD1234?session_token={valid_session_token}',
            json={'max_usage': 0}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'Max usage must be at least 1' in data['error']

    def test_update_coupon_non_numeric_max_usage_returns_400(self, client, valid_session_token, mock_coupon_manager):
        """Update coupon with non-numeric max_usage returns 400."""
        response = client.put(
            f'/pdn-admin/coupons/ABCD1234?session_token={valid_session_token}',
            json={'max_usage': 'abc'}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'Max usage must be at least 1' in data['error']

    def test_update_coupon_no_valid_fields_returns_400(self, client, valid_session_token, mock_coupon_manager):
        """Update coupon with no valid fields returns 400."""
        response = client.put(
            f'/pdn-admin/coupons/ABCD1234?session_token={valid_session_token}',
            json={'invalid_field': 'value'}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'No valid fields to update' in data['error']

    def test_update_coupon_no_data_returns_400(self, client, valid_session_token, mock_coupon_manager):
        """Update coupon with no JSON body returns 400."""
        response = client.put(
            f'/pdn-admin/coupons/ABCD1234?session_token={valid_session_token}',
            content_type='application/json',
            data=''
        )
        assert response.status_code == 400

    def test_update_coupon_unauthorized(self, client):
        """Update coupon without session token returns 401."""
        response = client.put(
            '/pdn-admin/coupons/ABCD1234',
            json={'name': 'Updated'}
        )
        assert response.status_code == 401


class TestDeleteCoupon:
    """Tests for DELETE /pdn-admin/coupons/<code>."""

    def test_delete_coupon_success(self, client, valid_session_token, mock_coupon_manager):
        """Delete existing coupon succeeds."""
        mock_coupon_manager.delete_coupon.return_value = None

        response = client.delete(
            f'/pdn-admin/coupons/ABCD1234?session_token={valid_session_token}'
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'ABCD1234' in data['message']

        mock_coupon_manager.delete_coupon.assert_called_once_with('ABCD1234')

    def test_delete_coupon_not_found_returns_404(self, client, valid_session_token, mock_coupon_manager):
        """Delete non-existent coupon returns 404."""
        mock_coupon_manager.delete_coupon.side_effect = KeyError("Coupon not found")

        response = client.delete(
            f'/pdn-admin/coupons/NOTFOUND?session_token={valid_session_token}'
        )
        assert response.status_code == 404
        data = response.get_json()
        assert 'Coupon not found' in data['error']

    def test_delete_coupon_unauthorized(self, client):
        """Delete coupon without session token returns 401."""
        response = client.delete('/pdn-admin/coupons/ABCD1234')
        assert response.status_code == 401


class TestGetCouponUsage:
    """Tests for GET /pdn-admin/coupons/<code>/usage."""

    def test_get_coupon_usage_success(self, client, valid_session_token, mock_coupon_manager):
        """Get usage details returns used_by list and status."""
        mock_coupon_manager.get_coupon.return_value = {
            "code": "ABCD1234",
            "name": "Workshop",
            "max_usage": 50,
            "usage_count": 2,
            "used_by": ["user1@test.com", "user2@test.com"],
            "created_at": "2025-03-01 10:30",
            "updated_at": "2025-03-15 14:20"
        }
        mock_coupon_manager.get_status.return_value = "active"

        response = client.get(
            f'/pdn-admin/coupons/ABCD1234/usage?session_token={valid_session_token}'
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data['code'] == 'ABCD1234'
        assert data['name'] == 'Workshop'
        assert data['usage_count'] == 2
        assert data['max_usage'] == 50
        assert data['used_by'] == ['user1@test.com', 'user2@test.com']
        assert data['status'] == 'active'

    def test_get_coupon_usage_not_found_returns_404(self, client, valid_session_token, mock_coupon_manager):
        """Get usage for non-existent coupon returns 404."""
        mock_coupon_manager.get_coupon.return_value = None

        response = client.get(
            f'/pdn-admin/coupons/NOTFOUND/usage?session_token={valid_session_token}'
        )
        assert response.status_code == 404
        data = response.get_json()
        assert 'Coupon not found' in data['error']

    def test_get_coupon_usage_unauthorized(self, client):
        """Get usage without session token returns 401."""
        response = client.get('/pdn-admin/coupons/ABCD1234/usage')
        assert response.status_code == 401


class TestUnauthorizedAccess:
    """Tests that all coupon endpoints require authentication."""

    def test_list_coupons_no_token(self, client):
        """GET /coupons without token returns 401."""
        response = client.get('/pdn-admin/coupons')
        assert response.status_code == 401

    def test_list_coupons_invalid_token(self, client):
        """GET /coupons with invalid token returns 401."""
        response = client.get('/pdn-admin/coupons?session_token=invalid-token-xyz')
        assert response.status_code == 401

    def test_create_coupon_no_token(self, client):
        """POST /coupons without token returns 401."""
        response = client.post('/pdn-admin/coupons', json={'name': 'Test', 'max_usage': 10})
        assert response.status_code == 401

    def test_update_coupon_no_token(self, client):
        """PUT /coupons/<code> without token returns 401."""
        response = client.put('/pdn-admin/coupons/CODE1234', json={'name': 'Updated'})
        assert response.status_code == 401

    def test_delete_coupon_no_token(self, client):
        """DELETE /coupons/<code> without token returns 401."""
        response = client.delete('/pdn-admin/coupons/CODE1234')
        assert response.status_code == 401

    def test_get_usage_no_token(self, client):
        """GET /coupons/<code>/usage without token returns 401."""
        response = client.get('/pdn-admin/coupons/CODE1234/usage')
        assert response.status_code == 401



# =============================================================================
# CouponManager Direct Unit Tests (mocked file I/O)
# Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7
# =============================================================================


@pytest.fixture
def coupon_manager():
    """Create a CouponManager with mocked file I/O.

    Mocks _load_initial_data and _save_to_file so no file system access occurs.
    """
    with patch.object(CouponManager, '_load_initial_data'):
        with patch.object(CouponManager, '_save_to_file'):
            cm = CouponManager(json_path=Path("/fake/coupons.json"))
            cm._coupons = {}
            yield cm


class TestCouponManagerCreate:
    """Tests for CouponManager.create_coupon — Requirement 3.2."""

    def test_create_coupon_auto_generated_code(self, coupon_manager):
        """Create coupon without code auto-generates an 8-char uppercase+digit code."""
        with patch.object(coupon_manager, '_save_to_file'):
            result = coupon_manager.create_coupon("Workshop", max_usage=10)

        assert result["name"] == "Workshop"
        assert result["max_usage"] == 10
        assert result["usage_count"] == 0
        assert result["used_by"] == []
        assert len(result["code"]) == 8
        assert result["code"].isalnum()
        assert result["code"] == result["code"].upper()
        assert "created_at" in result
        assert "updated_at" in result

    def test_create_coupon_custom_code(self, coupon_manager):
        """Create coupon with valid custom code uses the provided code."""
        with patch.object(coupon_manager, '_save_to_file'):
            result = coupon_manager.create_coupon("Custom", max_usage=5, code="MYCODE01")

        assert result["code"] == "MYCODE01"
        assert result["name"] == "Custom"
        assert result["max_usage"] == 5

    def test_create_coupon_duplicate_code_raises_value_error(self, coupon_manager):
        """Create coupon with duplicate code raises ValueError."""
        coupon_manager._coupons["EXISTING1"] = {
            "name": "Existing", "code": "EXISTING1", "max_usage": 10,
            "usage_count": 0, "used_by": [], "created_at": "", "updated_at": ""
        }

        with patch.object(coupon_manager, '_save_to_file'):
            with pytest.raises(ValueError, match="already exists"):
                coupon_manager.create_coupon("Dup", max_usage=5, code="EXISTING1")

    def test_create_coupon_invalid_custom_code_raises_value_error(self, coupon_manager):
        """Create coupon with invalid custom code (too short) raises ValueError."""
        with patch.object(coupon_manager, '_save_to_file'):
            with pytest.raises(ValueError, match="4-20 alphanumeric"):
                coupon_manager.create_coupon("Bad", max_usage=5, code="AB")

    def test_create_coupon_empty_name_raises_value_error(self, coupon_manager):
        """Create coupon with empty name raises ValueError."""
        with patch.object(coupon_manager, '_save_to_file'):
            with pytest.raises(ValueError, match="1-100 characters"):
                coupon_manager.create_coupon("", max_usage=5)

    def test_create_coupon_name_too_long_raises_value_error(self, coupon_manager):
        """Create coupon with name exceeding 100 chars raises ValueError."""
        with patch.object(coupon_manager, '_save_to_file'):
            with pytest.raises(ValueError, match="1-100 characters"):
                coupon_manager.create_coupon("A" * 101, max_usage=5)

    def test_create_coupon_persists_to_internal_store(self, coupon_manager):
        """Create coupon adds it to the internal _coupons dict."""
        with patch.object(coupon_manager, '_save_to_file'):
            result = coupon_manager.create_coupon("Stored", max_usage=3, code="STORE001")

        assert "STORE001" in coupon_manager._coupons
        assert coupon_manager._coupons["STORE001"]["name"] == "Stored"


class TestCouponManagerValidate:
    """Tests for CouponManager.validate_coupon — Requirement 3.3."""

    def test_validate_valid_coupon(self, coupon_manager):
        """Validate coupon with remaining uses returns (True, 'Valid')."""
        coupon_manager._coupons["VALID001"] = {
            "name": "Valid", "code": "VALID001", "max_usage": 10,
            "usage_count": 5, "used_by": [], "created_at": "", "updated_at": ""
        }

        is_valid, message = coupon_manager.validate_coupon("VALID001")
        assert is_valid is True
        assert message == "Valid"

    def test_validate_exhausted_coupon(self, coupon_manager):
        """Validate coupon at max usage returns (False, usage limit message)."""
        coupon_manager._coupons["FULL0001"] = {
            "name": "Full", "code": "FULL0001", "max_usage": 5,
            "usage_count": 5, "used_by": [], "created_at": "", "updated_at": ""
        }

        is_valid, message = coupon_manager.validate_coupon("FULL0001")
        assert is_valid is False
        assert "usage limit" in message

    def test_validate_non_existent_code(self, coupon_manager):
        """Validate non-existent code returns (False, 'Invalid coupon code')."""
        is_valid, message = coupon_manager.validate_coupon("NOSUCHCD")
        assert is_valid is False
        assert message == "Invalid coupon code"

    def test_validate_coupon_over_max_usage(self, coupon_manager):
        """Validate coupon with usage_count > max_usage returns invalid."""
        coupon_manager._coupons["OVER0001"] = {
            "name": "Over", "code": "OVER0001", "max_usage": 3,
            "usage_count": 5, "used_by": [], "created_at": "", "updated_at": ""
        }

        is_valid, message = coupon_manager.validate_coupon("OVER0001")
        assert is_valid is False
        assert "usage limit" in message


class TestCouponManagerValidateAndRedeem:
    """Tests for CouponManager.validate_and_redeem — Requirement 3.4."""

    def test_validate_and_redeem_success(self, coupon_manager):
        """Atomic validate+redeem increments usage_count and adds email to used_by."""
        coupon_manager._coupons["REDEEM01"] = {
            "name": "Redeem", "code": "REDEEM01", "max_usage": 10,
            "usage_count": 2, "used_by": ["prev@test.com"],
            "created_at": "2025-01-01 00:00", "updated_at": "2025-01-01 00:00"
        }

        with patch.object(coupon_manager, '_save_to_file'):
            success, message, coupon = coupon_manager.validate_and_redeem("REDEEM01", "new@test.com")

        assert success is True
        assert message == "Valid"
        assert coupon is not None
        assert coupon["usage_count"] == 3
        assert "new@test.com" in coupon["used_by"]
        assert "prev@test.com" in coupon["used_by"]

    def test_validate_and_redeem_email_deduplication(self, coupon_manager):
        """Redeeming with same email does not increment usage_count."""
        coupon_manager._coupons["DEDUP001"] = {
            "name": "Dedup", "code": "DEDUP001", "max_usage": 10,
            "usage_count": 1, "used_by": ["same@test.com"],
            "created_at": "2025-01-01 00:00", "updated_at": "2025-01-01 00:00"
        }

        with patch.object(coupon_manager, '_save_to_file'):
            success, message, coupon = coupon_manager.validate_and_redeem("DEDUP001", "same@test.com")

        assert success is True
        # Usage count should NOT increment for returning user
        assert coupon["usage_count"] == 1
        # Email should appear only once
        assert coupon["used_by"].count("same@test.com") == 1

    def test_validate_and_redeem_exhausted_coupon(self, coupon_manager):
        """Validate+redeem on exhausted coupon returns failure without modifying state."""
        coupon_manager._coupons["EXHAUST1"] = {
            "name": "Exhausted", "code": "EXHAUST1", "max_usage": 1,
            "usage_count": 1, "used_by": ["first@test.com"],
            "created_at": "2025-01-01 00:00", "updated_at": "2025-01-01 00:00"
        }

        success, message, coupon = coupon_manager.validate_and_redeem("EXHAUST1", "new@test.com")

        assert success is False
        assert "usage limit" in message
        assert coupon is None
        # State should not be modified
        assert coupon_manager._coupons["EXHAUST1"]["usage_count"] == 1

    def test_validate_and_redeem_non_existent_code(self, coupon_manager):
        """Validate+redeem on non-existent code returns failure."""
        success, message, coupon = coupon_manager.validate_and_redeem("NOEXIST1", "user@test.com")

        assert success is False
        assert message == "Invalid coupon code"
        assert coupon is None


class TestCouponManagerUpdate:
    """Tests for CouponManager.update_coupon — Requirement 3.5."""

    def test_update_coupon_name(self, coupon_manager):
        """Update coupon name succeeds and updates timestamp."""
        coupon_manager._coupons["UPD00001"] = {
            "name": "Original", "code": "UPD00001", "max_usage": 10,
            "usage_count": 0, "used_by": [],
            "created_at": "2025-01-01 00:00", "updated_at": "2025-01-01 00:00"
        }

        with patch.object(coupon_manager, '_save_to_file'):
            result = coupon_manager.update_coupon("UPD00001", name="Updated Name")

        assert result["name"] == "Updated Name"
        assert result["updated_at"] != "2025-01-01 00:00"

    def test_update_coupon_max_usage(self, coupon_manager):
        """Update coupon max_usage succeeds."""
        coupon_manager._coupons["UPD00002"] = {
            "name": "Test", "code": "UPD00002", "max_usage": 5,
            "usage_count": 0, "used_by": [],
            "created_at": "2025-01-01 00:00", "updated_at": "2025-01-01 00:00"
        }

        with patch.object(coupon_manager, '_save_to_file'):
            result = coupon_manager.update_coupon("UPD00002", max_usage=50)

        assert result["max_usage"] == 50

    def test_update_coupon_code_field_raises_value_error(self, coupon_manager):
        """Attempting to update the code field raises ValueError (immutable)."""
        coupon_manager._coupons["IMMUT001"] = {
            "name": "Immutable", "code": "IMMUT001", "max_usage": 10,
            "usage_count": 0, "used_by": [],
            "created_at": "2025-01-01 00:00", "updated_at": "2025-01-01 00:00"
        }

        with patch.object(coupon_manager, '_save_to_file'):
            with pytest.raises(ValueError, match="cannot be modified"):
                coupon_manager.update_coupon("IMMUT001", code="NEWCODE1")

    def test_update_coupon_disallowed_field_raises_value_error(self, coupon_manager):
        """Attempting to update a disallowed field raises ValueError."""
        coupon_manager._coupons["DISALL01"] = {
            "name": "Test", "code": "DISALL01", "max_usage": 10,
            "usage_count": 0, "used_by": [],
            "created_at": "2025-01-01 00:00", "updated_at": "2025-01-01 00:00"
        }

        with patch.object(coupon_manager, '_save_to_file'):
            with pytest.raises(ValueError, match="Cannot update field"):
                coupon_manager.update_coupon("DISALL01", usage_count=99)

    def test_update_coupon_not_found_raises_key_error(self, coupon_manager):
        """Update non-existent coupon raises KeyError."""
        with patch.object(coupon_manager, '_save_to_file'):
            with pytest.raises(KeyError, match="not found"):
                coupon_manager.update_coupon("NOEXIST1", name="New")


class TestCouponManagerDelete:
    """Tests for CouponManager.delete_coupon — Requirement 3.6."""

    def test_delete_coupon_success(self, coupon_manager):
        """Delete existing coupon removes it from the store."""
        coupon_manager._coupons["DEL00001"] = {
            "name": "ToDelete", "code": "DEL00001", "max_usage": 10,
            "usage_count": 0, "used_by": [],
            "created_at": "2025-01-01 00:00", "updated_at": "2025-01-01 00:00"
        }

        with patch.object(coupon_manager, '_save_to_file'):
            coupon_manager.delete_coupon("DEL00001")

        assert "DEL00001" not in coupon_manager._coupons

    def test_delete_coupon_not_found_raises_key_error(self, coupon_manager):
        """Delete non-existent coupon raises KeyError."""
        with pytest.raises(KeyError, match="not found"):
            coupon_manager.delete_coupon("NOEXIST1")


class TestCouponManagerFileIO:
    """Tests for mocked file I/O — Requirement 3.7."""

    def test_load_initial_data_from_valid_json(self):
        """_load_initial_data loads coupons from a valid JSON file."""
        sample_data = {
            "CODE0001": {
                "name": "Loaded", "code": "CODE0001", "max_usage": 10,
                "usage_count": 2, "used_by": ["a@b.com"],
                "created_at": "2025-01-01 00:00", "updated_at": "2025-01-01 00:00"
            }
        }
        fake_path = Path("/fake/coupons.json")

        with patch.object(Path, 'exists', return_value=True):
            with patch.object(Path, 'read_text', return_value=json.dumps(sample_data)):
                with patch.object(CouponManager, '_save_to_file'):
                    cm = CouponManager(json_path=fake_path)

        assert "CODE0001" in cm._coupons
        assert cm._coupons["CODE0001"]["name"] == "Loaded"

    def test_load_initial_data_missing_file_creates_empty(self):
        """_load_initial_data with missing file initializes empty coupons."""
        fake_path = Path("/fake/coupons.json")

        with patch.object(Path, 'exists', return_value=False):
            with patch.object(CouponManager, '_save_to_file'):
                cm = CouponManager(json_path=fake_path)

        assert cm._coupons == {}

    def test_load_initial_data_invalid_json_creates_empty(self):
        """_load_initial_data with invalid JSON initializes empty coupons."""
        fake_path = Path("/fake/coupons.json")

        with patch.object(Path, 'exists', return_value=True):
            with patch.object(Path, 'read_text', return_value="not valid json{{{"):
                with patch.object(CouponManager, '_save_to_file'):
                    cm = CouponManager(json_path=fake_path)

        assert cm._coupons == {}

    def test_save_to_file_writes_json(self):
        """_save_to_file writes coupons as JSON to the file path."""
        fake_path = MagicMock(spec=Path)
        fake_tmp_path = MagicMock(spec=Path)
        fake_path.with_suffix.return_value = fake_tmp_path
        fake_parent = MagicMock()
        fake_path.parent = fake_parent

        with patch.object(CouponManager, '_load_initial_data'):
            cm = CouponManager(json_path=fake_path)
            cm._coupons = {"TEST": {"name": "Test"}}

        # Call the real _save_to_file
        cm._save_to_file()

        fake_parent.mkdir.assert_called_once_with(parents=True, exist_ok=True)
        fake_tmp_path.write_text.assert_called_once()
        written_data = fake_tmp_path.write_text.call_args[0][0]
        assert json.loads(written_data) == {"TEST": {"name": "Test"}}
        fake_tmp_path.replace.assert_called_once_with(fake_path)


class TestGenerateCouponCode:
    """Tests for generate_coupon_code helper — Requirement 3.8."""

    def test_generates_8_char_code(self):
        """Generated code is exactly 8 characters."""
        code = generate_coupon_code(set())
        assert len(code) == 8

    def test_generates_uppercase_alphanumeric(self):
        """Generated code contains only uppercase letters and digits."""
        code = generate_coupon_code(set())
        assert code.isalnum()
        assert code == code.upper()

    def test_generates_unique_code(self):
        """Generated code is not in the existing codes set."""
        existing = {"AAAAAAAA", "BBBBBBBB", "CCCCCCCC"}
        code = generate_coupon_code(existing)
        assert code not in existing

    def test_raises_runtime_error_when_exhausted(self):
        """Raises RuntimeError when unable to generate unique code after max attempts."""
        # Create a mock that always returns the same code
        with patch('app.pdn_admin.coupon_manager.secrets.choice', return_value='A'):
            existing = {"AAAAAAAA"}  # The only code that can be generated
            with pytest.raises(RuntimeError, match="Unable to generate"):
                generate_coupon_code(existing)


class TestValidateCustomCode:
    """Tests for validate_custom_code helper."""

    def test_valid_code(self):
        """Valid 4-20 alphanumeric code passes validation."""
        is_valid, msg = validate_custom_code("ABCD1234")
        assert is_valid is True
        assert msg == ""

    def test_code_too_short(self):
        """Code shorter than 4 chars fails validation."""
        is_valid, msg = validate_custom_code("AB")
        assert is_valid is False
        assert "4-20" in msg

    def test_code_too_long(self):
        """Code longer than 20 chars fails validation."""
        is_valid, msg = validate_custom_code("A" * 21)
        assert is_valid is False
        assert "4-20" in msg

    def test_code_with_special_chars(self):
        """Code with special characters fails validation."""
        is_valid, msg = validate_custom_code("CODE-123")
        assert is_valid is False
        assert "alphanumeric" in msg

    def test_non_string_code(self):
        """Non-string code fails validation."""
        is_valid, msg = validate_custom_code(12345)
        assert is_valid is False
        assert "must be a string" in msg


class TestCouponManagerGetAndStatus:
    """Tests for CouponManager.get_coupon, get_all_coupons, get_status, to_response."""

    def test_get_coupon_existing(self, coupon_manager):
        """get_coupon returns a copy of the coupon for existing code."""
        coupon_manager._coupons["GET00001"] = {
            "name": "Get Test", "code": "GET00001", "max_usage": 10,
            "usage_count": 3, "used_by": ["a@b.com"],
            "created_at": "2025-01-01 00:00", "updated_at": "2025-01-01 00:00"
        }

        result = coupon_manager.get_coupon("GET00001")
        assert result is not None
        assert result["name"] == "Get Test"
        assert result["code"] == "GET00001"
        # Verify it's a copy (not the same object)
        assert result is not coupon_manager._coupons["GET00001"]

    def test_get_coupon_non_existent(self, coupon_manager):
        """get_coupon returns None for non-existent code."""
        result = coupon_manager.get_coupon("NOEXIST1")
        assert result is None

    def test_get_all_coupons(self, coupon_manager):
        """get_all_coupons returns all coupons with status field added."""
        coupon_manager._coupons["ACTIVE01"] = {
            "name": "Active", "code": "ACTIVE01", "max_usage": 10,
            "usage_count": 3, "used_by": [],
            "created_at": "2025-01-01 00:00", "updated_at": "2025-01-01 00:00"
        }
        coupon_manager._coupons["FULL0001"] = {
            "name": "Full", "code": "FULL0001", "max_usage": 5,
            "usage_count": 5, "used_by": [],
            "created_at": "2025-01-01 00:00", "updated_at": "2025-01-01 00:00"
        }

        result = coupon_manager.get_all_coupons()
        assert len(result) == 2
        # Check status is added
        statuses = {c["code"]: c["status"] for c in result}
        assert statuses["ACTIVE01"] == "active"
        assert statuses["FULL0001"] == "full"

    def test_get_status_active(self, coupon_manager):
        """get_status returns 'active' when usage_count < max_usage."""
        coupon = {"usage_count": 3, "max_usage": 10}
        assert coupon_manager.get_status(coupon) == "active"

    def test_get_status_full(self, coupon_manager):
        """get_status returns 'full' when usage_count >= max_usage."""
        coupon = {"usage_count": 10, "max_usage": 10}
        assert coupon_manager.get_status(coupon) == "full"

    def test_to_response_adds_status(self, coupon_manager):
        """to_response returns coupon dict with status field added."""
        coupon = {
            "name": "Test", "code": "RESP0001", "max_usage": 10,
            "usage_count": 2, "used_by": [],
            "created_at": "2025-01-01 00:00", "updated_at": "2025-01-01 00:00"
        }

        result = coupon_manager.to_response(coupon)
        assert result["status"] == "active"
        assert result["name"] == "Test"
        assert result["code"] == "RESP0001"


class TestCouponManagerRedeem:
    """Tests for CouponManager.redeem_coupon."""

    def test_redeem_coupon_success(self, coupon_manager):
        """Redeem valid coupon increments usage_count and adds email."""
        coupon_manager._coupons["REDM0001"] = {
            "name": "Redeem", "code": "REDM0001", "max_usage": 10,
            "usage_count": 2, "used_by": ["prev@test.com"],
            "created_at": "2025-01-01 00:00", "updated_at": "2025-01-01 00:00"
        }

        with patch.object(coupon_manager, '_save_to_file'):
            result = coupon_manager.redeem_coupon("REDM0001", "new@test.com")

        assert result["usage_count"] == 3
        assert "new@test.com" in result["used_by"]
        assert "prev@test.com" in result["used_by"]

    def test_redeem_coupon_email_deduplication(self, coupon_manager):
        """Redeem with same email does not increment usage_count."""
        coupon_manager._coupons["REDM0002"] = {
            "name": "Dedup", "code": "REDM0002", "max_usage": 10,
            "usage_count": 1, "used_by": ["same@test.com"],
            "created_at": "2025-01-01 00:00", "updated_at": "2025-01-01 00:00"
        }

        with patch.object(coupon_manager, '_save_to_file'):
            result = coupon_manager.redeem_coupon("REDM0002", "same@test.com")

        # Should NOT increment for returning user
        assert result["usage_count"] == 1
        assert result["used_by"].count("same@test.com") == 1

    def test_redeem_coupon_exhausted_raises_value_error(self, coupon_manager):
        """Redeem exhausted coupon raises ValueError."""
        coupon_manager._coupons["REDM0003"] = {
            "name": "Full", "code": "REDM0003", "max_usage": 1,
            "usage_count": 1, "used_by": ["first@test.com"],
            "created_at": "2025-01-01 00:00", "updated_at": "2025-01-01 00:00"
        }

        with pytest.raises(ValueError, match="usage limit"):
            coupon_manager.redeem_coupon("REDM0003", "new@test.com")

    def test_redeem_coupon_not_found_raises_value_error(self, coupon_manager):
        """Redeem non-existent coupon raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            coupon_manager.redeem_coupon("NOEXIST1", "user@test.com")
