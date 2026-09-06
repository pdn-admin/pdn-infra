"""Tests for user management."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, PropertyMock

from app.pdn_chat_ai.user_manager import UserManager


@pytest.fixture
def user_mgr(tmp_path):
    """Create a UserManager with tmp_path JSON file and mock prompts dir."""
    json_path = tmp_path / "users.json"
    # Create a mock prompts directory with some .prompt files
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    for code in ['a3', 'a7', 'a11', 'e1', 'e5', 'e9', 'p2', 'p6', 'p10', 't4', 't8', 't12']:
        (prompts_dir / f"{code}.prompt").write_text("prompt content")

    mgr = UserManager(json_path=json_path)
    # Override PROMPTS_DIR to use our tmp prompts
    mgr.PROMPTS_DIR = prompts_dir
    return mgr


class TestGetUser:
    """Tests for get_user()."""

    def test_returns_correct_data_for_existing_user(self, user_mgr):
        """Should return user data for seeded users."""
        # Seeded users exist from _SEED_USERS
        user = user_mgr.get_user('tomergur@gmail.com')
        assert user is not None
        assert user['name'] == 'תומר'
        assert user['pdn_code'] == 'e5'

    def test_returns_none_for_nonexistent_user(self, user_mgr):
        """Should return None for unknown email."""
        user = user_mgr.get_user('nobody@nowhere.com')
        assert user is None


class TestAddUser:
    """Tests for add_user()."""

    def test_add_user_with_valid_data(self, user_mgr):
        """Should successfully add a new user."""
        result = user_mgr.add_user(
            email='newuser@test.com',
            password='pass123',
            name='Test User',
            pdn_code='a7',
            daily_conversation_limit=20
        )
        assert result['email'] == 'newuser@test.com'
        assert result['name'] == 'Test User'
        assert result['pdn_code'] == 'a7'
        # Verify persisted
        user = user_mgr.get_user('newuser@test.com')
        assert user is not None

    def test_add_user_duplicate_email_raises(self, user_mgr):
        """Should raise ValueError for duplicate email."""
        user_mgr.add_user('dup@test.com', 'pass', 'Dup', 'a7')
        with pytest.raises(ValueError, match="כבר קיים"):
            user_mgr.add_user('dup@test.com', 'pass', 'Dup2', 'a7')

    def test_add_user_invalid_email_raises(self, user_mgr):
        """Should raise ValueError for invalid email format."""
        with pytest.raises(ValueError, match="אימייל"):
            user_mgr.add_user('not-an-email', 'pass', 'Name', 'a7')

    def test_add_user_empty_password_raises(self, user_mgr):
        """Should raise ValueError for empty password."""
        with pytest.raises(ValueError, match="סיסמה"):
            user_mgr.add_user('valid@test.com', '', 'Name', 'a7')

    def test_add_user_empty_name_raises(self, user_mgr):
        """Should raise ValueError for empty name."""
        with pytest.raises(ValueError, match="שם"):
            user_mgr.add_user('valid@test.com', 'pass', '  ', 'a7')

    def test_add_user_invalid_pdn_code_raises(self, user_mgr):
        """Should raise ValueError for invalid PDN code."""
        with pytest.raises(ValueError, match="PDN"):
            user_mgr.add_user('valid@test.com', 'pass', 'Name', 'invalid_code')


class TestUpdateUser:
    """Tests for update_user()."""

    def test_updates_fields_correctly(self, user_mgr):
        """Should update specified fields."""
        user_mgr.add_user('update@test.com', 'pass', 'Original', 'a7')
        result = user_mgr.update_user('update@test.com', name='Updated Name')
        assert result['name'] == 'Updated Name'
        # Verify persisted
        user = user_mgr.get_user('update@test.com')
        assert user['name'] == 'Updated Name'

    def test_update_nonexistent_user_raises(self, user_mgr):
        """Should raise KeyError for non-existent user."""
        with pytest.raises(KeyError):
            user_mgr.update_user('nobody@test.com', name='New Name')

    def test_update_pdn_code(self, user_mgr):
        """Should update PDN code if valid."""
        user_mgr.add_user('code@test.com', 'pass', 'User', 'a7')
        result = user_mgr.update_user('code@test.com', pdn_code='e5')
        assert result['pdn_code'] == 'e5'


class TestDeleteUser:
    """Tests for delete_user()."""

    def test_removes_user(self, user_mgr):
        """Should remove user from storage."""
        user_mgr.add_user('delete@test.com', 'pass', 'ToDelete', 'a7')
        user_mgr.delete_user('delete@test.com')
        assert user_mgr.get_user('delete@test.com') is None

    def test_delete_nonexistent_raises(self, user_mgr):
        """Should raise KeyError for non-existent user."""
        with pytest.raises(KeyError):
            user_mgr.delete_user('nobody@test.com')


class TestValidateEmail:
    """Tests for validate_email()."""

    def test_valid_emails(self, user_mgr):
        """Should accept valid email formats."""
        assert user_mgr.validate_email('user@example.com') is True
        assert user_mgr.validate_email('user.name@domain.co.il') is True
        assert user_mgr.validate_email('user+tag@gmail.com') is True

    def test_invalid_emails(self, user_mgr):
        """Should reject invalid email formats."""
        assert user_mgr.validate_email('') is False
        assert user_mgr.validate_email('no-at-sign') is False
        assert user_mgr.validate_email('@no-local.com') is False
        assert user_mgr.validate_email('no-domain@') is False
        assert user_mgr.validate_email('spaces in@email.com') is False


class TestGetAvailablePdnCodes:
    """Tests for get_available_pdn_codes()."""

    def test_returns_list_from_disk(self, user_mgr):
        """Should return sorted list of .prompt file stems."""
        codes = user_mgr.get_available_pdn_codes()
        assert isinstance(codes, list)
        assert 'a7' in codes
        assert 'e5' in codes
        assert 'p10' in codes
        assert codes == sorted(codes)

    def test_returns_empty_if_dir_missing(self, tmp_path):
        """Should return empty list if prompts dir doesn't exist."""
        json_path = tmp_path / "users.json"
        mgr = UserManager(json_path=json_path)
        mgr.PROMPTS_DIR = tmp_path / "nonexistent"
        assert mgr.get_available_pdn_codes() == []
