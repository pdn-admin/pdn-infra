"""Tests for diagnosis routes to achieve >80% code coverage.

Tests login, user info, questionnaire, answer submission,
report generation, and chat page endpoints.
"""

import pytest
from unittest.mock import patch, MagicMock
from flask import Flask

from app.pdn_diagnose.diagnosis_routes import pdn_diagnose_bp, active_sessions, _send_admin_notification


@pytest.fixture(autouse=True)
def clear_active_sessions():
    """Clear active sessions before each test."""
    active_sessions.clear()
    yield
    active_sessions.clear()


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
                        'text': 'Ranking question?',
                        'options': [
                            {'code': 'a', 'text': 'Option A'},
                            {'code': 'b', 'text': 'Option B'}
                        ],
                        'type': 'ranking'
                    }
                }
            },
            'PartB': {
                'instructions': 'Part B instructions',
                'questions': {
                    '27': {
                        'text': 'Part B question',
                        'options': [{'code': 'a', 'text': 'Option A'}],
                        'type': 'single'
                    }
                }
            }
        }
    }
    application.register_blueprint(pdn_diagnose_bp, url_prefix='/pdn-diagnose')

    # Initialize Flask-Session so session.sid is available
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
    """Create a client with an active session (set email directly in session)."""
    with client.session_transaction() as sess:
        sess['email'] = 'test@example.com'
    return client


class TestHomePage:
    """Tests for the home/login page."""

    def test_home_page(self, client):
        """GET / renders login page."""
        response = client.get('/pdn-diagnose/')
        assert response.status_code == 200


