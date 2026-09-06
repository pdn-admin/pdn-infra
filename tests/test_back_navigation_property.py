"""Property tests for back navigation.

**Validates: Requirements 3.1, 3.2, 3.4**

Property 5: Back button visibility follows history — visible when
questionHistory.length > 0, hidden when questionHistory.length === 0.
For any question number > 1 with a non-empty history, the button should
be visible. For question 1 with empty history, it should be hidden.

Property 6: Back navigation restores previous question — clicking back
navigates to the most recent history entry's questionNumber and removes
it from the stack.
"""

from dataclasses import dataclass
from typing import List

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st


# --- Python replication of client-side back navigation logic ---

@dataclass
class HistoryEntry:
    """Represents a single entry in the question history stack."""
    questionNumber: int
    selectedAnswer: str


def is_back_button_visible(question_history: List[HistoryEntry]) -> bool:
    """Python equivalent of the back button visibility logic:

    backButton.classList.toggle('hidden', questionHistory.length === 0);

    The back button is visible (not hidden) when questionHistory.length > 0,
    and hidden when questionHistory.length === 0.
    """
    return len(question_history) > 0


def go_back(question_history: List[HistoryEntry], current_question: int):
    """Python equivalent of the goBack() function logic:

    if (questionHistory.length > 0) {
        const historyEntry = questionHistory.pop();
        currentQuestion = historyEntry.questionNumber;
        pendingSelectedAnswer = historyEntry.selectedAnswer;
        loadQuestion(currentQuestion);
    }

    Returns (new_current_question, pending_selected_answer, updated_history)
    or None if history is empty.
    """
    if len(question_history) == 0:
        return None

    history_copy = list(question_history)
    history_entry = history_copy.pop()
    new_current_question = history_entry.questionNumber
    pending_selected_answer = history_entry.selectedAnswer
    return (new_current_question, pending_selected_answer, history_copy)


# --- Hypothesis strategies ---

# Valid question numbers for binary questions (PartA: 1-26)
binary_question_number = st.integers(min_value=1, max_value=26)

# Valid question numbers for any question (1-67)
any_question_number = st.integers(min_value=1, max_value=67)

# Answer codes used in binary questions
answer_code = st.sampled_from(['AP', 'BP', 'CP', 'DP', 'EP', 'FP',
                               'AS', 'BS', 'CS', 'DS', 'ES', 'FS'])

# A single history entry with valid question number and answer
history_entry_strategy = st.builds(
    HistoryEntry,
    questionNumber=binary_question_number,
    selectedAnswer=answer_code
)

# A non-empty history stack (at least 1 entry)
non_empty_history = st.lists(history_entry_strategy, min_size=1, max_size=25)

# An empty history stack
empty_history = st.just([])

# Any history stack (empty or non-empty)
any_history = st.lists(history_entry_strategy, min_size=0, max_size=25)


class TestBackButtonVisibility:
    """Property 5: Back button visibility follows history.

    **Validates: Requirements 3.1, 3.4**

    The back button is visible when questionHistory.length > 0 (question > 1
    with history), and hidden when questionHistory.length === 0 (question 1
    with empty history).
    """

    @given(history=non_empty_history, current_question=st.integers(min_value=2, max_value=26))
    @settings(max_examples=100, deadline=None)
    def test_back_button_visible_with_non_empty_history(self, history, current_question):
        """Property: For any question number > 1 with a non-empty history,
        the back button shall be visible.

        **Validates: Requirements 3.1**
        """
        visible = is_back_button_visible(history)
        assert visible is True, (
            f"Back button should be visible when history has {len(history)} entries "
            f"and current question is {current_question}"
        )

    @given(current_question=st.just(1))
    @settings(max_examples=10, deadline=None)
    def test_back_button_hidden_on_question_1_with_empty_history(self, current_question):
        """Property: For question 1 with empty history, the back button
        shall be hidden.

        **Validates: Requirements 3.4**
        """
        empty = []
        visible = is_back_button_visible(empty)
        assert visible is False, (
            "Back button should be hidden when history is empty (question 1)"
        )

    @given(history=any_history)
    @settings(max_examples=100, deadline=None)
    def test_visibility_determined_solely_by_history_length(self, history):
        """Property: Back button visibility is determined solely by whether
        the history stack is empty or not.

        **Validates: Requirements 3.1, 3.4**
        """
        visible = is_back_button_visible(history)
        if len(history) > 0:
            assert visible is True, (
                "Back button should be visible when history is non-empty"
            )
        else:
            assert visible is False, (
                "Back button should be hidden when history is empty"
            )

    def test_example_question_1_no_history(self):
        """Example: On question 1 with no history, back button is hidden."""
        assert is_back_button_visible([]) is False

    def test_example_question_2_with_history(self):
        """Example: On question 2 with one history entry, back button is visible."""
        history = [HistoryEntry(questionNumber=1, selectedAnswer='AP')]
        assert is_back_button_visible(history) is True

    def test_example_question_5_with_history(self):
        """Example: On question 5 with multiple history entries, back button is visible."""
        history = [
            HistoryEntry(questionNumber=1, selectedAnswer='AP'),
            HistoryEntry(questionNumber=2, selectedAnswer='BP'),
            HistoryEntry(questionNumber=3, selectedAnswer='AP'),
            HistoryEntry(questionNumber=4, selectedAnswer='CP'),
        ]
        assert is_back_button_visible(history) is True


