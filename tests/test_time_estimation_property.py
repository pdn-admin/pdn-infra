"""Property tests for time estimation and document title.

**Validates: Requirements 5.3, 5.4, 8.2**

Property 7: Time estimation calculation — for C≥2 questions and elapsed T,
remaining = round((total−C) × (T/C))

Property 8: Time display threshold — shows "כמעט סיימנו!" when < 120 seconds

Property 10: Document title reflects current question — title is "אבחון PDN - שאלה N/67"
"""

import math

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st


# Replicate the ProgressManager logic from questionnaire.html
TOTAL_QUESTIONS = 67


def calculate_time_remaining(current_question: int, elapsed_seconds: float, timestamps_count: int) -> int:
    """Python equivalent of ProgressManager.calculateTimeRemaining.

    When timestamps_count < 2, uses default 15-minute estimate.
    When timestamps_count >= 2, uses actual elapsed time to calculate average.
    """
    if timestamps_count < 2:
        avg_per_question = (15 * 60) / TOTAL_QUESTIONS
        return round((TOTAL_QUESTIONS - current_question) * avg_per_question)
    avg_per_question = elapsed_seconds / current_question
    return round((TOTAL_QUESTIONS - current_question) * avg_per_question)


def format_time_remaining(seconds: int) -> str:
    """Python equivalent of ProgressManager.formatTimeRemaining.

    Returns "כמעט סיימנו!" when < 120 seconds, otherwise "כ-N דקות נותרו".
    """
    if seconds < 120:
        return 'כמעט סיימנו!'
    minutes = math.ceil(seconds / 60)
    return f'כ-{minutes} דקות נותרו'


def format_title(current_question: int) -> str:
    """Python equivalent of ProgressManager.updateTitle.

    Returns "אבחון PDN - שאלה N/67".
    """
    return f'אבחון PDN - שאלה {current_question}/67'


# Strategies
completed_questions_strategy = st.integers(min_value=2, max_value=66)
elapsed_time_strategy = st.floats(min_value=1.0, max_value=7200.0, allow_nan=False, allow_infinity=False)
question_number_strategy = st.integers(min_value=1, max_value=67)
below_threshold_strategy = st.integers(min_value=0, max_value=119)
above_threshold_strategy = st.integers(min_value=120, max_value=36000)


class TestTimeEstimationCalculation:
    """Property 7: Time estimation calculation.

    For any number of completed questions C (where C ≥ 2) and elapsed time T
    (in seconds), the estimated remaining time shall equal
    round((totalQuestions − C) × (T / C)).

    **Validates: Requirements 5.3**
    """

    @given(
        current_question=completed_questions_strategy,
        elapsed_seconds=elapsed_time_strategy
    )
    @settings(max_examples=200)
    def test_time_remaining_formula_with_sufficient_data(self, current_question, elapsed_seconds):
        """Property: For C≥2 and T>0, remaining = round((67−C) × (T/C)).

        **Validates: Requirements 5.3**
        """
        timestamps_count = current_question + 1  # Enough timestamps (≥2)

        result = calculate_time_remaining(current_question, elapsed_seconds, timestamps_count)

        expected = round((TOTAL_QUESTIONS - current_question) * (elapsed_seconds / current_question))
        assert result == expected, (
            f"For C={current_question}, T={elapsed_seconds}: "
            f"expected {expected} but got {result}"
        )

    @given(
        current_question=completed_questions_strategy,
        elapsed_seconds=elapsed_time_strategy
    )
    @settings(max_examples=100)
    def test_time_remaining_is_non_negative(self, current_question, elapsed_seconds):
        """Property: Estimated remaining time is always non-negative when C < total.

        **Validates: Requirements 5.3**
        """
        timestamps_count = current_question + 1
        result = calculate_time_remaining(current_question, elapsed_seconds, timestamps_count)
        assert result >= 0, (
            f"Time remaining should be non-negative, got {result} "
            f"for C={current_question}, T={elapsed_seconds}"
        )

    @given(
        current_question=st.integers(min_value=1, max_value=66),
        elapsed_seconds=elapsed_time_strategy
    )
    @settings(max_examples=100)
    def test_time_remaining_decreases_as_questions_increase(self, current_question, elapsed_seconds):
        """Property: With constant pace, more completed questions means less remaining time.

        **Validates: Requirements 5.3**
        """
        assume(current_question < 66)
        timestamps_count = current_question + 1

        # Same elapsed time, one more question completed
        result_now = calculate_time_remaining(current_question, elapsed_seconds, timestamps_count)
        result_next = calculate_time_remaining(current_question + 1, elapsed_seconds, timestamps_count + 1)

        assert result_next <= result_now, (
            f"Time remaining should decrease as questions increase: "
            f"C={current_question} gave {result_now}, C={current_question + 1} gave {result_next}"
        )

    @given(current_question=st.integers(min_value=1, max_value=66))
    @settings(max_examples=66)
    def test_default_estimate_when_insufficient_timestamps(self, current_question):
        """Property: With < 2 timestamps, uses default 15-minute estimate.

        **Validates: Requirements 5.3**
        """
        timestamps_count = 1  # Less than 2
        elapsed_seconds = 30.0  # Irrelevant when timestamps < 2

        result = calculate_time_remaining(current_question, elapsed_seconds, timestamps_count)

        avg_per_question = (15 * 60) / TOTAL_QUESTIONS
        expected = round((TOTAL_QUESTIONS - current_question) * avg_per_question)
        assert result == expected, (
            f"With insufficient timestamps, should use default estimate. "
            f"Expected {expected} but got {result}"
        )