class TestLogin:
    """Tests for the login endpoint."""

    def test_login_valid_credentials(self, client):
        """Valid password (email local part) returns success."""
        response = client.post('/pdn-diagnose/login', json={
            'email': 'test@example.com',
            'password': 'test'
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['message'] == 'Login successful'

    def test_login_email_lowercased(self, client):
        """Email is stored in lowercase."""
        client.post('/pdn-diagnose/login', json={
            'email': 'TEST@EXAMPLE.COM',
            'password': 'test'
        })
        with client.session_transaction() as sess:
            assert sess.get('email') == 'test@example.com'

    def test_login_invalid_credentials(self, client):
        """Invalid password returns 401."""
        response = client.post('/pdn-diagnose/login', json={
            'email': 'test@example.com',
            'password': 'wrong'
        })
        assert response.status_code == 401
        data = response.get_json()
        assert 'error' in data

    def test_login_malformed_request(self, client):
        """Malformed request returns 400."""
        response = client.post('/pdn-diagnose/login',
                               data='not json',
                               content_type='application/json')
        assert response.status_code == 400

    @patch('app.pdn_diagnose.diagnosis_routes.get_coupon_manager')
    def test_login_coupon_valid(self, mock_get_cm, client):
        """Valid coupon code returns success."""
        mock_cm = MagicMock()
        mock_cm.validate_and_redeem.return_value = (True, "Valid", {"code": "TESTCODE"})
        mock_get_cm.return_value = mock_cm

        response = client.post('/pdn-diagnose/login', json={
            'password': 'TESTCODE',
            'email': 'user@example.com'
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['message'] == 'Login successful'
        # Verify session has email and coupon_code
        with client.session_transaction() as sess:
            assert sess['email'] == 'user@example.com'
            assert sess['coupon_code'] == 'TESTCODE'

    @patch('app.pdn_diagnose.diagnosis_routes.get_coupon_manager')
    def test_login_coupon_invalid(self, mock_get_cm, client):
        """Invalid coupon code returns 401."""
        mock_cm = MagicMock()
        mock_cm.validate_and_redeem.return_value = (False, "Invalid coupon code", None)
        mock_get_cm.return_value = mock_cm

        response = client.post('/pdn-diagnose/login', json={
            'password': 'BADCODE',
            'email': 'user@example.com'
        })
        assert response.status_code == 401
        data = response.get_json()
        assert 'error' in data

    @patch('app.pdn_diagnose.diagnosis_routes.get_coupon_manager')
    def test_login_coupon_exhausted(self, mock_get_cm, client):
        """Exhausted coupon (usage limit reached) returns 403."""
        mock_cm = MagicMock()
        mock_cm.validate_and_redeem.return_value = (False, "Coupon has reached its usage limit", None)
        mock_get_cm.return_value = mock_cm

        response = client.post('/pdn-diagnose/login', json={
            'password': 'USEDCODE',
            'email': 'user@example.com'
        })
        assert response.status_code == 403
        data = response.get_json()
        assert 'usage limit' in data['error']

    def test_login_coupon_missing_email(self, client):
        """Coupon login without email returns 400."""
        response = client.post('/pdn-diagnose/login', json={
            'password': 'TESTCODE',
            'email': ''
        })
        assert response.status_code == 400
        data = response.get_json()
        assert 'Email is required' in data['error']


class TestUserInfo:
    """Tests for user info endpoints."""

    def test_user_info_page(self, logged_in_client):
        """GET /user_info renders user form."""
        response = logged_in_client.get('/pdn-diagnose/user_info')
        assert response.status_code == 200

    @patch('app.pdn_diagnose.diagnosis_routes.save_user_metadata')
    def test_save_user_info_success(self, mock_save, logged_in_client):
        """POST /user_info saves user data."""
        response = logged_in_client.post('/pdn-diagnose/user_info', json={
            'email': 'Test@Example.com',
            'first_name': 'Test',
            'last_name': 'User',
            'phone': '0501234567'
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['message'] == 'User information saved successfully.'
        # Verify email was lowercased
        call_args = mock_save.call_args[0]
        assert call_args[0]['email'] == 'test@example.com'

    def test_save_user_info_error(self, logged_in_client):
        """POST /user_info with invalid data returns 400."""
        with patch('app.pdn_diagnose.diagnosis_routes.save_user_metadata', side_effect=ValueError("Invalid data")):
            response = logged_in_client.post('/pdn-diagnose/user_info', json={
                'email': 'test@example.com'
            })
            assert response.status_code == 400


class TestQuestionnaire:
    """Tests for questionnaire endpoints."""

    def test_get_question_valid(self, logged_in_client):
        """GET /questionnaire/<n> returns question data."""
        response = logged_in_client.get('/pdn-diagnose/questionnaire/1')
        assert response.status_code == 200
        data = response.get_json()
        assert data['question_number'] == 1
        assert 'question' in data
        assert 'options' in data

    def test_get_question_part_b(self, logged_in_client):
        """GET /questionnaire/<n> returns Part B question."""
        response = logged_in_client.get('/pdn-diagnose/questionnaire/27')
        assert response.status_code == 200
        data = response.get_json()
        assert data['stage'] == 'PartB'

    def test_get_question_out_of_range(self, logged_in_client):
        """GET /questionnaire/<n> for invalid number returns no-more message."""
        response = logged_in_client.get('/pdn-diagnose/questionnaire/999')
        assert response.status_code == 200
        data = response.get_json()
        assert 'message' in data


class TestAnswerSubmission:
    """Tests for answer submission endpoint."""

    @patch('app.pdn_diagnose.diagnosis_routes.save_answer')
    def test_submit_answer_regular(self, mock_save, logged_in_client):
        """POST /answer saves a regular answer."""
        response = logged_in_client.post('/pdn-diagnose/answer', json={
            'question_number': 1,
            'selected_option_code': 'a',
            'ranking': None
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['message'] == 'Answer saved successfully'

    @patch('app.pdn_diagnose.diagnosis_routes.save_answer')
    def test_submit_answer_ranking(self, mock_save, logged_in_client):
        """POST /answer saves a ranking answer."""
        response = logged_in_client.post('/pdn-diagnose/answer', json={
            'question_number': 2,
            'selected_option_code': None,
            'ranking': ['a', 'b']
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['message'] == 'Answer saved successfully'

    def test_submit_answer_missing_question_number(self, logged_in_client):
        """POST /answer without question_number returns 400."""
        response = logged_in_client.post('/pdn-diagnose/answer', json={
            'selected_option_code': 'a'
        })
        assert response.status_code == 400

    def test_submit_answer_missing_option_code(self, logged_in_client):
        """POST /answer without selected_option_code for regular question returns 400."""
        response = logged_in_client.post('/pdn-diagnose/answer', json={
            'question_number': 1,
            'selected_option_code': None,
            'ranking': None
        })
        assert response.status_code == 400

    @patch('app.pdn_diagnose.diagnosis_routes.save_answer', side_effect=Exception("DB error"))
    def test_submit_answer_save_error(self, mock_save, logged_in_client):
        """POST /answer with save error returns 500."""
        response = logged_in_client.post('/pdn-diagnose/answer', json={
            'question_number': 1,
            'selected_option_code': 'a',
            'ranking': None
        })
        assert response.status_code == 500


class TestDeleteAnswer:
    """Tests for delete answer endpoint."""

    @patch('app.pdn_diagnose.diagnosis_routes.delete_answer')
    def test_delete_answer_success(self, mock_delete, logged_in_client):
        """POST /delete_answer removes an answer."""
        mock_delete.return_value = True
        response = logged_in_client.post('/pdn-diagnose/delete_answer', json={
            'question_number': 1
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    def test_delete_answer_missing_question_number(self, logged_in_client):
        """POST /delete_answer without question_number returns 400."""
        response = logged_in_client.post('/pdn-diagnose/delete_answer', json={})
        assert response.status_code == 400

    @patch('app.pdn_diagnose.diagnosis_routes.delete_answer', side_effect=Exception("Error"))
    def test_delete_answer_error(self, mock_delete, logged_in_client):
        """POST /delete_answer with error returns 400."""
        response = logged_in_client.post('/pdn-diagnose/delete_answer', json={
            'question_number': 1
        })
        assert response.status_code == 400


class TestGetProgress:
    """Tests for get_progress endpoint."""

    @patch('app.pdn_diagnose.diagnosis_routes.load_answers')
    def test_get_progress_with_answers(self, mock_load, logged_in_client):
        """GET /get_progress returns max answered question number."""
        mock_load.return_value = {'1': {'selected_option_code': 'a'}, '5': {'selected_option_code': 'b'}, '3': {'selected_option_code': 'a'}}
        response = logged_in_client.get('/pdn-diagnose/get_progress')
        assert response.status_code == 200
        data = response.get_json()
        assert data['current_question'] == 5

    @patch('app.pdn_diagnose.diagnosis_routes.load_answers')
    def test_get_progress_no_answers(self, mock_load, logged_in_client):
        """GET /get_progress with no answers returns 0."""
        mock_load.return_value = None
        response = logged_in_client.get('/pdn-diagnose/get_progress')
        assert response.status_code == 200
        data = response.get_json()
        assert data['current_question'] == 0

    @patch('app.pdn_diagnose.diagnosis_routes.load_answers')
    def test_get_progress_empty_answers(self, mock_load, logged_in_client):
        """GET /get_progress with empty answers dict returns 0."""
        mock_load.return_value = {}
        response = logged_in_client.get('/pdn-diagnose/get_progress')
        assert response.status_code == 200
        data = response.get_json()
        assert data['current_question'] == 0

    def test_get_progress_requires_auth(self, client):
        """GET /get_progress without auth returns 401."""
        response = client.get('/pdn-diagnose/get_progress')
        assert response.status_code == 401


class TestCompleteQuestionnaire:
    """Tests for complete questionnaire endpoint."""

    @patch('app.pdn_diagnose.diagnosis_routes.threading.Thread')
    @patch('app.utils.csv_metadata_handler.UserMetadataHandler')
    @patch('app.pdn_diagnose.diagnosis_routes.calculate_pdn_code')
    @patch('app.pdn_diagnose.diagnosis_routes.load_answers')
    def test_complete_questionnaire_success(self, mock_load, mock_calc, mock_handler_cls, mock_thread, logged_in_client):
        """POST /complete_questionnaire calculates PDN code."""
        mock_load.return_value = {'1': {'selected_option_code': 'a'}, '2': {'selected_option_code': 'b'}}
        mock_calc.return_value = 'a3'
        mock_handler = MagicMock()
        mock_handler_cls.return_value = mock_handler

        response = logged_in_client.post('/pdn-diagnose/complete_questionnaire')
        assert response.status_code == 200
        data = response.get_json()
        assert data['pdn_code'] == 'a3'

    @patch('app.pdn_diagnose.diagnosis_routes.load_answers')
    def test_complete_questionnaire_no_answers(self, mock_load, logged_in_client):
        """POST /complete_questionnaire with no answers returns 400."""
        mock_load.return_value = None
        response = logged_in_client.post('/pdn-diagnose/complete_questionnaire')
        assert response.status_code == 400

    @patch('app.pdn_diagnose.diagnosis_routes.calculate_pdn_code')
    @patch('app.pdn_diagnose.diagnosis_routes.load_answers')
    def test_complete_questionnaire_no_pdn_code(self, mock_load, mock_calc, logged_in_client):
        """POST /complete_questionnaire with insufficient answers returns 400."""
        mock_load.return_value = {'1': {'selected_option_code': 'a'}}
        mock_calc.return_value = None
        response = logged_in_client.post('/pdn-diagnose/complete_questionnaire')
        assert response.status_code == 400


class TestReport:
    """Tests for report endpoints."""

    def test_pdn_report_page(self, logged_in_client):
        """GET /pdn_report renders report page."""
        response = logged_in_client.get('/pdn-diagnose/pdn_report')
        assert response.status_code == 200

    @patch('app.pdn_diagnose.diagnosis_routes.calculate_pdn_code')
    @patch('app.pdn_diagnose.diagnosis_routes.load_answers')
    def test_get_report_data_success(self, mock_load, mock_calc, logged_in_client):
        """GET /get_report_data returns report data with pdn_code."""
        mock_load.return_value = {'1': {'selected_option_code': 'a'}}
        mock_calc.return_value = 'e5'
        # Set user_data in session
        with logged_in_client.session_transaction() as sess:
            sess['user_data'] = {'first_name': 'Test', 'last_name': 'User'}

        response = logged_in_client.get('/pdn-diagnose/get_report_data')
        assert response.status_code == 200
        data = response.get_json()
        assert 'metadata' in data
        assert data['metadata']['first_name'] == 'Test'
        assert data['metadata']['last_name'] == 'User'
        assert data['metadata']['email'] == 'test@example.com'
        assert data['pdn_code'] == 'e5'

    @patch('app.pdn_diagnose.diagnosis_routes.calculate_pdn_code')
    @patch('app.pdn_diagnose.diagnosis_routes.load_answers')
    def test_get_report_data_no_pdn_code(self, mock_load, mock_calc, logged_in_client):
        """GET /get_report_data with no calculable PDN code returns 'N/A'."""
        mock_load.return_value = {'1': {'selected_option_code': 'a'}}
        mock_calc.return_value = None

        response = logged_in_client.get('/pdn-diagnose/get_report_data')
        assert response.status_code == 200
        data = response.get_json()
        assert data['pdn_code'] == 'N/A'

    @patch('app.pdn_diagnose.diagnosis_routes.load_answers')
    def test_get_report_data_no_answers(self, mock_load, logged_in_client):
        """GET /get_report_data with no answers returns 400."""
        mock_load.return_value = None
        response = logged_in_client.get('/pdn-diagnose/get_report_data')
        assert response.status_code == 400


class TestChatPage:
    """Tests for chat page endpoint."""

    def test_chat_page(self, logged_in_client):
        """GET /chat renders questionnaire page."""
        with logged_in_client.session_transaction() as sess:
            sess['user_data'] = {'first_name': 'Test'}
        response = logged_in_client.get('/pdn-diagnose/chat')
        assert response.status_code == 200


class TestSendAdminNotification:
    """Tests for _send_admin_notification helper."""

    @patch('app.pdn_diagnose.diagnosis_routes.threading.Thread')
    def test_send_admin_notification_starts_thread(self, mock_thread_cls, app):
        """_send_admin_notification dispatches email in a background thread."""
        mock_thread_instance = MagicMock()
        mock_thread_cls.return_value = mock_thread_instance

        with app.app_context():
            _send_admin_notification("Test Subject", "Test Body")

        # Verify Thread was created with daemon=True and started
        mock_thread_cls.assert_called_once()
        call_kwargs = mock_thread_cls.call_args[1]
        assert call_kwargs['daemon'] is True
        assert 'target' in call_kwargs
        mock_thread_instance.start.assert_called_once()

    @patch('app.pdn_diagnose.diagnosis_routes.send_email_via_smtp')
    def test_send_admin_notification_calls_smtp(self, mock_smtp, app):
        """_send_admin_notification thread target calls send_email_via_smtp."""
        with app.app_context():
            # Capture the thread target function by running it directly
            with patch('app.pdn_diagnose.diagnosis_routes.threading.Thread') as mock_thread_cls:
                mock_thread_instance = MagicMock()
                mock_thread_cls.return_value = mock_thread_instance

                _send_admin_notification("Test Subject", "Test Body")

                # Get the target function and call it directly
                call_kwargs = mock_thread_cls.call_args[1]
                target_fn = call_kwargs['target']

        # Execute the target function (simulating what the thread would do)
        target_fn()
        mock_smtp.assert_called_once()

    @patch('app.pdn_diagnose.diagnosis_routes.send_email_via_smtp', side_effect=Exception("SMTP error"))
    def test_send_admin_notification_handles_smtp_failure(self, mock_smtp, app):
        """_send_admin_notification thread target handles SMTP errors gracefully."""
        with app.app_context():
            with patch('app.pdn_diagnose.diagnosis_routes.threading.Thread') as mock_thread_cls:
                mock_thread_instance = MagicMock()
                mock_thread_cls.return_value = mock_thread_instance

                _send_admin_notification("Test Subject", "Test Body")

                call_kwargs = mock_thread_cls.call_args[1]
                target_fn = call_kwargs['target']

        # Execute the target function - should not raise
        target_fn()  # No exception raised despite SMTP failure


class TestCompleteQuestionnaireCSVUpdate:
    """Tests for complete_questionnaire CSV update path."""

    @patch('app.pdn_diagnose.diagnosis_routes.threading.Thread')
    @patch('app.utils.csv_metadata_handler.UserMetadataHandler')
    @patch('app.pdn_diagnose.diagnosis_routes.calculate_pdn_code')
    @patch('app.pdn_diagnose.diagnosis_routes.load_answers')
    def test_complete_questionnaire_updates_csv(self, mock_load, mock_calc, mock_handler_cls, mock_thread, logged_in_client):
        """POST /complete_questionnaire updates CSV with PDN code via UserMetadataHandler."""
        mock_load.return_value = {'1': {'selected_option_code': 'a'}, '2': {'selected_option_code': 'b'}}
        mock_calc.return_value = 'a3'
        mock_handler = MagicMock()
        mock_handler_cls.return_value = mock_handler

        response = logged_in_client.post('/pdn-diagnose/complete_questionnaire')
        assert response.status_code == 200
        data = response.get_json()
        assert data['pdn_code'] == 'a3'
        assert data['message'] == 'Questionnaire completed successfully'

        # Verify CSV handler was called with correct args
        mock_handler.update_pdn_code.assert_called_once_with('test@example.com', 'a3')

    @patch('app.pdn_diagnose.diagnosis_routes.threading.Thread')
    @patch('app.utils.csv_metadata_handler.UserMetadataHandler')
    @patch('app.pdn_diagnose.diagnosis_routes.calculate_pdn_code')
    @patch('app.pdn_diagnose.diagnosis_routes.load_answers')
    def test_complete_questionnaire_csv_failure_non_fatal(self, mock_load, mock_calc, mock_handler_cls, mock_thread, logged_in_client):
        """POST /complete_questionnaire succeeds even if CSV update fails."""
        mock_load.return_value = {'1': {'selected_option_code': 'a'}}
        mock_calc.return_value = 'e5'
        mock_handler = MagicMock()
        mock_handler.update_pdn_code.side_effect = Exception("CSV write error")
        mock_handler_cls.return_value = mock_handler

        response = logged_in_client.post('/pdn-diagnose/complete_questionnaire')
        # Should still succeed - CSV failure is non-fatal
        assert response.status_code == 200
        data = response.get_json()
        assert data['pdn_code'] == 'e5'

    @patch('app.pdn_diagnose.diagnosis_routes.threading.Thread')
    @patch('app.utils.csv_metadata_handler.UserMetadataHandler')
    @patch('app.pdn_diagnose.diagnosis_routes.calculate_pdn_code')
    @patch('app.pdn_diagnose.diagnosis_routes.load_answers')
    def test_complete_questionnaire_dict_result_extracts_code(self, mock_load, mock_calc, mock_handler_cls, mock_thread, logged_in_client):
        """POST /complete_questionnaire extracts pdn_code when calculator returns dict (stage_e_override/needs_verification)."""
        mock_load.return_value = {'1': {'selected_option_code': 'a'}, '2': {'selected_option_code': 'b'}}
        # Simulate the dict return when needs_verification or stage_e_override is True
        mock_calc.return_value = {
            'pdn_code': 'P6',
            'needs_verification': True,
            'stage_e_override': True,
            'dominant_before_stage_e': 'T',
            'scores': {'A': 10, 'T': 15, 'P': 16, 'E': 8, 'D': 10, 'S': 10, 'F': 20},
            'confidence_score': 12
        }
        mock_handler = MagicMock()
        mock_handler_cls.return_value = mock_handler

        response = logged_in_client.post('/pdn-diagnose/complete_questionnaire')
        assert response.status_code == 200
        data = response.get_json()
        # Must return the string code, NOT the entire dict
        assert data['pdn_code'] == 'P6'
        assert isinstance(data['pdn_code'], str)
        # CSV must be updated with the string code, not the dict
        mock_handler.update_pdn_code.assert_called_once_with('test@example.com', 'P6')


class TestSubmitAnswerSaveError:
    """Tests for save error returning HTTP 500."""

    @patch('app.pdn_diagnose.diagnosis_routes.save_answer', side_effect=Exception("Disk full"))
    def test_submit_answer_save_error_returns_500(self, mock_save, logged_in_client):
        """POST /answer with save error returns 500 with error message."""
        response = logged_in_client.post('/pdn-diagnose/answer', json={
            'question_number': 1,
            'selected_option_code': 'a',
            'ranking': None
        })
        assert response.status_code == 500
        data = response.get_json()
        assert 'error' in data
        assert 'Failed to save answer' in data['error']


# --- Property-Based Tests ---

from hypothesis import given, settings, strategies as st, HealthCheck


class TestPropertyDiagnosisProgressCalculation:
    """Property-based tests for diagnosis progress calculation.

    **Validates: Requirements 12.5**
    """

    @given(
        numeric_keys=st.lists(
            st.integers(min_value=1, max_value=200),
            min_size=1,
            max_size=20,
        )
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_progress_returns_max_numeric_key(self, numeric_keys, app, logged_in_client):
        """Property 21: For any set of saved answers with numeric string keys,
        get_progress returns the maximum numeric key value as current_question.

        **Validates: Requirements 12.5**
        """
        # Build an answers dict with numeric string keys
        answers = {str(k): {'selected_option_code': 'a'} for k in numeric_keys}
        expected_max = max(numeric_keys)

        with patch('app.pdn_diagnose.diagnosis_routes.load_answers', return_value=answers):
            response = logged_in_client.get('/pdn-diagnose/get_progress')
            assert response.status_code == 200
            data = response.get_json()
            assert data['current_question'] == expected_max

    @given(
        non_numeric_keys=st.lists(
            st.from_regex(r'[a-zA-Z_][a-zA-Z_0-9]*', fullmatch=True),
            min_size=0,
            max_size=10,
        )
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_progress_returns_zero_for_no_numeric_keys(self, non_numeric_keys, app, logged_in_client):
        """Property 21: For an empty answer set or one with no numeric keys,
        get_progress returns 0.

        **Validates: Requirements 12.5**
        """
        # Build an answers dict with only non-numeric keys (or empty)
        answers = {k: {'selected_option_code': 'a'} for k in non_numeric_keys}

        with patch('app.pdn_diagnose.diagnosis_routes.load_answers', return_value=answers):
            response = logged_in_client.get('/pdn-diagnose/get_progress')
            assert response.status_code == 200
            data = response.get_json()
            assert data['current_question'] == 0

    @given(
        numeric_keys=st.lists(
            st.integers(min_value=1, max_value=200),
            min_size=1,
            max_size=10,
        ),
        non_numeric_keys=st.lists(
            st.from_regex(r'[a-zA-Z_][a-zA-Z_]{2,8}', fullmatch=True),
            min_size=1,
            max_size=5,
        )
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    def test_progress_ignores_non_numeric_keys_in_mixed_dict(self, numeric_keys, non_numeric_keys, app, logged_in_client):
        """Property 21: In a mixed dict with both numeric and non-numeric keys,
        get_progress returns the max of only the numeric keys.

        **Validates: Requirements 12.5**
        """
        answers = {}
        for k in numeric_keys:
            answers[str(k)] = {'selected_option_code': 'a'}
        for k in non_numeric_keys:
            answers[k] = {'selected_option_code': 'b'}

        expected_max = max(numeric_keys)

        with patch('app.pdn_diagnose.diagnosis_routes.load_answers', return_value=answers):
            response = logged_in_client.get('/pdn-diagnose/get_progress')
            assert response.status_code == 200
            data = response.get_json()
            assert data['current_question'] == expected_max
