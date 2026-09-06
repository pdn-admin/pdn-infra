"""Property test: Scale question endpoint labels.

**Validates: Requirements 11.1**

Property 12: For any scale question with two options, both option text values
shall appear as visible labels on opposite sides of the scale. This is verified
by checking that the API response for scale questions (PartC: 38-42, PartD: 43-56)
always includes exactly 2 options with non-empty text values that the frontend
renders as endpoint labels via `data.options[0].text` and `data.options[1].text`.
"""

import pytest
from flask import Flask
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.pdn_diagnose.diagnosis_routes import pdn_diagnose_bp


# Scale question ranges: PartC (38-42) and PartD (43-56)
SCALE_QUESTION_NUMBERS = list(range(38, 57))


@pytest.fixture
def app():
    """Create a minimal Flask test app with the diagnose blueprint and scale questions."""
    application = Flask(__name__)
    application.config['TESTING'] = True
    application.config['SECRET_KEY'] = 'test-secret-key'
    application.config['ADMIN_PASSWORD'] = 'pdn'
    application.config['SESSION_TYPE'] = 'filesystem'
    application.config['QUESTIONS_FILE'] = {
        'phases': {
            'PersonalDetails': {
                'instructions': 'Personal details instructions'
            },
            'PartA': {
                'instructions': 'Part A instructions',
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
                'instructions': 'Part B instructions',
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
                'questions': {
                    '38': {
                        'text': 'באיזו מידה אתה נוטה לבדוק לעומק לפני נטילת סיכון?',
                        'options': [
                            {'code': 'A', 'text': 'לא מוודא כלל'},
                            {'code': 'T', 'text': 'מוודא כל פרט'}
                        ],
                        'type': 'scale'
                    },
                    '39': {
                        'text': 'עד כמה קשה לך להסתדר עם מצבי חוסר ודאות?',
                        'options': [
                            {'code': 'A', 'text': 'לא מתקשה כלל'},
                            {'code': 'T', 'text': 'מתקשה מאוד'}
                        ],
                        'type': 'scale'
                    },
                    '40': {
                        'text': 'באיזו מידה אתה מקבל החלטות במהירות באופן כללי?',
                        'options': [
                            {'code': 'P', 'text': 'מתקשה להחליט'},
                            {'code': 'E', 'text': 'מקבל החלטות במהירות'}
                        ],
                        'type': 'scale'
                    },
                    '41': {
                        'text': 'האם קשה לך לקבל הנחיות והובלה מאחרים?',
                        'options': [
                            {'code': 'E', 'text': 'קשה לי מאוד שמובילים אותי'},
                            {'code': 'P', 'text': 'אין לי קושי כלל שמובילים אותי'}
                        ],
                        'type': 'scale'
                    },
                    '42': {
                        'text': 'עד כמה אתה מרגיש נוח להוביל אחרים כשאין הנהגה ברורה?',
                        'options': [
                            {'code': 'P', 'text': 'מעדיף להישאר בצד'},
                            {'code': 'E', 'text': 'לוקח הובלה בלי היסוס'}
                        ],
                        'type': 'scale'
                    }
                }
            },
            'PartD': {
                'instructions': 'סמן את מיקומך על הסקאלה בחלק ד.',
                'questions': {str(i): {
                    'text': f'PartD scale question {i}',
                    'options': [
                        {'code': 'L', 'text': f'Left endpoint {i}'},
                        {'code': 'R', 'text': f'Right endpoint {i}'}
                    ],
                    'type': 'scale'
                } for i in range(43, 57)}
            },
            'PartE': {
                'instructions': 'Part E instructions',
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
                'instructions': 'Part F instructions',
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


# Strategy for scale question numbers (PartC: 38-42, PartD: 43-56)
scale_question_strategy = st.sampled_from(SCALE_QUESTION_NUMBERS)


class TestScaleEndpointLabels:
    """Property 12: Scale question endpoint labels.

    For any scale question with two options, both option text values shall
    appear as visible labels on opposite sides of the scale. The frontend
    code in renderScaleQuestion() uses data.options[0].text and
    data.options[1].text as endpoint labels.

    **Validates: Requirements 11.1**
    """

    @given(question_number=scale_question_strategy)
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_scale_question_has_exactly_two_options(self, app, question_number):
        """Property: For any scale question, the API response includes exactly
        2 options that serve as endpoint labels.

        **Validates: Requirements 11.1**
        """
        with app.test_client() as client:
            response = client.get(f'/pdn-diagnose/questionnaire/{question_number}')
            assert response.status_code == 200

            data = response.get_json()
            assert 'options' in data, (
                f"Scale question {question_number} response must include 'options' field"
            )
            assert len(data['options']) == 2, (
                f"Scale question {question_number} must have exactly 2 options "
                f"(endpoint labels), got {len(data['options'])}"
            )

    @given(question_number=scale_question_strategy)
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_scale_options_have_non_empty_text(self, app, question_number):
        """Property: For any scale question, both options have non-empty text
        values that the frontend renders as visible endpoint labels.

        **Validates: Requirements 11.1**
        """
        with app.test_client() as client:
            response = client.get(f'/pdn-diagnose/questionnaire/{question_number}')
            assert response.status_code == 200

            data = response.get_json()
            options = data['options']

            # First option text (right label in RTL layout)
            assert 'text' in options[0], (
                f"Scale question {question_number} first option must have 'text' field"
            )
            assert options[0]['text'] is not None and len(options[0]['text'].strip()) > 0, (
                f"Scale question {question_number} first option text must be non-empty "
                f"to serve as a visible endpoint label, got: '{options[0].get('text')}'"
            )

            # Second option text (left label in RTL layout)
            assert 'text' in options[1], (
                f"Scale question {question_number} second option must have 'text' field"
            )
            assert options[1]['text'] is not None and len(options[1]['text'].strip()) > 0, (
                f"Scale question {question_number} second option text must be non-empty "
                f"to serve as a visible endpoint label, got: '{options[1].get('text')}'"
            )

    @given(question_number=scale_question_strategy)
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_scale_options_are_distinct_labels(self, app, question_number):
        """Property: For any scale question, the two endpoint labels are distinct
        from each other (they represent opposite ends of the scale).

        **Validates: Requirements 11.1**
        """
        with app.test_client() as client:
            response = client.get(f'/pdn-diagnose/questionnaire/{question_number}')
            assert response.status_code == 200

            data = response.get_json()
            options = data['options']

            left_label = options[0]['text']
            right_label = options[1]['text']

            assert left_label != right_label, (
                f"Scale question {question_number} endpoint labels must be distinct. "
                f"Both labels are: '{left_label}'"
            )

    @given(question_number=scale_question_strategy)
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_scale_question_is_in_correct_phase(self, app, question_number):
        """Property: For any scale question number (38-56), the response stage
        is either PartC or PartD (the scale question phases).

        **Validates: Requirements 11.1**
        """
        with app.test_client() as client:
            response = client.get(f'/pdn-diagnose/questionnaire/{question_number}')
            assert response.status_code == 200

            data = response.get_json()
            assert data['stage'] in ('PartC', 'PartD'), (
                f"Scale question {question_number} should be in PartC or PartD, "
                f"got stage '{data['stage']}'"
            )
