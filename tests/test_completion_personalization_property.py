"""Property test: Completion message includes user name.

**Validates: Requirements 9.2**

Property 11: For any non-empty user first name string, the completion screen
congratulatory message shall contain that name.

The completion screen is rendered client-side in JavaScript (questionnaire.html).
The heading message is generated as:
    '🎉 כל הכבוד' + (firstName ? ', ' + firstName : '') + '!'

This test replicates the message generation logic in Python and verifies that
for any non-empty first name, the generated message always contains that name.
It also verifies that the hidden input `userName` in the template is populated
with the user's first name from the session.
"""

import pytest
from flask import Flask, session
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.pdn_diagnose.diagnosis_routes import pdn_diagnose_bp


def generate_completion_heading(first_name: str) -> str:
    """Python equivalent of the CompletionManager heading generation.

    Replicates the JavaScript logic:
        '🎉 כל הכבוד' + (firstName ? ', ' + firstName : '') + '!'
    """
    if first_name:
        return f"🎉 כל הכבוד, {first_name}!"
    return "🎉 כל הכבוד!"


# Strategy for valid first names: non-empty strings with Hebrew and English characters
# Mimics realistic user names that would be stored in the session
hebrew_name_chars = st.sampled_from(
    'אבגדהוזחטיכלמנסעפצקרשת'
)
english_name_chars = st.sampled_from(
    'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
)

# Strategy for Hebrew names (1-20 chars)
hebrew_name_strategy = st.text(
    alphabet=hebrew_name_chars,
    min_size=1,
    max_size=20
)

# Strategy for English names (1-20 chars)
english_name_strategy = st.text(
    alphabet=english_name_chars,
    min_size=1,
    max_size=20
)

# Combined strategy: either Hebrew or English names
name_strategy = st.one_of(hebrew_name_strategy, english_name_strategy)


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
            'PersonalDetails': {'instructions': 'Personal details'},
            'PartA': {
                'instructions': 'Part A instructions',
                'questions': {str(i): {
                    'text': f'Question {i}',
                    'options': [
                        {'code': 'a', 'text': 'Option A'},
                        {'code': 'b', 'text': 'Option B'}
                    ],
                    'type': 'single'
                } for i in range(1, 27)}
            },
            'PartB': {
                'instructions': 'Part B instructions',
                'questions': {str(i): {
                    'text': f'Question {i}',
                    'options': [
                        {'code': 'a', 'text': 'A'},
                        {'code': 'b', 'text': 'B'},
                        {'code': 'c', 'text': 'C'}
                    ],
                    'type': 'ranking'
                } for i in range(27, 38)}
            },
            'PartC': {
                'instructions': 'Part C instructions',
                'questions': {str(i): {
                    'text': f'Question {i}',
                    'options': [
                        {'code': 'L', 'text': 'Left'},
                        {'code': 'R', 'text': 'Right'}
                    ],
                    'type': 'scale'
                } for i in range(38, 43)}
            },
            'PartD': {
                'instructions': 'Part D instructions',
                'questions': {str(i): {
                    'text': f'Question {i}',
                    'options': [
                        {'code': 'L', 'text': 'Left'},
                        {'code': 'R', 'text': 'Right'}
                    ],
                    'type': 'scale'
                } for i in range(43, 57)}
            },
            'PartE': {
                'instructions': 'Part E instructions',
                'questions': {str(i): {
                    'text': f'Question {i}',
                    'options': [
                        {'code': 'a', 'text': 'A'},
                        {'code': 'b', 'text': 'B'},
                        {'code': 'c', 'text': 'C'}
                    ],
                    'type': 'ranking'
                } for i in range(57, 62)}
            },
            'PartF': {
                'instructions': 'Part F instructions',
                'questions': {str(i): {
                    'text': f'Question {i}',
                    'options': [
                        {'code': 'a', 'text': 'A'},
                        {'code': 'b', 'text': 'B'},
                        {'code': 'c', 'text': 'C'}
                    ],
                    'type': 'single'
                } for i in range(62, 68)}
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


class TestCompletionPersonalization:
    """Property 11: Completion message includes user name.

    For any non-empty user first name string, the completion screen
    congratulatory message shall contain that name.

    **Validates: Requirements 9.2**
    """

    @given(first_name=name_strategy)
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_completion_heading_contains_user_name(self, first_name):
        """Property: For any non-empty first name, the completion heading
        message contains that name.

        **Validates: Requirements 9.2**
        """
        heading = generate_completion_heading(first_name)
        assert first_name in heading, (
            f"Completion heading must contain the user's first name '{first_name}'. "
            f"Got heading: '{heading}'"
        )

    @given(first_name=name_strategy)
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_completion_heading_format_with_name(self, first_name):
        """Property: For any non-empty first name, the completion heading
        follows the expected format '🎉 כל הכבוד, {name}!'.

        **Validates: Requirements 9.2**
        """
        heading = generate_completion_heading(first_name)
        expected = f"🎉 כל הכבוד, {first_name}!"
        assert heading == expected, (
            f"Completion heading format mismatch. "
            f"Expected: '{expected}', Got: '{heading}'"
        )

    @given(first_name=name_strategy)
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_template_populates_username_hidden_input(self, app, first_name):
        """Property: For any non-empty first name stored in the session,
        the rendered questionnaire template contains a hidden input with
        that name value, making it available for the completion screen.

        **Validates: Requirements 9.2**
        """
        with app.test_client() as client:
            # Set up session with user data containing the first name
            with client.session_transaction() as sess:
                sess['email'] = 'test@example.com'
                sess['user_data'] = {'first_name': first_name}

            # Request the chat page which renders questionnaire.html
            response = client.get('/pdn-diagnose/chat')
            assert response.status_code == 200

            html = response.data.decode('utf-8')
            # The template renders: <input type="hidden" id="userName" value="{{ user_name or '' }}">
            # Verify the user's first name appears in the rendered HTML
            assert first_name in html, (
                f"The rendered questionnaire template must contain the user's "
                f"first name '{first_name}' in the hidden userName input field."
            )
