"""Property-based tests for UserHistoryService validation and path resolution.

Validates: Requirements 5, 9, 13, 14
"""

import tempfile
from pathlib import Path

import pytest
from hypothesis import given, assume, settings
from hypothesis import strategies as st

from app.utils.user_history_service import UserHistoryService


@pytest.fixture
def service(tmp_path):
    """Create a UserHistoryService with a temporary base directory."""
    return UserHistoryService(base_dir=str(tmp_path))


# --- Strategies ---

# Strategy for strings containing path traversal characters
_PATH_TRAVERSAL_CHARS = st.sampled_from(["../", "..\\", "..", "/", "\\", "\x00"])


@st.composite
def path_traversal_ids(draw):
    """Generate strings that contain path traversal sequences."""
    prefix = draw(st.text(min_size=0, max_size=5, alphabet=st.characters(whitelist_categories=("L", "N"))))
    traversal = draw(_PATH_TRAVERSAL_CHARS)
    suffix = draw(st.text(min_size=0, max_size=5, alphabet=st.characters(whitelist_categories=("L", "N"))))
    return prefix + traversal + suffix


# Strategy for valid email-like strings with a domain that has a dot
@st.composite
def email_with_domain(draw):
    """Generate email-like strings: local@domain.tld"""
    local = draw(st.text(
        min_size=1, max_size=10,
        alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789._+-")
    ))
    domain = draw(st.text(
        min_size=1, max_size=8,
        alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789")
    ))
    tld = draw(st.text(
        min_size=2, max_size=4,
        alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz")
    ))
    return f"{local}@{domain}.{tld}"


# Strategy for user_ids containing the + character
@st.composite
def user_id_with_plus(draw):
    """Generate valid user_ids that contain at least one + character."""
    local = draw(st.text(
        min_size=1, max_size=6,
        alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789._-")
    ).filter(lambda s: ".." not in s and not s.startswith(".") and not s.endswith(".")))
    tag = draw(st.text(
        min_size=1, max_size=6,
        alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789")
    ))
    domain = draw(st.text(
        min_size=1, max_size=6,
        alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789")
    ))
    tld = draw(st.text(
        min_size=2, max_size=4,
        alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz")
    ))
    return f"{local}+{tag}@{domain}.{tld}"


# Strategy for valid user_ids suitable for resolve_user_history_path
@st.composite
def valid_user_ids(draw):
    """Generate user_ids that pass validation (safe for filesystem)."""
    user_id = draw(st.text(
        min_size=1, max_size=20,
        alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789._@+-")
    ))
    # Ensure it doesn't accidentally contain traversal patterns
    assume(".." not in user_id)
    assume("/" not in user_id)
    assume("\\" not in user_id)
    assume("\x00" not in user_id)
    assume(user_id.strip() != "")
    return user_id


# --- Property 5: Path traversal prevention ---

class TestProperty5PathTraversalPrevention:
    """Property 5: Malicious user_ids containing path traversal are rejected.

    **Validates: Requirements 5**
    """

    @given(malicious_id=path_traversal_ids())
    @settings(max_examples=200)
    def test_path_traversal_rejected(self, malicious_id):
        """Any user_id containing .., /, \\, or null bytes is rejected."""
        service = UserHistoryService(base_dir="/tmp/test_prop5")
        assert service.validate_user_id(malicious_id) is False


# --- Property 9: Filename generation ---

class TestProperty9FilenameGeneration:
    """Property 9: _build_history_filename strips last domain suffix correctly.

    **Validates: Requirements 9**
    """

    @given(email=email_with_domain())
    @settings(max_examples=200)
    def test_strips_last_domain_suffix(self, email):
        """For email-like strings with @domain.tld, the last .tld is stripped."""
        service = UserHistoryService(base_dir="/tmp/test_prop9")
        filename = service._build_history_filename(email)

        # The filename should end with _history.enc
        assert filename.endswith("_history.enc")

        # The last dot-separated part of the original email should NOT appear
        # before _history.enc (it was stripped)
        last_suffix = email.rsplit(".", 1)[1]
        name_part = filename[: -len("_history.enc")]
        # The name_part should be email without the last .suffix
        expected_name = email.rsplit(".", 1)[0]
        assert name_part == expected_name

    @given(plain_id=st.text(
        min_size=1, max_size=15,
        alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789_-")
    ))
    @settings(max_examples=100)
    def test_non_email_uses_raw_string(self, plain_id):
        """Non-email user_ids (no @ or no dot in domain) use the raw string."""
        assume("@" not in plain_id)
        service = UserHistoryService(base_dir="/tmp/test_prop9")
        filename = service._build_history_filename(plain_id)
        assert filename == f"{plain_id}_history.enc"


# --- Property 13: validate_user_id accepts + character ---

class TestProperty13PlusCharacterAccepted:
    """Property 13: validate_user_id accepts user_ids with + character.

    **Validates: Requirements 13**
    """

    @given(user_id=user_id_with_plus())
    @settings(max_examples=200)
    def test_plus_character_accepted(self, user_id):
        """User IDs containing + (common in email tags) pass validation."""
        service = UserHistoryService(base_dir="/tmp/test_prop13")
        assert service.validate_user_id(user_id) is True


# --- Property 14: resolve_user_history_path creates directory ---

class TestProperty14ResolveCreatesDirectory:
    """Property 14: resolve_user_history_path creates parent directory.

    **Validates: Requirements 14**
    """

    @given(user_id=valid_user_ids())
    @settings(max_examples=50)
    def test_parent_directory_created(self, user_id):
        """After resolving a path, the parent directory exists."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = UserHistoryService(base_dir=tmp_dir)
            path = service.resolve_user_history_path(user_id)
            assert path.parent.exists()
            assert path.parent.is_dir()

    @given(user_id=valid_user_ids())
    @settings(max_examples=50)
    def test_resolved_path_under_base_dir(self, user_id):
        """Resolved path is always under the service's base_dir."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = UserHistoryService(base_dir=tmp_dir)
            path = service.resolve_user_history_path(user_id)
            assert str(path).startswith(str(Path(tmp_dir).resolve()))