class TestBackNavigationRestoresPreviousQuestion:
    """Property 6: Back navigation restores previous question.

    **Validates: Requirements 3.2**

    For any history stack with at least one entry, going back should navigate
    to the most recent entry's questionNumber and remove it from the stack.
    """

    @given(history=non_empty_history, current_question=st.integers(min_value=2, max_value=67))
    @settings(max_examples=100, deadline=None)
    def test_back_navigates_to_most_recent_history_entry(self, history, current_question):
        """Property: Clicking back navigates to the most recent history
        entry's questionNumber.

        **Validates: Requirements 3.2**
        """
        expected_question = history[-1].questionNumber

        result = go_back(history, current_question)
        assert result is not None, "go_back should not return None with non-empty history"

        new_question, _, _ = result
        assert new_question == expected_question, (
            f"After going back, current question should be {expected_question} "
            f"(last history entry) but got {new_question}"
        )

    @given(history=non_empty_history, current_question=st.integers(min_value=2, max_value=67))
    @settings(max_examples=100, deadline=None)
    def test_back_removes_last_entry_from_history(self, history, current_question):
        """Property: Going back removes the most recent entry from the
        history stack.

        **Validates: Requirements 3.2**
        """
        original_length = len(history)

        result = go_back(history, current_question)
        assert result is not None

        _, _, updated_history = result
        assert len(updated_history) == original_length - 1, (
            f"History should have {original_length - 1} entries after going back, "
            f"but has {len(updated_history)}"
        )

    @given(history=non_empty_history, current_question=st.integers(min_value=2, max_value=67))
    @settings(max_examples=100, deadline=None)
    def test_back_preserves_remaining_history(self, history, current_question):
        """Property: Going back preserves all history entries except the
        last one (which was popped).

        **Validates: Requirements 3.2**
        """
        result = go_back(history, current_question)
        assert result is not None

        _, _, updated_history = result
        # The remaining history should be all entries except the last
        expected_remaining = history[:-1]
        assert len(updated_history) == len(expected_remaining)
        for i, entry in enumerate(updated_history):
            assert entry.questionNumber == expected_remaining[i].questionNumber
            assert entry.selectedAnswer == expected_remaining[i].selectedAnswer

    @given(history=non_empty_history, current_question=st.integers(min_value=2, max_value=67))
    @settings(max_examples=100, deadline=None)
    def test_back_restores_selected_answer(self, history, current_question):
        """Property: Going back restores the previously selected answer
        from the history entry.

        **Validates: Requirements 3.2**
        """
        expected_answer = history[-1].selectedAnswer

        result = go_back(history, current_question)
        assert result is not None

        _, pending_answer, _ = result
        assert pending_answer == expected_answer, (
            f"After going back, pending selected answer should be "
            f"'{expected_answer}' but got '{pending_answer}'"
        )

    @given(current_question=st.integers(min_value=1, max_value=67))
    @settings(max_examples=20, deadline=None)
    def test_back_does_nothing_with_empty_history(self, current_question):
        """Property: Going back with empty history has no effect (returns None).

        **Validates: Requirements 3.4**
        """
        result = go_back([], current_question)
        assert result is None, (
            "go_back should return None when history is empty"
        )

    def test_example_single_entry_back(self):
        """Example: Going back with one history entry navigates to that question."""
        history = [HistoryEntry(questionNumber=3, selectedAnswer='AP')]
        result = go_back(history, current_question=4)
        assert result is not None
        new_q, answer, remaining = result
        assert new_q == 3
        assert answer == 'AP'
        assert remaining == []

    def test_example_multiple_entries_back(self):
        """Example: Going back pops only the last entry."""
        history = [
            HistoryEntry(questionNumber=1, selectedAnswer='AP'),
            HistoryEntry(questionNumber=2, selectedAnswer='BP'),
            HistoryEntry(questionNumber=3, selectedAnswer='CP'),
        ]
        result = go_back(history, current_question=4)
        assert result is not None
        new_q, answer, remaining = result
        assert new_q == 3
        assert answer == 'CP'
        assert len(remaining) == 2
        assert remaining[-1].questionNumber == 2
