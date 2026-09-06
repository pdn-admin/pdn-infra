"""Property tests for relationship routes: login validation and session storage.

**Validates: Correctness Property 1** - Login validates partner_code against known PDN codes
**Validates: Correctness Property 5** - Session stores relationship context after login
"""

import tempfile
from unittest.mock import patch, MagicMock

import pytest
from hypothesis import given, settings, HealthCheck, assume
from hypothesis import strategies as st
from flask import Flask

from app.pdn_relationships.constants import PDN_CODES, RelationshipType
from app.pdn_relationships.relationship_routes import pdn_relationships_bp


# --- Strategies ---
valid_pdn_code_strategy = st.sampled_from(PDN_CODES)
relationship_type_strategy = st.sampled_from(["partner", "friend", "colleague"])
invalid_pdn_code_strategy = st.text(min_size=1, max_size=10).filter(
    lambda x: x.strip().lower() not in PDN_CODES
)


def _create_test_app():
    """Create a minimal Flask app with the relationship blueprint registered."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['SESSION_TYPE'] = 'filesystem'
    app.register_blueprint(pdn_relationships_bp, url_prefix='/pdn-relationships')
    return app


def _mock_user_data():
    """Return a mock user data dict matching what get_user_manager().get_user() returns."""
    return {
        'password': 'testpass',
        'name': 'Test User',
        'pdn_code': 'a3',
        'daily_conversation_limit': 15,
    }


class TestLoginValidatesPartnerCode:
    """Property 1: Login validates partner_code against known PDN codes.

    **Validates: Correctness Property 1**

    All valid PDN codes should be accepted (return 200);
    invalid codes should return 400.
    """

    @given(partner_code=valid_pdn_code_strategy)
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_valid_pdn_codes_accepted(self, partner_code):
        """Property: For any valid PDN code, login returns 200 (success)."""
        app = _create_test_app()

        with patch(
            'app.pdn_relationships.relationship_routes.get_user_manager'
        ) as mock_um:
            mock_mgr = MagicMock()
            mock_mgr.get_user.return_value = _mock_user_data()
            mock_um.return_value = mock_mgr

            with patch(
                'app.pdn_relationships.relationship_routes.get_relationship_agent'
            ) as mock_agent_factory:
                mock_agent = MagicMock()
                mock_agent_factory.return_value = mock_agent

                with patch(
                    'app.pdn_relationships.relationship_routes._history_service'
                ) as mock_history:
                    mock_history.load_user_history.return_value = None

                    with app.test_client() as client:
                        response = client.post(
                            '/pdn-relationships/login',
                            json={
                                'email': 'test@example.com',
                                'password': 'testpass',
                                'partner_code': partner_code,
                                'relationship_type': 'partner',
                            },
                        )

                        assert response.status_code == 200, (
                            f"Valid PDN code '{partner_code}' should be accepted "
                            f"but got status {response.status_code}: "
                            f"{response.get_json()}"
                        )
                        data = response.get_json()
                        assert data['success'] is True

    @given(partner_code=invalid_pdn_code_strategy)
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_invalid_pdn_codes_rejected(self, partner_code):
        """Property: For any invalid PDN code, login returns 400."""
        app = _create_test_app()

        with patch(
            'app.pdn_relationships.relationship_routes.get_user_manager'
        ) as mock_um:
            mock_mgr = MagicMock()
            mock_mgr.get_user.return_value = _mock_user_data()
            mock_um.return_value = mock_mgr

            with app.test_client() as client:
                response = client.post(
                    '/pdn-relationships/login',
                    json={
                        'email': 'test@example.com',
                        'password': 'testpass',
                        'partner_code': partner_code,
                        'relationship_type': 'partner',
                    },
                )

                assert response.status_code == 400, (
                    f"Invalid PDN code '{partner_code}' should be rejected "
                    f"but got status {response.status_code}: "
                    f"{response.get_json()}"
                )


class TestErrorDecoratorExceptionToStatusMapping:
    """Property 8: Error Decorator Exception-to-Status Mapping.

    **Validates: Requirements 10.5**

    For any exception type in {ValueError→400, TimeoutError→503, Exception→500},
    the handle_errors decorator returns the corresponding HTTP status code.
    """

    # Strategy: sample from the known exception-to-status mappings
    error_mapping_strategy = st.sampled_from([
        (ValueError, 400),
        (TimeoutError, 503),
        (ConnectionError, 503),
        (Exception, 500),
        (RuntimeError, 500),
        (TypeError, 500),
        (KeyError, 500),
    ])

    error_message_strategy = st.text(min_size=1, max_size=100).filter(
        lambda x: x.strip() != ''
    )

    @given(
        error_mapping=error_mapping_strategy,
        error_message=error_message_strategy,
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_exception_type_maps_to_correct_status_code(self, error_mapping, error_message):
        """Property: For any exception type in the mapping, handle_errors returns
        the corresponding HTTP status code regardless of the error message content."""
        from app.pdn_relationships.relationship_routes import handle_errors

        exception_class, expected_status = error_mapping

        app = _create_test_app()

        with app.app_context():
            # Create a decorated function that raises the given exception
            @handle_errors
            def failing_endpoint():
                raise exception_class(error_message)

            # Use test request context to simulate a request
            with app.test_request_context():
                result = failing_endpoint()

                # handle_errors returns a tuple (response, status_code)
                response, status_code = result

                assert status_code == expected_status, (
                    f"Exception {exception_class.__name__}('{error_message}') "
                    f"should map to status {expected_status} but got {status_code}"
                )

                # Verify response is valid JSON with an 'error' key
                response_data = response.get_json()
                assert 'error' in response_data, (
                    f"Response should contain 'error' key but got: {response_data}"
                )


class TestSessionStoresRelationshipContext:
    """Property 5: Session stores relationship context after login.

    **Validates: Correctness Property 5**

    After successful login, session contains `partner_code` and
    `relationship_type` matching the input values.
    """

    @given(
        partner_code=valid_pdn_code_strategy,
        relationship_type=relationship_type_strategy,
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_session_contains_partner_code_and_relationship_type(
        self, partner_code, relationship_type
    ):
        """Property: After successful login, session contains the correct
        partner_code and relationship_type matching the login input."""
        app = _create_test_app()

        with patch(
            'app.pdn_relationships.relationship_routes.get_user_manager'
        ) as mock_um:
            mock_mgr = MagicMock()
            mock_mgr.get_user.return_value = _mock_user_data()
            mock_um.return_value = mock_mgr

            with patch(
                'app.pdn_relationships.relationship_routes.get_relationship_agent'
            ) as mock_agent_factory:
                mock_agent = MagicMock()
                mock_agent_factory.return_value = mock_agent

                with patch(
                    'app.pdn_relationships.relationship_routes._history_service'
                ) as mock_history:
                    mock_history.load_user_history.return_value = None

                    with app.test_client() as client:
                        response = client.post(
                            '/pdn-relationships/login',
                            json={
                                'email': 'test@example.com',
                                'password': 'testpass',
                                'partner_code': partner_code,
                                'relationship_type': relationship_type,
                            },
                        )

                        assert response.status_code == 200, (
                            f"Login should succeed but got {response.status_code}: "
                            f"{response.get_json()}"
                        )

                        # Verify session contents via the response JSON
                        # (the route returns partner_code and relationship_type)
                        data = response.get_json()
                        assert data['partner_code'] == partner_code, (
                            f"Response partner_code should be '{partner_code}' "
                            f"but got '{data.get('partner_code')}'"
                        )
                        assert data['relationship_type'] == relationship_type, (
                            f"Response relationship_type should be '{relationship_type}' "
                            f"but got '{data.get('relationship_type')}'"
                        )

                        # Also verify session directly using the chat-page route
                        # which reads from session
                        with client.session_transaction() as sess:
                            assert sess.get('partner_code') == partner_code, (
                                f"Session partner_code should be '{partner_code}' "
                                f"but got '{sess.get('partner_code')}'"
                            )
                            assert sess.get('relationship_type') == relationship_type, (
                                f"Session relationship_type should be "
                                f"'{relationship_type}' but got "
                                f"'{sess.get('relationship_type')}'"
                            )
