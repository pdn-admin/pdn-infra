"""Property test: No validation on initial question display.

**Validates: Requirements 2.1**

Property 4: For any initial page load of the questionnaire, no validation
message element (class 'validation-message') shall be present or visible
in the DOM. Validation messages should only appear after the user attempts
to proceed without selecting an answer.
"""

import pytest
from flask import Flask
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.pdn_diagnose.diagnosis_routes import pdn_diagnose_bp


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
                    '1': {
                        'text': 'What is your preference?',
                        'options': [
                            {'code': 'a', 'text': 'Option A'},
                            {'code': 'b', 'text': 'Option B'}
                        ],
                        'type': 'single'
                    },
                    '2': {
                        'text': 'Second question?',
                        'options': [
                            {'code': 'a', 'text': 'Option A'},
                            {'code': 'b', 'text': 'Option B'}
                        ],
                        'type': 'single'
                    }
                }
            },
            'PartB': {
                'instructions': 'Part B instructions',
                'questions': {
                    '27': {
                        'text': 'Part B question',
                        'options': [
                            {'code': 'a', 'text': 'Option A'},
                            {'code': 'b', 'text': 'Option B'},
                            {'code': 'c', 'text': 'Option C'}
                        ],
                        'type': 'ranking'
                    }
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
    """Create a client with an active session and user data."""
    client.post('/pdn-diagnose/login', json={
        'email': 'test@example.com',
        'password': 'pdn'
    })
    with client.session_transaction() as sess:
        sess['user_data'] = {'first_name': 'Test'}
    return client


class TestNoValidationOnInitialRender:
    """Property 4: No validation on initial question display.

    For any initial page load of the questionnaire, no element with class
    'validation-message' shall be present in the rendered HTML.
    """

    def test_no_validation_message_on_initial_page_load(self, logged_in_client):
        """The questionnaire page should not contain any validation-message
        elements when first rendered."""
        response = logged_in_client.get('/pdn-diagnose/chat')
        assert response.status_code == 200
        html = response.data.decode('utf-8')

        # The CSS class definition in <style> is expected, but no actual
        # validation-message DOM element should be present in the HTML body
        # Split at </style> to only check the body content
        parts = html.split('</style>')
        body_html = parts[-1] if len(parts) > 1 else html

        # No element with class="validation-message" should exist in the body
        assert 'class="validation-message"' not in body_html, (
            "Found a validation-message element in the initial page render. "
            "Validation messages should only appear after user attempts to proceed."
        )

    @given(
        email=st.emails(),
        first_name=st.text(
            alphabet=st.characters(whitelist_categories=('L', 'N', 'Zs')),
            min_size=1,
            max_size=50
        )
    )
    @settings(
        max_examples=20,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture]
    )
    def test_no_validation_message_for_any_user(self, app, email, first_name):
        """Property: For any valid user session, the initial questionnaire
        page render shall contain no validation-message DOM elements.

        This property holds regardless of the user's email or name.
        """
        with app.test_client() as client:
            # Log in with the generated email
            client.post('/pdn-diagnose/login', json={
                'email': email,
                'password': 'pdn'
            })
            with client.session_transaction() as sess:
                sess['user_data'] = {'first_name': first_name}

            response = client.get('/pdn-diagnose/chat')
            assert response.status_code == 200
            html = response.data.decode('utf-8')

            # Only check body content (after style definitions)
            parts = html.split('</style>')
            body_html = parts[-1] if len(parts) > 1 else html

            # No validation-message element should be present in the DOM
            assert 'class="validation-message"' not in body_html, (
                f"Found a validation-message element in initial render for "
                f"user '{email}'. Validation messages must only appear after "
                f"the user attempts to proceed without answering."
            )

    def test_validation_css_class_defined_but_not_instantiated(self, logged_in_client):
        """The .validation-message CSS class should be defined in styles
        (for later dynamic use) but no actual element should use it on load."""
        response = logged_in_client.get('/pdn-diagnose/chat')
        assert response.status_code == 200
        html = response.data.decode('utf-8')

        # CSS definition should exist (in <style> block)
        assert '.validation-message' in html, (
            "Expected .validation-message CSS class to be defined in styles"
        )

        # But no DOM element should have it as a class attribute in the body
        parts = html.split('</style>')
        body_html = parts[-1] if len(parts) > 1 else html
        assert 'class="validation-message"' not in body_html
        assert "class='validation-message'" not in body_html