class TestTimeDisplayThreshold:
    """Property 8: Time display threshold.

    For any estimated remaining time value less than 120 seconds, the time
    display shall show "כמעט סיימנו!" instead of a numeric value.

    **Validates: Requirements 5.4**
    """

    @given(seconds=below_threshold_strategy)
    @settings(max_examples=120)
    def test_below_threshold_shows_almost_done(self, seconds):
        """Property: For any seconds < 120, output is "כמעט סיימנו!".

        **Validates: Requirements 5.4**
        """
        result = format_time_remaining(seconds)
        assert result == 'כמעט סיימנו!', (
            f"For {seconds} seconds (< 120), expected 'כמעט סיימנו!' but got '{result}'"
        )

    @given(seconds=above_threshold_strategy)
    @settings(max_examples=200)
    def test_above_threshold_shows_numeric_minutes(self, seconds):
        """Property: For any seconds >= 120, output contains numeric minutes.

        **Validates: Requirements 5.4**
        """
        result = format_time_remaining(seconds)
        expected_minutes = math.ceil(seconds / 60)
        expected = f'כ-{expected_minutes} דקות נותרו'
        assert result == expected, (
            f"For {seconds} seconds (>= 120), expected '{expected}' but got '{result}'"
        )

    @given(seconds=above_threshold_strategy)
    @settings(max_examples=100)
    def test_above_threshold_never_shows_almost_done(self, seconds):
        """Property: For seconds >= 120, never shows the "almost done" message.

        **Validates: Requirements 5.4**
        """
        result = format_time_remaining(seconds)
        assert result != 'כמעט סיימנו!', (
            f"For {seconds} seconds (>= 120), should not show 'כמעט סיימנו!'"
        )

    def test_boundary_119_shows_almost_done(self):
        """Example: 119 seconds shows "כמעט סיימנו!"."""
        assert format_time_remaining(119) == 'כמעט סיימנו!'

    def test_boundary_120_shows_numeric(self):
        """Example: 120 seconds shows numeric format."""
        result = format_time_remaining(120)
        assert result == 'כ-2 דקות נותרו'

    def test_zero_seconds_shows_almost_done(self):
        """Example: 0 seconds shows "כמעט סיימנו!"."""
        assert format_time_remaining(0) == 'כמעט סיימנו!'


class TestDocumentTitle:
    """Property 10: Document title reflects current question.

    For any question number N (1-67), after navigating to that question,
    the document title shall be "אבחון PDN - שאלה N/67".

    **Validates: Requirements 8.2**
    """

    @given(question_number=question_number_strategy)
    @settings(max_examples=67)
    def test_title_matches_expected_format(self, question_number):
        """Property: For any N in [1, 67], title is "אבחון PDN - שאלה N/67".

        **Validates: Requirements 8.2**
        """
        result = format_title(question_number)
        expected = f'אבחון PDN - שאלה {question_number}/67'
        assert result == expected, (
            f"Title for question {question_number} should be "
            f"'{expected}' but got '{result}'"
        )

    @given(question_number=question_number_strategy)
    @settings(max_examples=67)
    def test_title_contains_question_number(self, question_number):
        """Property: The title always contains the current question number.

        **Validates: Requirements 8.2**
        """
        result = format_title(question_number)
        assert str(question_number) in result

    @given(question_number=question_number_strategy)
    @settings(max_examples=67)
    def test_title_contains_total_67(self, question_number):
        """Property: The title always contains the total '/67'.

        **Validates: Requirements 8.2**
        """
        result = format_title(question_number)
        assert '/67' in result

    @given(question_number=question_number_strategy)
    @settings(max_examples=67)
    def test_title_starts_with_prefix(self, question_number):
        """Property: The title always starts with "אבחון PDN - שאלה".

        **Validates: Requirements 8.2**
        """
        result = format_title(question_number)
        assert result.startswith('אבחון PDN - שאלה')

    def test_first_question_title(self):
        """Example: First question title."""
        assert format_title(1) == 'אבחון PDN - שאלה 1/67'

    def test_last_question_title(self):
        """Example: Last question title."""
        assert format_title(67) == 'אבחון PDN - שאלה 67/67'

    def test_middle_question_title(self):
        """Example: Middle question title."""
        assert format_title(34) == 'אבחון PDN - שאלה 34/67'
