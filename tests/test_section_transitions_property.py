"""Property test: Phase transition triggers instruction modal.

**Validates: Requirements 6.1**

Property 9: When the user transitions from one question phase to another
(e.g., PartA to PartB), the instruction modal shall be displayed with the
instructions text from questions.json for that phase. This is verified by
checking that the API response for phase boundary questions includes a
non-empty `instructions` field.
"""

import pytest
from flask import Flask
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.pdn_diagnose.diagnosis_routes import pdn_diagnose_bp
from app.utils.questionnaire import get_question


# Phase boundaries based on actual questionnaire.py logic:
# PartA: 1-26, PartB: 27-37, PartC: 38-42, PartD: 43-56, PartE: 57-61, PartF: 62-67
PHASE_BOUNDARIES = {
    27: ("PartA", "PartB"),
    38: ("PartB", "PartC"),
    43: ("PartC", "PartD"),
    57: ("PartD", "PartE"),
    62: ("PartE", "PartF"),
}

# All valid question numbers and their phases
PHASE_RANGES = [
    (range(1, 27), "PartA"),
    (range(27, 38), "PartB"),
    (range(38, 43), "PartC"),
    (range(43, 57), "PartD"),
    (range(57, 62), "PartE"),
    (range(62, 68), "PartF"),
]


def get_phase_for_question(question_number: int) -> str:
    """Determine the phase for a given question number."""
    if 1 <= question_number <= 26:
        return "PartA"
    elif 27 <= question_number <= 37:
        return "PartB"
    elif 38 <= question_number <= 42:
        return "PartC"
    elif 43 <= question_number <= 56:
        return "PartD"
    elif 57 <= question_number <= 61:
        return "PartE"
    elif 62 <= question_number <= 67:
        return "PartF"
    return ""


def is_phase_boundary(question_number: int) -> bool:
    """Check if a question is the first in a new phase (phase differs from previous)."""
    if question_number <= 1:
        return False
    current_phase = get_phase_for_question(question_number)
    previous_phase = get_phase_for_question(question_number - 1)
    return current_phase != previous_phase and current_phase != ""


@pytest.fixture
def questions_data():
    """Provide a complete questions data structure with all phases and instructions."""
    return {
        'phases': {
            'PersonalDetails': {
                'instructions': 'Personal details instructions'
            },
            'PartA': {
                'instructions': 'בחר את מה שהכי מייצג אותך.',
                'questions': {str(i): {
                    'text': f'PartA question {i}',
                    'options': [
                        {'code': 'a', 'text': 'Option A'},
                        {'code': 'b', 'text': 'Option B'}
                    ],
                    'type': 'single'
                } for i in range(1, 27)}
            },
            'PartB': {
                'instructions': 'דרג את האפשרויות לפי סדר עדיפות.',
                'questions': {str(i): {
                    'text': f'PartB question {i}',
                    'options': [
                        {'code': 'a', 'text': 'Option A'},
                        {'code': 'b', 'text': 'Option B'},
                        {'code': 'c', 'text': 'Option C'}
                    ],
                    'type': 'ranking'
                } for i in range(27, 38)}
            },
            'PartC': {
                'instructions': 'סמן את מיקומך על הסקאלה.',
                'questions': {str(i): {
                    'text': f'PartC question {i}',
                    'options': [
                        {'code': 'a', 'text': 'Left endpoint'},
                        {'code': 'b', 'text': 'Right endpoint'}
                    ],
                    'type': 'scale'
                } for i in range(38, 43)}
            },
            'PartD': {
                'instructions': 'סמן את מיקומך על הסקאלה בחלק ד.',
                'questions': {str(i): {
                    'text': f'PartD question {i}',
                    'options': [
                        {'code': 'a', 'text': 'Left endpoint'},
                        {'code': 'b', 'text': 'Right endpoint'}
                    ],
                    'type': 'scale'
                } for i in range(43, 57)}
            },
            'PartE': {
                'instructions': 'דרג את האפשרויות בחלק ה.',
                'questions': {str(i): {
                    'text': f'PartE question {i}',
                    'options': [
                        {'code': 'a', 'text': 'Option A'},
                        {'code': 'b', 'text': 'Option B'},
                        {'code': 'c', 'text': 'Option C'}
                    ],
                    'type': 'ranking'
                } for i in range(57, 62)}
            },
            'PartF': {
                'instructions': 'בחר תשובה אחת בחלק ו.',
                'questions': {str(i): {
                    'text': f'PartF question {i}',
                    'options': [
                        {'code': 'a', 'text': 'Option A'},
                        {'code': 'b', 'text': 'Option B'},
                        {'code': 'c', 'text': 'Option C'}
                    ],
                    'type': 'single'
                } for i in range(62, 68)}
            }
        }
    }


@pytest.fixture
def app(questions_data):
    """Create a minimal Flask test app with the diagnose blueprint."""
    application = Flask(__name__)
    application.config['TESTING'] = True
    application.config['SECRET_KEY'] = 'test-secret-key'
    application.config['ADMIN_PASSWORD'] = 'pdn'
    application.config['SESSION_TYPE'] = 'filesystem'
    application.config['QUESTIONS_FILE'] = questions_data
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
        'password': 'pdn'
    })
    with client.session_transaction() as sess:
        sess['user_data'] = {'first_name': 'Test'}
    return client


