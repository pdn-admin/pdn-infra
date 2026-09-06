"""Tests for answer persistence."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.utils.answer_storage import (
    save_answer,
    load_answers,
    delete_answer,
    save_user_metadata,
)
from app.utils.pdn_file_path import PDNFilePath


@pytest.fixture
def storage_path(tmp_path):
    """Create a PDNFilePath instance using tmp_path."""
    return PDNFilePath(base_dir=str(tmp_path))


@pytest.fixture
def mock_pdn_file_path(tmp_path):
    """Patch the module-level pdn_file_path in answer_storage."""
    pdn_fp = PDNFilePath(base_dir=str(tmp_path))
    with patch('app.utils.answer_storage.pdn_file_path', pdn_fp):
        yield pdn_fp


class TestSaveAnswer:
    """Tests for save_answer()."""

    def test_creates_file_and_stores_data(self, mock_pdn_file_path):
        """Should create answer file and store answer data."""
        answer_data = {
            'selected_option_code': 'AP',
            'selected_option_text': 'Option A and P'
        }
        save_answer('test@example.com', 1, answer_data)

        # Verify file was created and contains data
        answers = load_answers('test@example.com')
        assert answers is not None
        assert '1' in answers
        assert answers['1']['selected_option_code'] == 'AP'

    def test_stores_multiple_answers(self, mock_pdn_file_path):
        """Should store multiple answers in same file."""
        save_answer('test@example.com', 1, {'selected_option_code': 'AP'})
        save_answer('test@example.com', 2, {'selected_option_code': 'ET'})

        answers = load_answers('test@example.com')
        assert '1' in answers
        assert '2' in answers

    def test_overwrites_existing_answer(self, mock_pdn_file_path):
        """Should overwrite answer for same question number."""
        save_answer('test@example.com', 1, {'selected_option_code': 'AP'})
        save_answer('test@example.com', 1, {'selected_option_code': 'ET'})

        answers = load_answers('test@example.com')
        assert answers['1']['selected_option_code'] == 'ET'

    def test_stores_question_text(self, mock_pdn_file_path):
        """Should store question_text when provided."""
        save_answer('test@example.com', 1, {'selected_option_code': 'AP'}, question_text="What is your preference?")

        answers = load_answers('test@example.com')
        assert answers['1']['question_text'] == "What is your preference?"

    def test_filters_none_values(self, mock_pdn_file_path):
        """Should filter out None values from answer_data."""
        save_answer('test@example.com', 1, {
            'selected_option_code': 'AP',
            'ranking': None,
            'extra': None
        })
        answers = load_answers('test@example.com')
        assert 'ranking' not in answers['1']
        assert 'extra' not in answers['1']


class TestLoadAnswers:
    """Tests for load_answers()."""

    def test_returns_saved_data(self, mock_pdn_file_path):
        """Should return previously saved answers."""
        save_answer('test@example.com', 1, {'selected_option_code': 'AP'})
        result = load_answers('test@example.com')
        assert result is not None
        assert '1' in result

    def test_returns_none_for_nonexistent_user(self, mock_pdn_file_path):
        """Should return None when no answers file exists."""
        result = load_answers('nonexistent@example.com')
        assert result is None


class TestDeleteAnswer:
    """Tests for delete_answer()."""

    def test_removes_specific_answer(self, mock_pdn_file_path):
        """Should remove only the specified answer."""
        save_answer('test@example.com', 1, {'selected_option_code': 'AP'})
        save_answer('test@example.com', 2, {'selected_option_code': 'ET'})

        result = delete_answer('test@example.com', 1)
        assert result is True

        answers = load_answers('test@example.com')
        assert '1' not in answers
        assert '2' in answers

    def test_returns_false_for_nonexistent_answer(self, mock_pdn_file_path):
        """Should return False when answer doesn't exist."""
        save_answer('test@example.com', 1, {'selected_option_code': 'AP'})
        result = delete_answer('test@example.com', 99)
        assert result is False


class TestSaveUserMetadata:
    """Tests for save_user_metadata()."""

    def test_stores_metadata(self, mock_pdn_file_path):
        """Should store metadata in the answers file."""
        with patch('app.utils.answer_storage.UserMetadataHandler') as mock_handler:
            mock_handler.return_value.append_user_metadata.return_value = True
            save_user_metadata({'name': 'Test', 'email': 'test@example.com'}, email='test@example.com')

        answers = load_answers('test@example.com')
        assert answers is not None
        assert 'metadata' in answers
        assert answers['metadata']['name'] == 'Test'

    def test_requires_email(self, mock_pdn_file_path):
        """Should raise ValueError when email is missing."""
        with pytest.raises(ValueError, match="Email is required"):
            save_user_metadata({'name': 'Test'}, email=None)

    def test_adds_timestamp(self, mock_pdn_file_path):
        """Should add timestamp to metadata."""
        with patch('app.utils.answer_storage.UserMetadataHandler') as mock_handler:
            mock_handler.return_value.append_user_metadata.return_value = True
            save_user_metadata({'name': 'Test'}, email='test@example.com')

        answers = load_answers('test@example.com')
        assert 'timestamp' in answers['metadata']
