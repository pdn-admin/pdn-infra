"""Integration tests for UserHistoryService save/load lifecycle.

Tests the full end-to-end behavior of UserHistoryService without mocking.
Focuses on realistic scenarios: save → load → inject into context,
service restart persistence, delete semantics, and Hebrew text handling.
"""

import pytest

from app.utils.user_history_service import (
    SCHEMA_VERSION,
    UserHistoryService,
)


@pytest.fixture
def service(tmp_path):
    """Create a UserHistoryService with a temporary base directory."""
    return UserHistoryService(base_dir=str(tmp_path))


class TestSaveLoadFullLifecycle:
    """Test full flow: save with all fields, load, verify all payload fields."""

    def test_save_load_full_lifecycle(self, tmp_path):
        """Save with all fields, load, verify summary/user_id/schema_version/metadata/updated_at."""
        service = UserHistoryService(base_dir=str(tmp_path))
        user_id = "tomer.gur@example.com"
        summary = "Topic: Career transition\nStage: 2\nInsight: Fears change\nAction: Journaling"
        metadata = {"source": "PDNChat", "summary_version": "1", "turns_summarized": 10}

        # Save
        result = service.save_user_history(user_id, summary, metadata=metadata)
        assert result is True

        # Load
        loaded = service.load_user_history(user_id)
        assert loaded is not None

        # Verify all fields
        assert loaded.summary == summary
        assert loaded.user_id == user_id
        assert loaded.schema_version == SCHEMA_VERSION
        assert loaded.metadata == metadata
        assert loaded.updated_at  # non-empty ISO 8601 timestamp
        # Verify timestamp is valid ISO format (contains 'T' separator)
        assert "T" in loaded.updated_at


class TestHistorySurvivesServiceRestart:
    """Test that history persists across service instances (simulating restart)."""

    def test_history_survives_service_restart(self, tmp_path):
        """Save with one service instance, create new instance with same base_dir, load and verify."""
        user_id = "penina+test@gmail.com"
        summary = "נושא: מעבר קריירה\nשלב: 3\nתובנה: מוכנה לשינוי"
        metadata = {"source": "PDNChat", "summary_version": "1"}

        # First service instance — save
        service1 = UserHistoryService(base_dir=str(tmp_path))
        result = service1.save_user_history(user_id, summary, metadata=metadata)
        assert result is True

        # Simulate restart: create a completely new service instance with same base_dir
        service2 = UserHistoryService(base_dir=str(tmp_path))

        # Load from the new instance
        loaded = service2.load_user_history(user_id)
        assert loaded is not None
        assert loaded.summary == summary
        assert loaded.user_id == user_id
        assert loaded.schema_version == SCHEMA_VERSION
        assert loaded.metadata == metadata


class TestSaveLoadInjectContext:
    """Test save, load, inject into messages, verify injected message contains summary."""

    def test_save_load_inject_context(self, tmp_path):
        """Save, load, inject into messages, verify the injected message contains the summary."""
        service = UserHistoryService(base_dir=str(tmp_path))
        user_id = "user@domain.co.il"
        summary = "Topic: Self-awareness\nStage: 1\nInsight: Needs structure\nAction: Morning routine"
        metadata = {"source": "PDNChat"}

        # Save
        service.save_user_history(user_id, summary, metadata=metadata)

        # Load
        payload = service.load_user_history(user_id)
        assert payload is not None

        # Inject into conversation context
        messages = [
            {"role": "system", "content": "You are a PDN coach."},
            {"role": "user", "content": "שלום, אני רוצה להתחיל"},
        ]
        result = service.inject_user_history_into_context(payload, messages)

        # Verify injection
        assert len(result) == 3  # original 2 + 1 injected
        # Original system message is first
        assert result[0]["role"] == "system"
        assert result[0]["content"] == "You are a PDN coach."
        # Injected history message is second (after first system message)
        assert result[1]["role"] == "system"
        assert "[Previous Session Summary]" in result[1]["content"]
        assert summary in result[1]["content"]
        assert "[End Previous Session Summary]" in result[1]["content"]
        # User message preserved at the end
        assert result[2]["role"] == "user"
        assert result[2]["content"] == "שלום, אני רוצה להתחיל"


class TestDeleteClearsHistory:
    """Test that delete clears history and subsequent load returns None."""

    def test_delete_clears_history(self, tmp_path):
        """Save, delete, load returns None."""
        service = UserHistoryService(base_dir=str(tmp_path))
        user_id = "delete-test@example.com"
        summary = "Some conversation summary to be deleted"

        # Save
        result = service.save_user_history(user_id, summary)
        assert result is True

        # Verify it exists
        loaded = service.load_user_history(user_id)
        assert loaded is not None

        # Delete
        delete_result = service.delete_user_history(user_id)
        assert delete_result is True

        # Load after delete returns None
        loaded_after = service.load_user_history(user_id)
        assert loaded_after is None


class TestOverrideSemanticsIntegration:
    """Test that saving twice returns only the second save."""

    def test_override_semantics_integration(self, tmp_path):
        """Save twice, load returns only the second."""
        service = UserHistoryService(base_dir=str(tmp_path))
        user_id = "override@example.com"
        first_summary = "First session: Topic was career change"
        second_summary = "Second session: Topic shifted to relationships"
        metadata_first = {"session": "1"}
        metadata_second = {"session": "2"}

        # First save
        service.save_user_history(user_id, first_summary, metadata=metadata_first)

        # Second save (override)
        service.save_user_history(user_id, second_summary, metadata=metadata_second)

        # Load — should only have the second
        loaded = service.load_user_history(user_id)
        assert loaded is not None
        assert loaded.summary == second_summary
        assert first_summary not in loaded.summary
        assert loaded.metadata == metadata_second


class TestHebrewFullLifecycle:
    """Test Hebrew summary survives the full save → load → inject lifecycle."""

    def test_hebrew_full_lifecycle(self, tmp_path):
        """Save Hebrew summary, load, inject, verify Hebrew text preserved throughout."""
        service = UserHistoryService(base_dir=str(tmp_path))
        user_id = "tomer.gur@gmail.com"
        hebrew_summary = (
            "נושא: מעבר קריירה\n"
            "שלב: 2\n"
            "תובנה: חושש משינוי אבל מוכן לצעד הבא\n"
            "פעולה: כתיבת יומן רגשי"
        )
        metadata = {"source": "PDNChat", "summary_version": "1"}

        # Save Hebrew content
        result = service.save_user_history(user_id, hebrew_summary, metadata=metadata)
        assert result is True

        # Load and verify Hebrew preserved
        loaded = service.load_user_history(user_id)
        assert loaded is not None
        assert loaded.summary == hebrew_summary

        # Inject into context and verify Hebrew preserved
        messages = [
            {"role": "system", "content": "אתה מאמן PDN מקצועי"},
            {"role": "user", "content": "מה עשינו בפעם הקודמת?"},
        ]
        result = service.inject_user_history_into_context(loaded, messages)

        assert len(result) == 3
        injected = result[1]
        assert injected["role"] == "system"
        assert hebrew_summary in injected["content"]
        assert "נושא: מעבר קריירה" in injected["content"]
        assert "חושש משינוי" in injected["content"]