# Strategy for phase boundary question numbers
phase_boundary_strategy = st.sampled_from(list(PHASE_BOUNDARIES.keys()))


class TestPhaseTransitionTriggersInstructionModal:
    """Property 9: Phase transition triggers instruction modal.

    For any question that is the first in a new phase (where the phase differs
    from the previous question's phase), the API response shall include a
    non-empty `instructions` field containing the phase instructions text.

    **Validates: Requirements 6.1**
    """

    @given(boundary_question=phase_boundary_strategy)
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_phase_boundary_returns_instructions(self, app, boundary_question):
        """Property: For any phase boundary question, the API response includes
        non-empty instructions text.

        **Validates: Requirements 6.1**
        """
        with app.test_client() as client:
            response = client.get(f'/pdn-diagnose/questionnaire/{boundary_question}')
            assert response.status_code == 200

            data = response.get_json()
            assert 'instructions' in data, (
                f"Question {boundary_question} (phase boundary) response "
                f"should include 'instructions' field"
            )
            assert data['instructions'] is not None and len(data['instructions']) > 0, (
                f"Question {boundary_question} (phase boundary) should have "
                f"non-empty instructions text, got: '{data.get('instructions')}'"
            )

    @given(boundary_question=phase_boundary_strategy)
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_phase_boundary_stage_differs_from_previous(self, app, boundary_question):
        """Property: For any phase boundary question, its stage differs from
        the previous question's stage.

        **Validates: Requirements 6.1**
        """
        with app.test_client() as client:
            # Get the boundary question
            response = client.get(f'/pdn-diagnose/questionnaire/{boundary_question}')
            assert response.status_code == 200
            current_data = response.get_json()

            # Get the previous question
            prev_response = client.get(f'/pdn-diagnose/questionnaire/{boundary_question - 1}')
            assert prev_response.status_code == 200
            prev_data = prev_response.get_json()

            assert current_data['stage'] != prev_data['stage'], (
                f"Question {boundary_question} should be in a different phase "
                f"than question {boundary_question - 1}. "
                f"Both are in '{current_data['stage']}'"
            )

    @given(
        boundary_question=phase_boundary_strategy,
        prev_offset=st.integers(min_value=1, max_value=5)
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_instructions_match_phase(self, app, questions_data, boundary_question, prev_offset):
        """Property: The instructions returned for a phase boundary question
        match the instructions defined for that phase in questions.json.

        **Validates: Requirements 6.1**
        """
        with app.test_client() as client:
            response = client.get(f'/pdn-diagnose/questionnaire/{boundary_question}')
            assert response.status_code == 200

            data = response.get_json()
            phase = data['stage']

            expected_instructions = questions_data['phases'][phase]['instructions']
            assert data['instructions'] == expected_instructions, (
                f"Question {boundary_question} instructions should match "
                f"phase '{phase}' instructions from questions.json. "
                f"Expected: '{expected_instructions}', Got: '{data['instructions']}'"
            )

    @given(question_number=st.integers(min_value=1, max_value=67))
    @settings(
        max_examples=67,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_all_questions_include_instructions_field(self, app, question_number):
        """Property: Every valid question response includes an instructions field.
        The frontend uses this to determine whether to show the instruction modal
        on phase transitions.

        **Validates: Requirements 6.1**
        """
        with app.test_client() as client:
            response = client.get(f'/pdn-diagnose/questionnaire/{question_number}')
            assert response.status_code == 200

            data = response.get_json()
            assert 'instructions' in data, (
                f"Question {question_number} response should include "
                f"'instructions' field for phase transition detection"
            )

    def test_all_known_boundaries_have_instructions(self, logged_in_client):
        """Example: All known phase boundary questions return non-empty instructions."""
        for boundary_q, (from_phase, to_phase) in PHASE_BOUNDARIES.items():
            response = logged_in_client.get(f'/pdn-diagnose/questionnaire/{boundary_q}')
            assert response.status_code == 200

            data = response.get_json()
            assert data['stage'] == to_phase, (
                f"Question {boundary_q} should be in phase '{to_phase}', "
                f"got '{data['stage']}'"
            )
            assert data['instructions'], (
                f"Question {boundary_q} (first of {to_phase}) should have "
                f"non-empty instructions"
            )

    def test_non_boundary_same_phase_as_previous(self, logged_in_client):
        """Example: Non-boundary questions share the same phase as their predecessor."""
        non_boundary_questions = [2, 10, 26, 30, 40, 50, 60, 65]
        for q in non_boundary_questions:
            response = logged_in_client.get(f'/pdn-diagnose/questionnaire/{q}')
            prev_response = logged_in_client.get(f'/pdn-diagnose/questionnaire/{q - 1}')

            data = response.get_json()
            prev_data = prev_response.get_json()

            assert data['stage'] == prev_data['stage'], (
                f"Question {q} and {q-1} should be in the same phase, "
                f"but got '{data['stage']}' and '{prev_data['stage']}'"
            )
