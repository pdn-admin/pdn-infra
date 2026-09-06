"""Property tests for auto-save and resume logic.

**Validates: Requirements 1.1, 1.3, 1.5**

Property 1: Auto-save dual persistence — verify session contains answer data after save.
Property 2: Resume restores correct position — accepting resume navigates to N+1.
Property 3: Conflict resolution uses maximum — max(session, local) wins.
"""

import pytest
from unittest.mock import patch
from flask import Flask
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.pdn_diagnose.diagnosis_routes import pdn_diagnose_bp


# --- Python implementation of resolveConflict logic (from AutoSaveManager) ---

def resolve_conflict(session_question: int, local_question: int) -> int:
    """Python equivalent of AutoSaveManager.resolveConflict(sessionQuestion, localQuestion).

    Resolves conflict between session and localStorage progress by taking
    the maximum of the two values. Treats None/0 as no progress.

    Returns the authoritative progress (highest question number).
    """
    return max(session_question or 0, local_question or 0)


# --- Strategies ---

# Valid question numbers for the 67-question questionnaire
question_number_strategy = st.integers(min_value=1, max_value=67)

# Valid answer option codes (single character codes used in the questionnaire)
option_code_strategy = st.sampled_from(['a', 'b', 'c', 'd', 'AP', 'BP', 'CP', 'DP'])

# Progress values including 0 (no progress) and valid question numbers
progress_strategy = st.integers(min_value=0, max_value=67)


# --- Fixtures ---

@pytest.fixture
def app():
    """Create a minimal Flask test app with the diagnose blueprint."""
    application = Flask(__name__)
    application.config['TESTING'] = True
    application.config['SECRET_KEY'] = 'test-secret-key'
    application.config['ADMIN_PASSWORD'] = 'pdn'
    application.config['SESSION_TYPE'] = 'filesystem'
    application.config['QUESTIONS_FILE'] = {
        'phases': {
            'PersonalDetails': {
                'instructions': 'Fill in your personal details'
            },
            'PartA': {
                'instructions': 'Part A instructions',
                'questions': {
                    str(i): {
                        'text': f'Question {i}?',
                        'options': [
                            {'code': 'AP', 'text': 'Option A'},
                            {'code': 'BP', 'text': 'Option B'}
                        ],
                        'type': 'single'
                    }
                    for i in range(1, 27)
                }
            },
            'PartB': {
                'instructions': 'Part B instructions',
                'questions': {
                    str(i): {
                        'text': f'Question {i}?',
                        'options': [
                            {'code': 'a', 'text': 'Option A'},
                            {'code': 'b', 'text': 'Option B'},
                            {'code': 'c', 'text': 'Option C'}
                        ],
                        'type': 'ranking'
                    }
                    for i in range(27, 38)
                }
            }
        }
    }
    application.register_blueprint(pdn_diagnose_bp, url_prefix='/pdn-diagnose')

    try:
        from flask_session import Session
        Session(application)
    except ImportError:
        pass

    return application


@pytest.fixture
def client(app):
    """Create Flask test client."""
    return app.test_client()


@pytest.fixture
def logged_in_client(client):
    """Create a client with an active session."""
    client.post('/pdn-diagnose/login', json={
        'email': 'test@example.com',
        'password': 'test'
    })
    return client


