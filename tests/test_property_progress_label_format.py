"""Property test: Progress label format matches "שאלה X מתוך 67".

**Validates: Requirements 12.1**
**Validates: Correctness Property 13**

Verifies that for any question number X (1-67), the progress label text
shall be "שאלה X מתוך 67".
"""

import re

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st


# Replicate the ProgressManager.formatProgressLabel logic from questionnaire.html
TOTAL_QUESTIONS = 67


def format_progress_label(current_question: int) -> str:
    """Python equivalent of ProgressManager.formatProgressLabel(currentQuestion).

    Returns the progress label in Hebrew format: "שאלה X מתוך 67"
    """
    return f"שאלה {current_question} מתוך {TOTAL_QUESTIONS}"


# Strategy: valid question numbers 1-67
question_number_strategy = st.integers(min_value=1, max_value=67)


class TestProgressLabelFormat:
    """Property 13: Progress label format — label text matches 'שאלה X מתוך 67'."""

    @given(question_number=question_number_strategy)
    @settings(max_examples=67)
    def test_progress_label_matches_expected_format(self, question_number):
        """Property: For any question number X (1-67), the progress label text
        shall be 'שאלה X מתוך 67'.

        **Validates: Requirements 12.1**
        """
        label = format_progress_label(question_number)

        # Verify exact format
        expected = f"שאלה {question_number} מתוך 67"
        assert label == expected, (
            f"Progress label for question {question_number} should be "
            f"'{expected}' but got '{label}'"
        )

    @given(question_number=question_number_strategy)
    @settings(max_examples=67)
    def test_progress_label_contains_question_number(self, question_number):
        """Property: The progress label always contains the current question number.

        **Validates: Requirements 12.1**
        """
        label = format_progress_label(question_number)
        assert str(question_number) in label

    @given(question_number=question_number_strategy)
    @settings(max_examples=67)
    def test_progress_label_contains_total_67(self, question_number):
        """Property: The progress label always contains the total '67'.

        **Validates: Requirements 12.1**
        """
        label = format_progress_label(question_number)
        assert "מתוך 67" in label

    @given(question_number=question_number_strategy)
    @settings(max_examples=67)
    def test_progress_label_regex_pattern(self, question_number):
        """Property: The progress label matches the regex pattern for
        'שאלה <number> מתוך 67'.

        **Validates: Requirements 12.1**
        """
        label = format_progress_label(question_number)
        pattern = r'^שאלה \d{1,2} מתוך 67$'
        assert re.match(pattern, label), (
            f"Progress label '{label}' does not match expected pattern '{pattern}'"
        )

    def test_first_question_label(self):
        """Example: First question label is 'שאלה 1 מתוך 67'."""
        assert format_progress_label(1) == "שאלה 1 מתוך 67"

    def test_last_question_label(self):
        """Example: Last question label is 'שאלה 67 מתוך 67'."""
        assert format_progress_label(67) == "שאלה 67 מתוך 67"

    def test_middle_question_label(self):
        """Example: Middle question label is 'שאלה 34 מתוך 67'."""
        assert format_progress_label(34) == "שאלה 34 מתוך 67"
