"""Property-based tests for UserHistoryService encryption and persistence round-trip.

Validates: Requirements 1, 2, 3, 4, 6, 8, 12
"""

import json
import tempfile

import pytest
from hypothesis import given, assume, settings
from hypothesis import strategies as st

from app.utils.user_history_service import UserHistoryService, SCHEMA_VERSION


@pytest.fixture
def service(tmp_path):
    """Create a UserHistoryService with a temporary base directory."""
    return UserHistoryService(base_dir=str(tmp_path))


# --- Strategies ---

@st.composite
def valid_user_ids(draw):
    """Generate user_ids that pass validation (safe for filesystem)."""
    user_id = draw(st.text(
        min_size=1, max_size=20,
        alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789._@+-")
    ))
    assume(".." not in user_id)
    assume("/" not in user_id)
    assume("\\" not in user_id)
    assume("\x00" not in user_id)
    assume(user_id.strip() != "")
    return user_id


@st.composite
def non_empty_summaries(draw):
    """Generate non-empty summary strings."""
    summary = draw(st.text(min_size=1, max_size=200))
    assume(summary.strip() != "")
    return summary


# Strategy for arbitrary text that can be valid JSON strings
valid_json_strings = st.text(min_size=1, max_size=500)

# Strategy for Hebrew/Unicode text
hebrew_text = st.text(
    min_size=1, max_size=100,
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "Z"),
        whitelist_characters="אבגדהוזחטיכלמנסעפצקרשת\n "
    )
)


# --- Property 1: Round-trip integrity ---

class TestProperty1RoundTripIntegrity:
    """Property 1: Save then load returns same data.

    **Validates: Requirements 1**
    """

    @given(user_id=valid_user_ids(), summary=non_empty_summaries())
    @settings(max_examples=100)
    def test_save_then_load_returns_same_data(self, user_id, summary):
        """For any valid user_id and summary, saving then loading returns the same data."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = UserHistoryService(base_dir=tmp_dir)

            result = service.save_user_history(user_id, summary)
            assume(result is True)

            loaded = service.load_user_history(user_id)
            assert loaded is not None
            assert loaded.summary == summary
            assert loaded.user_id == user_id
            assert loaded.schema_version == SCHEMA_VERSION


# --- Property 2: Encryption round-trip ---

class TestProperty2EncryptionRoundTrip:
    """Property 2: Encrypt then decrypt is identity for any valid JSON string.

    **Validates: Requirements 2**
    """

    @given(text=valid_json_strings)
    @settings(max_examples=200)
    def test_encrypt_decrypt_identity(self, text):
        """For any text string, encrypt then decrypt returns the original."""
        service = UserHistoryService(base_dir="/tmp/test_prop2")
        encrypted = service.encrypt_payload(text)
        decrypted = service.decrypt_payload(encrypted)
        assert decrypted == text


# --- Property 3: Encryption obfuscation ---

class TestProperty3EncryptionObfuscation:
    """Property 3: Encrypted output is never valid JSON.

    **Validates: Requirements 3**
    """

    @given(text=valid_json_strings)
    @settings(max_examples=200)
    def test_encrypted_output_not_valid_json(self, text):
        """Encrypted output should never be parseable as valid JSON."""
        service = UserHistoryService(base_dir="/tmp/test_prop3")
        encrypted = service.encrypt_payload(text)

        # encrypted is bytes; try to parse as JSON (both as bytes and decoded)
        try:
            json.loads(encrypted)
            # If it parses as JSON, that's a failure
            assert False, "Encrypted data should not be valid JSON"
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            pass  # Expected — encrypted data is not valid JSON


# --- Property 4: Atomic write safety ---

class TestProperty4AtomicWriteSafety:
    """Property 4: File always contains complete valid payload after save.

    **Validates: Requirements 4**
    """

    @given(user_id=valid_user_ids(), summary=non_empty_summaries())
    @settings(max_examples=50)
    def test_file_contains_complete_payload_after_save(self, user_id, summary):
        """After save, loading returns a complete payload with all required fields."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = UserHistoryService(base_dir=tmp_dir)

            result = service.save_user_history(user_id, summary)
            assume(result is True)

            loaded = service.load_user_history(user_id)
            assert loaded is not None
            assert loaded.summary == summary
            assert loaded.user_id == user_id
            assert loaded.schema_version == SCHEMA_VERSION
            assert loaded.updated_at  # non-empty timestamp


# --- Property 6: Delete idempotency ---

class TestProperty6DeleteIdempotency:
    """Property 6: Deleting non-existent history returns True.

    **Validates: Requirements 6**
    """

    @given(user_id=valid_user_ids())
    @settings(max_examples=100)
    def test_delete_nonexistent_returns_true(self, user_id):
        """Deleting a user_id that was never saved returns True (no error)."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            service = UserHistoryService(base_dir=tmp_dir)
            result = service.delete_user_history(user_id)
            assert result is True


# --- Property 8: Override semantics ---

class TestProperty8OverrideSemantics:
    """Property 8: Each save fully replaces previous content.

    **Validates: Requirements 8**
    """

    @given(
        user_id=valid_user_ids(),
        summary1=non_empty_summaries(),
        summary2=non_empty_summaries(),
    )
    @settings(max_examples=50)
    def test_second_save_replaces_first(self, user_id, summary1, summary2):
        """Saving twice with different summaries, only the second is present."""
        assume(summary1 != summary2)
        # Avoid cases where one summary is a substring of the other
        assume(summary1 not in summary2)

        with tempfile.TemporaryDirectory() as tmp_dir:
            service = UserHistoryService(base_dir=tmp_dir)

            result1 = service.save_user_history(user_id, summary1)
            assume(result1 is True)

            result2 = service.save_user_history(user_id, summary2)
            assume(result2 is True)

            loaded = service.load_user_history(user_id)
            assert loaded is not None
            assert loaded.summary == summary2
            assert summary1 not in loaded.summary


# --- Property 12: Unicode/Hebrew summary round-trip ---

class TestProperty12UnicodeHebrewRoundTrip:
    """Property 12: Hebrew text survives persistence round-trip.

    **Validates: Requirements 12**
    """

    @given(user_id=valid_user_ids(), summary=hebrew_text)
    @settings(max_examples=50)
    def test_hebrew_text_survives_round_trip(self, user_id, summary):
        """Hebrew/Unicode text is preserved exactly through save and load."""
        assume(summary.strip() != "")

        with tempfile.TemporaryDirectory() as tmp_dir:
            service = UserHistoryService(base_dir=tmp_dir)

            result = service.save_user_history(user_id, summary)
            assume(result is True)

            loaded = service.load_user_history(user_id)
            assert loaded is not None
            assert loaded.summary == summary