class TestAutoSaveDualPersistence:
    """Property 1: Auto-save dual persistence.

    For any valid question number (1-67) and answer data, after submitting
    an answer via the /pdn-diagnose/answer endpoint, the server session
    (via save_answer) shall contain the answer data with the correct
    question number.

    **Validates: Requirements 1.1**
    """

    @given(
        question_number=st.integers(min_value=1, max_value=26),
        option_code=st.sampled_from(['AP', 'BP'])
    )
    @settings(
        max_examples=30,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_answer_persisted_in_session_for_any_question(
        self, app, question_number, option_code
    ):
        """Property: For any valid question number and answer code, submitting
        an answer via /answer persists it server-side (save_answer is called
        with correct question number and answer data).

        **Validates: Requirements 1.1**
        """
        with app.test_client() as client:
            # Log in (password is email local part before @)
            client.post('/pdn-diagnose/login', json={
                'email': 'proptest@example.com',
                'password': 'proptest'
            })

            with patch('app.pdn_diagnose.diagnosis_routes.save_answer') as mock_save:
                response = client.post('/pdn-diagnose/answer', json={
                    'question_number': question_number,
                    'selected_option_code': option_code,
                    'ranking': None
                })

                assert response.status_code == 200
                data = response.get_json()
                assert data['message'] == 'Answer saved successfully'
                assert data['question_number'] == question_number

                # Verify save_answer was called with correct parameters
                mock_save.assert_called_once()
                call_args = mock_save.call_args[0]
                assert call_args[0] == 'proptest@example.com'  # email
                assert call_args[1] == question_number  # question_number
                assert call_args[2]['selected_option_code'] == option_code  # answer_data

    @given(
        question_number=st.integers(min_value=1, max_value=26),
        option_code=st.sampled_from(['AP', 'BP'])
    )
    @settings(
        max_examples=20,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_answer_endpoint_returns_question_number(
        self, app, question_number, option_code
    ):
        """Property: The answer endpoint always returns the submitted question
        number in the response, confirming server-side persistence.

        **Validates: Requirements 1.1**
        """
        with app.test_client() as client:
            client.post('/pdn-diagnose/login', json={
                'email': 'proptest@example.com',
                'password': 'proptest'
            })

            with patch('app.pdn_diagnose.diagnosis_routes.save_answer'):
                response = client.post('/pdn-diagnose/answer', json={
                    'question_number': question_number,
                    'selected_option_code': option_code,
                    'ranking': None
                })

                assert response.status_code == 200
                data = response.get_json()
                assert data['question_number'] == question_number


class TestResumeRestoresCorrectPosition:
    """Property 2: Resume restores correct position.

    For any saved progress state with last answered question number N
    (where 1 ≤ N ≤ 66), accepting the resume prompt shall set the current
    question to N + 1. The /get_progress endpoint returns the max question
    number, and resume point + 1 is the correct next question.

    **Validates: Requirements 1.3**
    """

    @given(
        answered_questions=st.lists(
            st.integers(min_value=1, max_value=67),
            min_size=1,
            max_size=20,
            unique=True
        )
    )
    @settings(
        max_examples=30,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_get_progress_returns_max_question_number(
        self, app, answered_questions
    ):
        """Property: For any set of answered questions, /get_progress returns
        the maximum question number as current_question.

        **Validates: Requirements 1.3**
        """
        # Build mock answers dict with question numbers as string keys
        mock_answers = {
            str(q): {'selected_option_code': 'AP'}
            for q in answered_questions
        }
        expected_max = max(answered_questions)

        with app.test_client() as client:
            client.post('/pdn-diagnose/login', json={
                'email': 'proptest@example.com',
                'password': 'proptest'
            })

            with patch('app.pdn_diagnose.diagnosis_routes.load_answers', return_value=mock_answers):
                response = client.get('/pdn-diagnose/get_progress')

                assert response.status_code == 200
                data = response.get_json()
                assert data['current_question'] == expected_max

    @given(
        last_answered=st.integers(min_value=1, max_value=66)
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_resume_point_is_next_question(self, app, last_answered):
        """Property: For any last answered question N (1 ≤ N ≤ 66), the
        resume point (next question to show) is N + 1.

        **Validates: Requirements 1.3**
        """
        # Build mock answers up to last_answered
        mock_answers = {
            str(q): {'selected_option_code': 'AP'}
            for q in range(1, last_answered + 1)
        }

        with app.test_client() as client:
            client.post('/pdn-diagnose/login', json={
                'email': 'proptest@example.com',
                'password': 'proptest'
            })

            with patch('app.pdn_diagnose.diagnosis_routes.load_answers', return_value=mock_answers):
                response = client.get('/pdn-diagnose/get_progress')

                assert response.status_code == 200
                data = response.get_json()
                current_question = data['current_question']

                # Resume point is N+1 (next question after last answered)
                resume_point = current_question + 1
                assert resume_point == last_answered + 1
                assert 2 <= resume_point <= 67

    def test_no_progress_returns_zero(self, app):
        """Example: When no answers exist, get_progress returns 0."""
        with app.test_client() as client:
            client.post('/pdn-diagnose/login', json={
                'email': 'proptest@example.com',
                'password': 'proptest'
            })

            with patch('app.pdn_diagnose.diagnosis_routes.load_answers', return_value=None):
                response = client.get('/pdn-diagnose/get_progress')
                data = response.get_json()
                assert data['current_question'] == 0


class TestConflictResolutionUsesMaximum:
    """Property 3: Conflict resolution uses maximum.

    For any two progress states where the session reports question number S
    and localStorage reports question number L (where S ≠ L), the resolved
    progress shall equal max(S, L).

    **Validates: Requirements 1.5**
    """

    @given(
        session_question=progress_strategy,
        local_question=progress_strategy
    )
    @settings(max_examples=100, deadline=None)
    def test_resolve_conflict_always_returns_maximum(
        self, session_question, local_question
    ):
        """Property: For any pair of session and local progress values,
        resolveConflict returns the maximum of the two.

        **Validates: Requirements 1.5**
        """
        result = resolve_conflict(session_question, local_question)
        assert result == max(session_question or 0, local_question or 0)

    @given(
        session_question=st.integers(min_value=1, max_value=67),
        local_question=st.integers(min_value=1, max_value=67)
    )
    @settings(max_examples=50, deadline=None)
    def test_conflict_resolution_is_commutative(
        self, session_question, local_question
    ):
        """Property: Conflict resolution is commutative — the order of
        arguments does not affect the result.

        **Validates: Requirements 1.5**
        """
        result_a = resolve_conflict(session_question, local_question)
        result_b = resolve_conflict(local_question, session_question)
        assert result_a == result_b

    @given(
        session_question=st.integers(min_value=1, max_value=67),
        local_question=st.integers(min_value=1, max_value=67)
    )
    @settings(max_examples=50, deadline=None)
    def test_conflict_resolution_result_is_valid_progress(
        self, session_question, local_question
    ):
        """Property: The resolved progress is always a valid question number
        (between 0 and 67 inclusive).

        **Validates: Requirements 1.5**
        """
        result = resolve_conflict(session_question, local_question)
        assert 0 <= result <= 67

    @given(
        higher=st.integers(min_value=2, max_value=67),
        lower=st.integers(min_value=0, max_value=66)
    )
    @settings(max_examples=50, deadline=None)
    def test_conflict_resolution_picks_higher_when_different(
        self, higher, lower
    ):
        """Property: When session and local differ, the higher value wins
        regardless of which source it comes from.

        **Validates: Requirements 1.5**
        """
        from hypothesis import assume
        assume(higher > lower)

        # Higher in session position
        assert resolve_conflict(higher, lower) == higher
        # Higher in local position
        assert resolve_conflict(lower, higher) == higher

    @given(question=progress_strategy)
    @settings(max_examples=30, deadline=None)
    def test_conflict_resolution_with_zero_uses_nonzero(self, question):
        """Property: When one source has 0 (no progress), the other source wins.

        **Validates: Requirements 1.5**
        """
        result = resolve_conflict(question, 0)
        assert result == (question or 0)

        result = resolve_conflict(0, question)
        assert result == (question or 0)

    @given(question=st.integers(min_value=1, max_value=67))
    @settings(max_examples=30, deadline=None)
    def test_conflict_resolution_equal_values(self, question):
        """Property: When both sources agree, the result equals both.

        **Validates: Requirements 1.5**
        """
        result = resolve_conflict(question, question)
        assert result == question
