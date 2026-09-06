"""Unit tests for UserHistoryService.validate_user_id()."""

import pytest

from app.utils.user_history_service import UserHistoryService


@pytest.fixture
def service():
    """Create a UserHistoryService instance for testing."""
    return UserHistoryService(base_dir="/tmp/test_history")


class TestValidateUserId:
    """Tests for validate_user_id method."""

    def test_valid_email(self, service):
        assert service.validate_user_id("user@example.com") is True

    def test_valid_email_with_plus(self, service):
        assert service.validate_user_id("user+tag@gmail.com") is True

    def test_valid_simple_username(self, service):
        assert service.validate_user_id("username123") is True

    def test_valid_with_dots_and_hyphens(self, service):
        assert service.validate_user_id("first.last-name@domain.co.il") is True

    def test_valid_with_underscore(self, service):
        assert service.validate_user_id("user_name") is True

    def test_rejects_empty_string(self, service):
        assert service.validate_user_id("") is False

    def test_rejects_whitespace_only(self, service):
        assert service.validate_user_id("   ") is False

    def test_rejects_tab_only(self, service):
        assert service.validate_user_id("\t") is False

    def test_rejects_path_traversal_dotdot(self, service):
        assert service.validate_user_id("../etc/passwd") is False

    def test_rejects_path_traversal_embedded(self, service):
        assert service.validate_user_id("user/../admin") is False

    def test_rejects_forward_slash(self, service):
        assert service.validate_user_id("user/name") is False

    def test_rejects_backslash(self, service):
        assert service.validate_user_id("user\\name") is False

    def test_rejects_null_byte(self, service):
        assert service.validate_user_id("user\x00name") is False

    def test_rejects_spaces_in_id(self, service):
        assert service.validate_user_id("user name") is False

    def test_rejects_special_characters(self, service):
        assert service.validate_user_id("user<script>") is False

    def test_rejects_semicolon(self, service):
        assert service.validate_user_id("user;drop") is False

    def test_no_side_effects(self, service):
        """validate_user_id is a pure function with no side effects."""
        # Calling multiple times with same input gives same result
        result1 = service.validate_user_id("test@example.com")
        result2 = service.validate_user_id("test@example.com")
        assert result1 == result2 is True
